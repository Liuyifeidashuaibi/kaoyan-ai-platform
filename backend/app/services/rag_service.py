"""
RAG 知识库服务 — 基于 LlamaIndex + Chroma 向量数据库。

- 公共知识库：data/public/ 下的 PDF、TXT、Markdown
- 私有知识库：用户错题本内容
- 检索优先级：用户错题 → 公共知识库
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
from llama_index.core import Document, Settings as LlamaSettings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings
from app.utils.text_utils import compress_rag_snippet

logger = logging.getLogger(__name__)

# Chroma 集合名称
COLLECTION_PUBLIC = "public_knowledge"
COLLECTION_PRIVATE = "private_wrong_questions"
COLLECTION_SCHOOL = "school_knowledge"


class RAGService:
    """RAG 检索与索引管理服务。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: chromadb.PersistentClient | None = None
        self._public_index: VectorStoreIndex | None = None
        self._private_index: VectorStoreIndex | None = None
        self._school_index: VectorStoreIndex | None = None
        self._embed_model: DashScopeEmbedding | None = None

    def _get_embed_model(self) -> DashScopeEmbedding:
        """懒加载百炼嵌入模型。"""
        if self._embed_model is None:
            self._embed_model = DashScopeEmbedding(
                model_name=self.settings.embedding_model,
                api_key=self.settings.dashscope_api_key,
            )
            LlamaSettings.embed_model = self._embed_model
        return self._embed_model

    def _get_chroma_client(self) -> chromadb.PersistentClient:
        """获取 Chroma 持久化客户端。"""
        if self._client is None:
            self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        return self._client

    def _build_index(self, collection_name: str) -> VectorStoreIndex:
        """从 Chroma 集合构建或加载 LlamaIndex 索引。"""
        self._get_embed_model()
        client = self._get_chroma_client()
        chroma_collection = client.get_or_create_collection(collection_name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )

    @property
    def public_index(self) -> VectorStoreIndex:
        if self._public_index is None:
            self._public_index = self._build_index(COLLECTION_PUBLIC)
        return self._public_index

    @property
    def private_index(self) -> VectorStoreIndex:
        if self._private_index is None:
            self._private_index = self._build_index(COLLECTION_PRIVATE)
        return self._private_index

    @property
    def school_index(self) -> VectorStoreIndex:
        if self._school_index is None:
            self._school_index = self._build_index(COLLECTION_SCHOOL)
        return self._school_index

    def _load_documents_from_dir(self, directory: Path) -> list[Document]:
        """
        扫描目录，加载 PDF / TXT / Markdown 文件为 LlamaIndex Document。
        """
        documents: list[Document] = []
        if not directory.exists():
            logger.warning("资料目录不存在: %s", directory)
            return documents

        extensions = {".pdf", ".txt", ".md", ".markdown"}
        for filepath in directory.rglob("*"):
            if filepath.suffix.lower() not in extensions or not filepath.is_file():
                continue
            try:
                text = self._read_file_text(filepath)
                if text.strip():
                    documents.append(
                        Document(
                            text=text,
                            metadata={
                                "source": str(filepath.relative_to(self.settings.root)),
                                "filename": filepath.name,
                                "type": "public",
                            },
                        )
                    )
            except Exception as exc:
                logger.error("读取文件失败 %s: %s", filepath, exc)
        return documents

    def _read_file_text(self, filepath: Path) -> str:
        """按扩展名读取文件纯文本。"""
        suffix = filepath.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(filepath))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        return filepath.read_text(encoding="utf-8", errors="ignore")

    def ingest_public_knowledge(self, force: bool = False) -> dict[str, Any]:
        """
        将 data/public/ 下所有资料向量化写入公共知识库。

        :param force: 为 True 时清空后重建索引
        """
        self._get_embed_model()
        data_dir = self.settings.public_data_path
        docs = self._load_documents_from_dir(data_dir)

        client = self._get_chroma_client()
        if force:
            try:
                client.delete_collection(COLLECTION_PUBLIC)
            except Exception:
                pass
            self._public_index = None

        if not docs:
            return {"ingested": 0, "message": "未找到可索引的文档"}

        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        nodes = splitter.get_nodes_from_documents(docs)

        chroma_collection = client.get_or_create_collection(COLLECTION_PUBLIC)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        VectorStoreIndex(nodes, storage_context=storage_context)
        self._public_index = None  # 下次使用时重新加载

        return {"ingested": len(nodes), "files": len(docs), "message": "公共知识库索引完成"}

    def ingest_wrong_question(
        self,
        question_id: int,
        title: str,
        notes: str,
        ai_analysis: str | None,
        category_name: str,
    ) -> None:
        """
        将单条错题内容写入私有向量库，供 RAG 优先检索。
        """
        self._get_embed_model()
        # 拼接可检索文本：标题 + 分类 + 笔记 + AI 解析
        parts = [f"【错题】{title}", f"科目：{category_name}"]
        if notes:
            parts.append(f"笔记：{notes}")
        if ai_analysis:
            parts.append(f"AI解析：{ai_analysis}")
        text = "\n".join(parts)

        doc = Document(
            text=text,
            metadata={
                "question_id": str(question_id),
                "category": category_name,
                "type": "private",
            },
        )
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        nodes = splitter.get_nodes_from_documents([doc])

        client = self._get_chroma_client()
        chroma_collection = client.get_or_create_collection(COLLECTION_PRIVATE)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        index.insert_nodes(nodes)
        self._private_index = None

    def retrieve(self, query: str, top_k: int | None = None) -> str:
        """
        混合检索：错题私有库 → 院校招生库 → 公共资料库。
        Top3~4，召回文本经短句压缩后拼接。
        """
        k = top_k or self.settings.rag_top_k
        max_snip = self.settings.rag_snippet_max_chars
        contexts: list[str] = []

        def _add(label: str, nodes: list) -> None:
            for node in nodes:
                snippet = compress_rag_snippet(node.get_content(), max_snip)
                if snippet:
                    contexts.append(f"[{label}] {snippet}")

        # 1. 用户错题
        try:
            nodes = self.private_index.as_retriever(similarity_top_k=k).retrieve(query)
            _add("用户错题", nodes)
        except Exception as exc:
            logger.warning("私有库检索失败: %s", exc)

        # 2. Supabase 同步的院校招生知识
        try:
            nodes = self.school_index.as_retriever(similarity_top_k=k).retrieve(query)
            _add("院校数据", nodes)
        except Exception as exc:
            logger.warning("院校库检索失败: %s", exc)

        # 3. 公共考研资料
        try:
            nodes = self.public_index.as_retriever(similarity_top_k=k).retrieve(query)
            for node in nodes:
                source = node.metadata.get("source", "未知")
                snippet = compress_rag_snippet(node.get_content(), max_snip)
                if snippet:
                    contexts.append(f"[公共资料-{source}] {snippet}")
        except Exception as exc:
            logger.warning("公共库检索失败: %s", exc)

        if not contexts:
            return ""
        return "\n\n".join(contexts[:k])


# 全局单例
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例。"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
