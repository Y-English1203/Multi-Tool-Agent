import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder


class HybridRetriever:
    """混合检索器：BM25 关键词召回 + 向量语义召回 + RRF 融合 + Reranker 精排"""

    def __init__(self, vectorstore, reranker_model="BAAI/bge-reranker-base"):
        self.vectorstore = vectorstore
        self.reranker = CrossEncoder(reranker_model)
        # 从向量库取出所有文档，用于构建 BM25 索引
        data = vectorstore.get()
        self.all_docs = data["documents"]
        self.tokenized_corpus = [list(doc) for doc in self.all_docs]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _bm25_search(self, query, top_k=20):
        """关键词检索（BM25）"""
        tokenized_query = list(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.all_docs[i] for i in top_indices]

    def _vector_search(self, query, top_k=20):
        """向量语义检索"""
        docs = self.vectorstore.similarity_search(query, k=top_k)
        return [doc.page_content for doc in docs]

    def _rrf_fusion(self, bm25_results, vector_results, k=60):
        """RRF（Reciprocal Rank Fusion）融合两路召回结果"""
        rrf_scores = {}
        for rank, doc in enumerate(bm25_results):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)
        for rank, doc in enumerate(vector_results):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in sorted_docs]

    def _rerank(self, query, candidates, top_k=5):
        """Reranker 精排：用交叉编码器对候选文档重新打分"""
        pairs = [[query, doc] for doc in candidates]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:top_k]]

    def retrieve(self, query, top_k=5):
        """完整流程：BM25 + 向量 → RRF融合 → Reranker精排 → Top-K"""
        bm25_results = self._bm25_search(query, top_k=20)
        vector_results = self._vector_search(query, top_k=20)
        fused = self._rrf_fusion(bm25_results, vector_results)
        final = self._rerank(query, fused[:20], top_k=top_k)
        return final