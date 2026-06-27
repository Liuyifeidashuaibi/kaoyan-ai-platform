"""
RAG 知识库服务 — 基于 LlamaIndex + Chroma 向量数据库。

- 公共知识库：data/public/ 下的 PDF、TXT、Markdown
- 私有知识库：用户错题本内容
- 检索优先级：用户错题 → 公共知识库
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
COLLECTION_TEMPLATES = "agent_templates"  # 文档/行业模板向量库（格式强约束）


class RAGService:
    """RAG 检索与索引管理服务。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: chromadb.PersistentClient | None = None
        self._public_index: VectorStoreIndex | None = None
        self._private_index: VectorStoreIndex | None = None
        self._school_index: VectorStoreIndex | None = None
        self._templates_index: VectorStoreIndex | None = None
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

    @property
    def templates_index(self) -> VectorStoreIndex:
        """模板向量索引（懒加载）。"""
        if self._templates_index is None:
            self._templates_index = self._build_index(COLLECTION_TEMPLATES)
        return self._templates_index

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
        混合检索：错题私有库 → 院校招生库 → 公共资料库（三路并行）。
        Top3~4，召回文本经短句压缩后拼接。
        """
        k = top_k or self.settings.rag_top_k
        max_snip = self.settings.rag_snippet_max_chars
        contexts: list[str] = []

        def _retrieve_private() -> list[str]:
            out: list[str] = []
            try:
                nodes = self.private_index.as_retriever(similarity_top_k=k).retrieve(query)
                for node in nodes:
                    snippet = compress_rag_snippet(node.get_content(), max_snip)
                    if snippet:
                        out.append(f"[用户错题] {snippet}")
            except Exception as exc:
                logger.warning("私有库检索失败: %s", exc)
            return out

        def _retrieve_school() -> list[str]:
            out: list[str] = []
            try:
                nodes = self.school_index.as_retriever(similarity_top_k=k).retrieve(query)
                for node in nodes:
                    snippet = compress_rag_snippet(node.get_content(), max_snip)
                    if snippet:
                        out.append(f"[院校数据] {snippet}")
            except Exception as exc:
                logger.warning("院校库检索失败: %s", exc)
            return out

        def _retrieve_public() -> list[str]:
            out: list[str] = []
            try:
                nodes = self.public_index.as_retriever(similarity_top_k=k).retrieve(query)
                for node in nodes:
                    source = node.metadata.get("source", "未知")
                    snippet = compress_rag_snippet(node.get_content(), max_snip)
                    if snippet:
                        out.append(f"[公共资料-{source}] {snippet}")
            except Exception as exc:
                logger.warning("公共库检索失败: %s", exc)
            return out

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(_retrieve_private),
                pool.submit(_retrieve_school),
                pool.submit(_retrieve_public),
            ]
            for future in as_completed(futures):
                contexts.extend(future.result())

        if not contexts:
            return ""
        return "\n\n".join(contexts[:k])

    # ── 模板知识库 ────────────────────────────────────────

    def ingest_template(
        self,
        template_id: int,
        name: str,
        category: str,
        doc_type: str,
        style_rules: str,
        validation_rules: str,
        source_text: str = "",
    ) -> None:
        """
        将文档/行业模板向量化写入模板库，供 Agent 导出前检索。

        模板检索结果会打 kind="template" 元数据标记，与参考资料区分。
        """
        self._get_embed_model()

        # 拼接可检索文本：名称 + 分类 + 文档类型 + 样式规则 + 校验规则 + 源文本
        parts = [f"【模板】{name}", f"分类：{category}", f"文档类型：{doc_type}"]
        if style_rules:
            parts.append(f"样式规则：{style_rules}")
        if validation_rules:
            parts.append(f"校验规则：{validation_rules}")
        if source_text:
            parts.append(f"模板原文：{source_text[:3000]}")
        text = "\n".join(parts)

        doc = Document(
            text=text,
            metadata={
                "template_id": str(template_id),
                "name": name,
                "category": category,
                "doc_type": doc_type,
                "kind": "template",
            },
        )
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        nodes = splitter.get_nodes_from_documents([doc])

        client = self._get_chroma_client()
        chroma_collection = client.get_or_create_collection(COLLECTION_TEMPLATES)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        index.insert_nodes(nodes)
        self._templates_index = None  # 下次使用时重新加载

    def retrieve_templates(
        self,
        query: str,
        doc_type: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        语义检索匹配模板 — 按文档类型+查询关键词召回。

        返回模板列表，每项含 name/category/doc_type/style_rules/validation_rules 等字段。
        结果打 kind="template" 标记，与参考资料检索结果区分。
        """
        try:
            nodes = self.templates_index.as_retriever(
                similarity_top_k=top_k,
            ).retrieve(query)
        except Exception as exc:
            logger.warning("模板库检索失败: %s", exc)
            return []

        results: list[dict[str, Any]] = []
        for node in nodes:
            meta = node.metadata or {}
            # 过滤：如果指定了 doc_type，只返回匹配的
            if doc_type and meta.get("doc_type", "") and meta["doc_type"] != doc_type:
                continue
            snippet = compress_rag_snippet(node.get_content(), self.settings.rag_snippet_max_chars)
            results.append({
                "template_id": meta.get("template_id", ""),
                "name": meta.get("name", ""),
                "category": meta.get("category", ""),
                "doc_type": meta.get("doc_type", ""),
                "kind": "template",
                "snippet": snippet,
            })
        return results


# 全局单例
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例。"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
