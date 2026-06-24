"""
永久考研知识库向量操作 — 官方真题、用户收藏的高质量题目。

仅可通过官方导入 / 用户收藏入库，禁止上传试卷自动批量入库。
"""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.vector.base import VectorDocument, VectorQueryResult
from app.infrastructure.vector.chroma_impl import (
    COLLECTION_KAOYAN_BANK,
    get_chroma_store,
)

logger = logging.getLogger(__name__)


class KaoyanBankStore:
    """永久考研知识库向量存储。"""

    def __init__(self) -> None:
        self._store = get_chroma_store()

    def add_question(
        self,
        *,
        stem: str,
        answer: str,
        analysis: str = "",
        key_points: str = "",
        subject: str = "",
        year: str = "",
        source: str = "",
        user_id: str = "",
    ) -> int:
        """
        单题入库永久知识库。

        :param stem: 题干
        :param answer: 答案
        :param analysis: 解析
        :param key_points: 考点
        :param subject: 科目 (english/math/politics/professional)
        :param year: 年份
        :param source: 来源 (official/user_favorite)
        :param user_id: 用户 ID（收藏时关联）
        """
        if not stem.strip():
            return 0

        # 拼接可检索文本
        parts = [f"【题干】{stem}"]
        if answer:
            parts.append(f"【答案】{answer}")
        if analysis:
            parts.append(f"【解析】{analysis}")
        if key_points:
            parts.append(f"【考点】{key_points}")
        text = "\n".join(parts)

        metadata: dict[str, Any] = {
            "subject": subject,
            "source": source or "official",
            "type": "kaoyan_question",
        }
        if year:
            metadata["year"] = year
        if user_id:
            metadata["user_id"] = user_id

        doc = VectorDocument(text=text, metadata=metadata)
        count = self._store.add_documents([doc], collection=COLLECTION_KAOYAN_BANK)
        logger.info("知识库入库: subject=%s, source=%s", subject, source)
        return count

    def batch_add_questions(
        self,
        questions: list[dict[str, Any]],
    ) -> int:
        """批量入库（官方导入时使用）。"""
        docs: list[VectorDocument] = []
        for q in questions:
            stem = q.get("stem", "")
            if not stem.strip():
                continue

            parts = [f"【题干】{stem}"]
            if q.get("answer"):
                parts.append(f"【答案】{q['answer']}")
            if q.get("analysis"):
                parts.append(f"【解析】{q['analysis']}")
            if q.get("key_points"):
                parts.append(f"【考点】{q['key_points']}")
            text = "\n".join(parts)

            metadata: dict[str, Any] = {
                "subject": q.get("subject", ""),
                "source": q.get("source", "official"),
                "type": "kaoyan_question",
            }
            if q.get("year"):
                metadata["year"] = q["year"]

            docs.append(VectorDocument(text=text, metadata=metadata))

        if docs:
            count = self._store.add_documents(docs, collection=COLLECTION_KAOYAN_BANK)
            logger.info("批量入库 %d 题", count)
            return count
        return 0

    def query(
        self,
        query_text: str,
        *,
        top_k: int = 5,
        subject: str | None = None,
    ) -> list[VectorQueryResult]:
        """检索知识库。"""
        where: dict[str, Any] | None = None
        if subject:
            where = {"subject": subject}

        return self._store.query(
            query_text,
            top_k=top_k,
            collection=COLLECTION_KAOYAN_BANK,
            where=where,
        )

    def search_context(
        self,
        query_text: str,
        *,
        subject: str | None = None,
        top_k: int = 3,
        max_chars: int = 2000,
    ) -> str:
        """
        检索知识库并格式化为 RAG 上下文字符串。

        :param query_text: 查询文本
        :param subject: 科目过滤（仅检索同科目内容）
        :param top_k: 返回结果数
        :param max_chars: 上下文最大字符数
        :return: 格式化的上下文字符串，若无结果返回空字符串
        """
        results = self.query(query_text, top_k=top_k, subject=subject)
        if not results:
            return ""

        parts: list[str] = []
        total_len = 0
        for r in results:
            # 截断单条结果避免过长
            snippet = r.text[:600] if len(r.text) > 600 else r.text
            meta_str = ""
            if r.metadata.get("year"):
                meta_str += f" [{r.metadata['year']}年]"
            if r.metadata.get("subject"):
                meta_str += f" [{r.metadata['subject']}]"
            entry = f"--- 相关题目{meta_str} (相关度: {r.score:.2f}) ---\n{snippet}"
            if total_len + len(entry) > max_chars:
                break
            parts.append(entry)
            total_len += len(entry)

        return "\n\n".join(parts) if parts else ""

    def count(self, subject: str | None = None) -> int:
        """统计知识库题目数量。"""
        where: dict[str, Any] | None = None
        if subject:
            where = {"subject": subject}
        return self._store.count(collection=COLLECTION_KAOYAN_BANK, where=where)

    def delete_by_user(self, user_id: str) -> int:
        """删除用户收藏的题目（用户取消收藏时）。"""
        return self._store.delete_by_metadata(
            {"user_id": user_id, "source": "user_favorite"},
            collection=COLLECTION_KAOYAN_BANK,
        )


# 全局单例
_kaoyan_bank_store: KaoyanBankStore | None = None


def get_kaoyan_bank_store() -> KaoyanBankStore:
    global _kaoyan_bank_store
    if _kaoyan_bank_store is None:
        _kaoyan_bank_store = KaoyanBankStore()
    return _kaoyan_bank_store
