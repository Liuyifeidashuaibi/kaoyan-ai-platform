"""
Chroma 向量存储实现 — 复用现有 RAGService 的 Chroma 客户端和 DashScope embedding。

新增两个集合:
- temp_paper: 临时试卷向量（绑定 session_id，支持 TTL）
- kaoyan_bank: 永久考研知识库
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import chromadb
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.core.node_parser import SentenceSplitter

from app.config import get_settings
from app.infrastructure.vector.base import VectorStore, VectorDocument, VectorQueryResult

logger = logging.getLogger(__name__)

# 集合名称常量
COLLECTION_TEMP_PAPER = "temp_paper"
COLLECTION_KAOYAN_BANK = "kaoyan_bank"


class ChromaVectorStore(VectorStore):
    """基于 Chroma + DashScope Embedding 的向量存储实现。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: chromadb.PersistentClient | None = None
        self._embed_model: DashScopeEmbedding | None = None

    def _get_embed_model(self) -> DashScopeEmbedding:
        if self._embed_model is None:
            self._embed_model = DashScopeEmbedding(
                model_name=self.settings.embedding_model,
                api_key=self.settings.dashscope_api_key,
            )
            LlamaSettings.embed_model = self._embed_model
        return self._embed_model

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        return self._client

    def _get_collection(self, name: str | None = None) -> chromadb.Collection:
        collection_name = name or COLLECTION_TEMP_PAPER
        client = self._get_client()
        return client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """使用 DashScope 生成文本向量。"""
        model = self._get_embed_model()
        # LlamaIndex DashScopeEmbedding 的 get_text_embedding_batch
        embeddings = model.get_text_embedding_batch(texts)
        return embeddings

    def add_documents(
        self,
        documents: list[VectorDocument],
        *,
        collection: str | None = None,
    ) -> int:
        if not documents:
            return 0

        chroma_col = self._get_collection(collection)
        texts = [doc.text for doc in documents if doc.text.strip()]
        if not texts:
            return 0

        # 分片（长文本切分为更小单元）
        splitter = SentenceSplitter(
            chunk_size=self.settings.vector_chunk_size,
            chunk_overlap=self.settings.vector_chunk_overlap,
        )

        ids: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict] = []
        stored_texts: list[str] = []

        for doc in documents:
            if not doc.text.strip():
                continue
            # 生成分片
            from llama_index.core import Document as LlamaDoc
            nodes = splitter.get_nodes_from_documents(
                [LlamaDoc(text=doc.text, metadata=doc.metadata)]
            )
            for node in nodes:
                doc_id = doc.doc_id or str(uuid.uuid4())
                ids.append(f"{doc_id}_{len(ids)}")
                stored_texts.append(node.get_content())
                meta = dict(doc.metadata)
                meta["_created_ts"] = int(time.time())
                metadatas.append(meta)

        # 批量生成 embedding
        if stored_texts:
            embeddings = self._get_embeddings(stored_texts)

        # 写入 Chroma
        if ids and embeddings:
            chroma_col.add(
                ids=ids,
                embeddings=embeddings,
                documents=stored_texts,
                metadatas=metadatas,
            )
            logger.info(
                "入库 %d 个向量到集合 %s",
                len(ids), collection or COLLECTION_TEMP_PAPER,
            )
        return len(ids)

    def query(
        self,
        query_text: str,
        *,
        top_k: int = 5,
        collection: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[VectorQueryResult]:
        if not query_text.strip():
            return []

        chroma_col = self._get_collection(collection)
        query_embedding = self._get_embeddings([query_text])[0]

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if where:
            query_kwargs["where"] = where

        results = chroma_col.query(**query_kwargs)
        output: list[VectorQueryResult] = []

        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            doc_ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

            for text, meta, dist, did in zip(docs, metas, distances, doc_ids):
                # Chroma cosine distance: 越小越相似，转换为 similarity score
                score = 1.0 - dist if dist <= 1.0 else 0.0
                output.append(VectorQueryResult(
                    text=text,
                    metadata=meta,
                    doc_id=did,
                    score=score,
                ))

        return output

    def delete_by_ids(
        self,
        doc_ids: list[str],
        *,
        collection: str | None = None,
    ) -> int:
        if not doc_ids:
            return 0
        chroma_col = self._get_collection(collection)
        try:
            chroma_col.delete(ids=doc_ids)
            return len(doc_ids)
        except Exception as exc:
            logger.warning("删除向量失败: %s", exc)
            return 0

    def delete_by_metadata(
        self,
        where: dict[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        chroma_col = self._get_collection(collection)
        try:
            # 先查出匹配的 IDs
            results = chroma_col.get(where=where)
            if results and results["ids"]:
                count = len(results["ids"])
                chroma_col.delete(ids=results["ids"])
                logger.info("按元数据删除 %d 个向量: %s", count, where)
                return count
        except Exception as exc:
            logger.warning("按元数据删除失败: %s", exc)
        return 0

    def count(
        self,
        *,
        collection: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> int:
        chroma_col = self._get_collection(collection)
        if where:
            results = chroma_col.get(where=where)
            return len(results["ids"]) if results and results.get("ids") else 0
        return chroma_col.count()

    def cleanup_expired(
        self,
        *,
        collection: str | None = None,
    ) -> int:
        """清理超过 TTL 的临时试卷向量。"""
        from datetime import datetime, timedelta

        col_name = collection or COLLECTION_TEMP_PAPER
        if col_name != COLLECTION_TEMP_PAPER:
            return 0

        settings = get_settings()
        cutoff_ts = int(
            (datetime.utcnow() - timedelta(days=settings.exam_temp_ttl_days)).timestamp()
        )

        chroma_col = self._get_collection(col_name)
        try:
            # 查找过期文档
            results = chroma_col.get(where={"_created_ts": {"$lt": cutoff_ts}})
            if results and results["ids"]:
                count = len(results["ids"])
                chroma_col.delete(ids=results["ids"])
                logger.info("清理过期临时向量 %d 个", count)
                return count
        except Exception as exc:
            logger.warning("清理过期向量失败: %s", exc)
        return 0


# 全局单例
_chroma_store: ChromaVectorStore | None = None


def get_chroma_store() -> ChromaVectorStore:
    global _chroma_store
    if _chroma_store is None:
        _chroma_store = ChromaVectorStore()
    return _chroma_store
