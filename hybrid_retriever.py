import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document


class HybridRetriever:
    """
    混合检索器：

    BM25 关键词召回
        +
    Vector 语义召回
        ↓
    RRF 融合
        ↓
    CrossEncoder Reranker 精排
        ↓
    Top-K

    注意：
    全流程保留 Document 和 metadata，
    避免 PDF 页码等信息在检索过程中丢失。
    """

    def __init__(
        self,
        vectorstore,
        reranker_model="BAAI/bge-reranker-base"
    ):
        self.vectorstore = vectorstore

        print("[HybridRetriever] 正在加载 Reranker...")
        self.reranker = CrossEncoder(reranker_model)

        # 从向量库读取文档和 metadata
        data = vectorstore.get()

        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        self.all_docs = []

        for i, content in enumerate(documents):
            metadata = {}

            if i < len(metadatas) and metadatas[i]:
                metadata = metadatas[i]

            self.all_docs.append(
                Document(
                    page_content=content,
                    metadata=metadata
                )
            )

        # BM25 使用纯文本建立索引
        self.tokenized_corpus = [
            list(doc.page_content)
            for doc in self.all_docs
        ]

        self.bm25 = BM25Okapi(self.tokenized_corpus)

        print(
            f"[HybridRetriever] 文档数量：{len(self.all_docs)}"
        )

    def _bm25_search(self, query, top_k=20):
        """
        BM25 关键词检索。
        返回 Document，而不是字符串。
        """

        tokenized_query = list(query)

        scores = self.bm25.get_scores(tokenized_query)

        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        return [
            self.all_docs[i]
            for i in top_indices
        ]

    def _vector_search(self, query, top_k=20):
        """
        Vector 语义检索。
        LangChain 返回的 Document 会保留 metadata。
        """

        docs = self.vectorstore.similarity_search(
            query,
            k=top_k
        )
        for i, doc in enumerate(docs):
            print(f"\n--- 检索结果 {i + 1} ---")
            print("内容：", doc.page_content[:200])
            print("metadata：", doc.metadata)

        return docs

    @staticmethod
    def _doc_key(doc):
        """
        为 Document 创建稳定唯一 Key。

        加入 page 是为了避免：
        不同页出现完全相同文本时被错误合并。
        """

        page = doc.metadata.get("page", "unknown")

        return f"{page}::{doc.page_content}"

    def _rrf_fusion(
        self,
        bm25_results,
        vector_results,
        k=60
    ):
        """
        Reciprocal Rank Fusion。

        同时保留 Document 对象和 metadata。
        """

        rrf_scores = {}
        doc_map = {}

        for rank, doc in enumerate(bm25_results):

            key = self._doc_key(doc)

            rrf_scores[key] = (
                rrf_scores.get(key, 0)
                + 1 / (k + rank + 1)
            )

            doc_map[key] = doc

        for rank, doc in enumerate(vector_results):

            key = self._doc_key(doc)

            rrf_scores[key] = (
                rrf_scores.get(key, 0)
                + 1 / (k + rank + 1)
            )

            doc_map[key] = doc

        sorted_keys = sorted(
            rrf_scores,
            key=rrf_scores.get,
            reverse=True
        )

        return [
            doc_map[key]
            for key in sorted_keys
        ]

    def _rerank(
        self,
        query,
        candidates,
        top_k=5
    ):
        """
        CrossEncoder 精排。

        输入输出都保持 Document。
        """

        if not candidates:
            return []

        pairs = [
            [query, doc.page_content]
            for doc in candidates
        ]

        scores = self.reranker.predict(pairs)

        ranked = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            doc
            for doc, _ in ranked[:top_k]
        ]

    def retrieve(self, query, top_k=5):
        """
        完整 Hybrid Retrieval：

        BM25
          +
        Vector
          ↓
        RRF
          ↓
        Reranker
          ↓
        Top-K

        最终返回 Document 列表，
        保留 metadata。
        """

        bm25_results = self._bm25_search(
            query,
            top_k=20
        )

        vector_results = self._vector_search(
            query,
            top_k=20
        )

        fused = self._rrf_fusion(
            bm25_results,
            vector_results
        )

        final = self._rerank(
            query,
            fused[:20],
            top_k=top_k
        )

        return final