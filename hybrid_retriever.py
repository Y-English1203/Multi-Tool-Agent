"""混合检索器。

BM25 关键词召回 + Vector 语义召回 -> RRF 融合 -> CrossEncoder 精排。
全流程保留 Document 及 metadata（来源文档、页码），供回答引用。
"""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


class HybridRetriever:
    def __init__(
        self,
        vectorstore,
        reranker_model: str = "BAAI/bge-reranker-base",
        use_reranker: bool = True,
    ):
        self.vectorstore = vectorstore
        self.reranker = None
        self.reranker_model = reranker_model

        if use_reranker:
            try:
                print(f"[HybridRetriever] 正在加载 Reranker：{reranker_model}")
                from sentence_transformers import CrossEncoder

                self.reranker = CrossEncoder(reranker_model, device="cpu")
                print("[HybridRetriever] Reranker 加载完成")
            except Exception as exc:
                print(f"[HybridRetriever] Reranker 不可用，降级为 RRF 排序：{exc}")

        self.all_docs: list[Document] = []
        self.bm25: BM25Okapi | None = None
        self._load_documents()

    def _load_documents(self) -> None:
        data = self.vectorstore.get()
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []

        self.all_docs = []
        for index, content in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            self.all_docs.append(
                Document(page_content=content, metadata=metadata or {})
            )

        if self.all_docs:
            corpus = [list(doc.page_content) for doc in self.all_docs]
            self.bm25 = BM25Okapi(corpus)
        else:
            self.bm25 = None

        print(f"[HybridRetriever] 文档切片数量：{len(self.all_docs)}")

    def refresh(self) -> None:
        """知识库变更后重建内存索引。"""
        self._load_documents()

    def _bm25_search(self, query: str, top_k: int = 20) -> list[Document]:
        if not self.bm25 or not self.all_docs:
            return []

        scores = self.bm25.get_scores(list(query))
        top_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        return [self.all_docs[index] for index in top_indices if scores[index] > 0]

    def _vector_search(self, query: str, top_k: int = 20) -> list[Document]:
        try:
            return self.vectorstore.similarity_search(query, k=top_k)
        except Exception as exc:
            print(f"[HybridRetriever] 向量检索失败：{exc}")
            return []

    @staticmethod
    def _doc_key(doc: Document) -> str:
        page = doc.metadata.get("page", "unknown")
        source = doc.metadata.get("source", "unknown")
        return f"{source}::{page}::{doc.page_content}"

    def _rrf_fusion(
        self,
        bm25_results: list[Document],
        vector_results: list[Document],
        k: int = 60,
    ) -> list[Document]:
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(bm25_results):
            key = self._doc_key(doc)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(vector_results):
            key = self._doc_key(doc)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        return [doc_map[key] for key in sorted_keys]

    def _rerank(
        self,
        query: str,
        candidates: list[Document],
        top_k: int = 10,
    ) -> list[tuple[Document, float]]:
        if not candidates:
            return []

        if self.reranker is None:
            return [
                (doc, round(1.0 / (rank + 1), 4))
                for rank, doc in enumerate(candidates[:top_k])
            ]

        pairs = [[query, doc.page_content] for doc in candidates]
        scores = self.reranker.predict(pairs)

        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(doc, float(score)) for doc, score in ranked[:top_k]]

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        bm25_results = self._bm25_search(query, top_k=20)
        vector_results = self._vector_search(query, top_k=20)
        fused = self._rrf_fusion(bm25_results, vector_results)
        reranked = self._rerank(query, fused[:20], top_k=top_k * 2)

        selected: list[dict[str, Any]] = []
        seen: set[str] = set()

        # 优先保证页码多样性
        for doc, score in reranked:
            page = doc.metadata.get("page")
            source = doc.metadata.get("source", "")
            key = f"{source}::{page}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(
                {
                    "content": doc.page_content,
                    "source": source,
                    "page": page,
                    "score": round(score, 4),
                    "metadata": doc.metadata,
                }
            )
            if len(selected) >= top_k:
                break

        # 结果不足时用剩余结果补齐
        if len(selected) < top_k:
            used_content = {(item["content"], item.get("page")) for item in selected}
            for doc, score in reranked:
                if (doc.page_content, doc.metadata.get("page")) in used_content:
                    continue
                selected.append(
                    {
                        "content": doc.page_content,
                        "source": doc.metadata.get("source", ""),
                        "page": doc.metadata.get("page"),
                        "score": round(score, 4),
                        "metadata": doc.metadata,
                    }
                )
                if len(selected) >= top_k:
                    break

        return selected

    def retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        return [
            Document(
                page_content=item["content"],
                metadata=item["metadata"],
            )
            for item in self.retrieve_with_scores(query, top_k=top_k)
        ]
