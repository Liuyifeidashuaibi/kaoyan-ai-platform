"""
向量存储抽象接口 — 定义统一 API，上层业务不依赖具体实现。

后期从 Chroma 切换 pgvector / Pinecone 仅需替换实现类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorDocument:
    """向量文档：文本 + 元数据 + 可选 ID。"""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str | None = None


@dataclass
class VectorQueryResult:
    """查询结果：单条匹配。"""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str = ""
    score: float = 0.0


class VectorStore(ABC):
    """向量存储抽象接口。"""

    @abstractmethod
    def add_documents(
        self,
        documents: list[VectorDocument],
        *,
        collection: str | None = None,
    ) -> int:
        """批量添加文档，返回成功入库数量。"""
        ...

    @abstractmethod
    def query(
        self,
        query_text: str,
        *,
        top_k: int = 5,
        collection: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[VectorQueryResult]:
        """相似度检索，返回 top_k 结果。"""
        ...

    @abstractmethod
    def delete_by_ids(
        self,
        doc_ids: list[str],
        *,
        collection: str | None = None,
    ) -> int:
        """按 ID 删除文档，返回删除数量。"""
        ...

    @abstractmethod
    def delete_by_metadata(
        self,
        where: dict[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        """按元数据条件删除文档，返回删除数量。"""
        ...

    @abstractmethod
    def count(
        self,
        *,
        collection: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> int:
        """统计文档数量。"""
        ...

    @abstractmethod
    def cleanup_expired(
        self,
        *,
        collection: str | None = None,
    ) -> int:
        """清理过期数据（如有 TTL 机制），返回清理数量。"""
        ...
