"""
临时试卷向量操作 — 绑定 session_id，支持按会话批量删除、TTL 自动过期。
"""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.vector.base import VectorDocument, VectorQueryResult
from app.infrastructure.vector.chroma_impl import (
    COLLECTION_TEMP_PAPER,
    get_chroma_store,
)

logger = logging.getLogger(__name__)


class TempPaperStore:
    """临时试卷向量存储 — 与聊天会话 session_id 一一绑定。"""

    def __init__(self) -> None:
        self._store = get_chroma_store()

    def ingest_paper_segments(
        self,
        segments: list[str],
        *,
        session_id: str,
        paper_id: int,
        subject: str = "",
        extra_metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        将试卷文本片段入库临时集合。

        :param segments: 文本片段列表（按题号/段落顺序）
        :param session_id: 关联的聊天会话 ID
        :param paper_id: ExamPaper 数据库 ID
        :param subject: 科目 english/math
        :param extra_metadata: 附加元数据
        """
        if not segments:
            return 0

        docs: list[VectorDocument] = []
        for idx, text in enumerate(segments):
            if not text.strip():
                continue
            meta: dict[str, Any] = {
                "session_id": session_id,
                "paper_id": str(paper_id),
                "subject": subject,
                "segment_index": idx,
            }
            if extra_metadata:
                meta.update(extra_metadata)
            docs.append(VectorDocument(
                text=text,
                metadata=meta,
            ))

        count = self._store.add_documents(docs, collection=COLLECTION_TEMP_PAPER)
        logger.info(
            "临时试卷入库: session=%s paper=%d, %d 段 → %d 向量",
            session_id, paper_id, len(segments), count,
        )
        return count

    def query_by_session(
        self,
        query_text: str,
        *,
        session_id: str,
        top_k: int = 5,
    ) -> list[VectorQueryResult]:
        """在指定会话的临时向量中检索。"""
        return self._store.query(
            query_text,
            top_k=top_k,
            collection=COLLECTION_TEMP_PAPER,
            where={"session_id": session_id},
        )

    def delete_by_session(self, session_id: str) -> int:
        """按 session_id 批量删除临时向量（用户删除聊天记录时调用）。"""
        count = self._store.delete_by_metadata(
            {"session_id": session_id},
            collection=COLLECTION_TEMP_PAPER,
        )
        logger.info("清理会话 %s 的临时向量: %d 个", session_id, count)
        return count

    def delete_by_paper(self, paper_id: int) -> int:
        """按 paper_id 删除临时向量。"""
        return self._store.delete_by_metadata(
            {"paper_id": str(paper_id)},
            collection=COLLECTION_TEMP_PAPER,
        )

    def cleanup_expired(self) -> int:
        """清理超过 TTL 的过期临时向量。"""
        return self._store.cleanup_expired(collection=COLLECTION_TEMP_PAPER)

    def count_by_session(self, session_id: str) -> int:
        """统计指定会话的临时向量数量。"""
        return self._store.count(
            collection=COLLECTION_TEMP_PAPER,
            where={"session_id": session_id},
        )


# 全局单例
_temp_paper_store: TempPaperStore | None = None


def get_temp_paper_store() -> TempPaperStore:
    global _temp_paper_store
    if _temp_paper_store is None:
        _temp_paper_store = TempPaperStore()
    return _temp_paper_store
