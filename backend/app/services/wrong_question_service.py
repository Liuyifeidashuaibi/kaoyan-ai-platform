"""
错题本业务服务 — 分类管理、学习资料 CRUD、AI 解析、向量化入库。
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import urlopen

from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import WrongQuestion, WrongQuestionCategory
from app.services.ai_service import get_ai_service
from app.services.rag_service import get_rag_service
from app.utils.auth import DEV_USER_ID
from app.utils.file_utils import (
    detect_file_type,
    ensure_dir,
    save_upload_file,
    save_upload_image,
)

logger = logging.getLogger(__name__)

COMMUNITY_FAVORITES_CATEGORY = "我的收藏"


def community_post_marker(post_id: str) -> str:
    return f"[community_post:{post_id}]"


class WrongQuestionService:
    """错题本 / 学习资料相关业务逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def claim_legacy_data(self, user_id: str) -> None:
        """
        将升级前归属 dev/空 user_id 的历史数据认领给当前用户。
        仅在当前用户尚无资料、且存在未认领历史数据时执行一次。
        """
        if user_id == DEV_USER_ID:
            return

        own_count = (
            self.db.query(WrongQuestion).filter(WrongQuestion.user_id == user_id).count()
        )
        if own_count > 0:
            return

        legacy_filter = (WrongQuestion.user_id == DEV_USER_ID) | (
            WrongQuestion.user_id.is_(None)
        )
        legacy_count = self.db.query(WrongQuestion).filter(legacy_filter).count()
        if legacy_count > 0:
            self.db.query(WrongQuestion).filter(legacy_filter).update(
                {WrongQuestion.user_id: user_id},
                synchronize_session=False,
            )
            cat_legacy_filter = (WrongQuestionCategory.user_id == DEV_USER_ID) | (
                WrongQuestionCategory.user_id.is_(None)
            )
            self.db.query(WrongQuestionCategory).filter(cat_legacy_filter).update(
                {WrongQuestionCategory.user_id: user_id},
                synchronize_session=False,
            )
            self.db.commit()
            logger.info(
                "已将 %s 条历史错题本数据认领至 user_id=%s", legacy_count, user_id
            )
            return

        # 本地单用户库：全部资料仅归属另一账号时，由当前登录用户接管
        other_owners = [
            row[0]
            for row in self.db.query(WrongQuestion.user_id).distinct().all()
            if row[0] and row[0] not in (user_id, DEV_USER_ID)
        ]
        if len(other_owners) == 1:
            other_id = other_owners[0]
            moved = (
                self.db.query(WrongQuestion)
                .filter(WrongQuestion.user_id == other_id)
                .count()
            )
            if moved > 0:
                self.db.query(WrongQuestion).filter(
                    WrongQuestion.user_id == other_id
                ).update(
                    {WrongQuestion.user_id: user_id},
                    synchronize_session=False,
                )
                self.db.query(WrongQuestionCategory).filter(
                    WrongQuestionCategory.user_id == other_id
                ).update(
                    {WrongQuestionCategory.user_id: user_id},
                    synchronize_session=False,
                )
                self.db.commit()
                logger.info(
                    "已将 user_id=%s 的 %s 条错题本数据认领至 user_id=%s",
                    other_id,
                    moved,
                    user_id,
                )

    # ---------- 分类 ----------

    def create_category(self, name: str, user_id: str) -> WrongQuestionCategory:
        """创建科目分类（如「数学一」），按用户隔离。"""
        existing = (
            self.db.query(WrongQuestionCategory)
            .filter_by(name=name.strip(), user_id=user_id)
            .first()
        )
        if existing:
            return existing
        cat = WrongQuestionCategory(
            name=name.strip(),
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(cat)
        self.db.commit()
        self.db.refresh(cat)
        return cat

    def list_categories(self, user_id: str) -> list[dict]:
        """列出当前用户的分类及资料数量。"""
        self.claim_legacy_data(user_id)
        rows = (
            self.db.query(
                WrongQuestionCategory,
                func.count(WrongQuestion.id).label("question_count"),
            )
            .outerjoin(
                WrongQuestion,
                (WrongQuestion.category_id == WrongQuestionCategory.id)
                & (WrongQuestion.user_id == user_id),
            )
            .filter(WrongQuestionCategory.user_id == user_id)
            .group_by(WrongQuestionCategory.id)
            .order_by(WrongQuestionCategory.created_at.asc())
            .all()
        )
        return [
            {
                "id": cat.id,
                "name": cat.name,
                "created_at": cat.created_at,
                "question_count": count,
            }
            for cat, count in rows
        ]

    def get_or_create_category(self, name: str, user_id: str) -> WrongQuestionCategory:
        cat = (
            self.db.query(WrongQuestionCategory)
            .filter_by(name=name, user_id=user_id)
            .first()
        )
        if cat:
            return cat
        return self.create_category(name, user_id)

    def _get_user_category(self, category_id: int, user_id: str) -> WrongQuestionCategory | None:
        return (
            self.db.query(WrongQuestionCategory)
            .filter_by(id=category_id, user_id=user_id)
            .first()
        )

    # ---------- 资料 CRUD ----------

    def create_question(
        self,
        category_id: int,
        file_path: str,
        file_type: str,
        user_id: str,
        title: str = "未命名资料",
        notes: str = "",
        original_filename: str | None = None,
        is_public: bool = False,
    ) -> WrongQuestion:
        """创建学习资料记录。"""
        q = WrongQuestion(
            category_id=category_id,
            user_id=user_id,
            is_public=is_public,
            title=title,
            image_path=file_path,
            file_path=file_path,
            file_type=file_type,
            original_filename=original_filename,
            notes=notes,
            created_at=datetime.utcnow(),
        )
        self.db.add(q)
        self.db.commit()
        q = self.get_question(q.id, user_id=user_id)  # type: ignore[arg-type]
        if q:
            self._sync_to_rag(q)
        return q  # type: ignore[return-value]

    def list_questions(
        self,
        user_id: str,
        category_id: int | None = None,
        file_type: str | None = None,
    ) -> list[dict]:
        """按用户与分类筛选资料列表。"""
        self.claim_legacy_data(user_id)
        q = (
            self.db.query(WrongQuestion)
            .join(WrongQuestionCategory)
            .filter(WrongQuestion.user_id == user_id)
            .filter(WrongQuestionCategory.user_id == user_id)
        )
        if category_id is not None:
            q = q.filter(WrongQuestion.category_id == category_id)
        if file_type:
            q = q.filter(WrongQuestion.file_type == file_type)
        questions = q.order_by(WrongQuestion.created_at.asc()).all()
        return [self._to_dict(item) for item in questions]

    def list_public_questions(self, owner_user_id: str) -> list[dict]:
        """列出某用户公开的资料（供个人主页展示）。"""
        questions = (
            self.db.query(WrongQuestion)
            .join(WrongQuestionCategory)
            .filter(WrongQuestion.user_id == owner_user_id)
            .filter(WrongQuestion.is_public.is_(True))
            .order_by(WrongQuestion.created_at.desc())
            .all()
        )
        return [self._to_dict(item) for item in questions]

    def get_question(
        self,
        question_id: int,
        *,
        user_id: str | None = None,
        allow_public: bool = False,
    ) -> WrongQuestion | None:
        q = (
            self.db.query(WrongQuestion)
            .options(joinedload(WrongQuestion.category))
            .filter_by(id=question_id)
            .first()
        )
        if not q:
            return None
        if user_id and q.user_id == user_id:
            return q
        if allow_public and q.is_public:
            return q
        return None

    def update_question(
        self,
        question_id: int,
        user_id: str,
        title: str | None = None,
        notes: str | None = None,
        category_id: int | None = None,
        is_public: bool | None = None,
    ) -> WrongQuestion | None:
        q = self.get_question(question_id, user_id=user_id)
        if not q:
            return None
        if title is not None:
            q.title = title
        if notes is not None:
            q.notes = notes
        if is_public is not None:
            q.is_public = is_public
        if category_id is not None:
            cat = self._get_user_category(category_id, user_id)
            if not cat:
                return None
            q.category_id = category_id
        self.db.commit()
        self.db.refresh(q)
        self._sync_to_rag(q)
        return q

    def delete_question(self, question_id: int, user_id: str) -> bool:
        q = self.get_question(question_id, user_id=user_id)
        if not q:
            return False
        self.db.delete(q)
        self.db.commit()
        return True

    async def analyze_question(self, question_id: int, user_id: str) -> str | None:
        """使用 VL + LLM 对图片资料进行 AI 解析。"""
        q = self.get_question(question_id, user_id=user_id)
        if not q:
            return None

        file_type = q.file_type or detect_file_type(q.file_path or q.image_path)
        if file_type != "image":
            return None

        ai = get_ai_service()
        prompt = (
            f"这是「{q.category.name}」科目的一道错题。"
            "请识别图片中的题目，给出详细的分步骤解析和解题思路。"
            "如果是数学题，请写出完整推导过程。"
        )
        analysis = await ai.analyze_image(q.file_path or q.image_path, prompt)

        q.ai_analysis = analysis
        self.db.commit()
        self._sync_to_rag(q)
        return analysis

    def save_file(self, content: bytes, filename: str, upload_dir) -> tuple[str, str]:
        """保存上传的学习资料，返回 (相对路径, 文件类型)。"""
        ensure_dir(upload_dir)
        file_type = detect_file_type(filename)
        if file_type == "image":
            path = save_upload_image(
                content, upload_dir, filename, project_root=get_settings().root
            )
        else:
            path = save_upload_file(
                content, upload_dir, filename, project_root=get_settings().root
            )
        return path, file_type

    @staticmethod
    def _pick_attachment(attachments: list[dict] | None) -> dict | None:
        if not attachments:
            return None
        for att in attachments:
            mime = (att.get("mime_type") or "").lower()
            name = (att.get("name") or "").lower()
            if mime.startswith("image/") or re.search(
                r"\.(jpe?g|png|gif|webp|bmp)$", name
            ):
                return att
        return attachments[0]

    @staticmethod
    def _download_bytes(url: str) -> bytes | None:
        try:
            import httpx

            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except Exception:
            try:
                with urlopen(url, timeout=30) as resp:
                    return resp.read()
            except Exception:
                logger.warning("下载社区附件失败: %s", url, exc_info=True)
                return None

    def find_community_favorite(self, post_id: str, user_id: str) -> WrongQuestion | None:
        cat = self.get_or_create_category(COMMUNITY_FAVORITES_CATEGORY, user_id)
        marker = community_post_marker(post_id)
        return (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.category_id == cat.id)
            .filter(WrongQuestion.user_id == user_id)
            .filter(WrongQuestion.notes.contains(marker))
            .first()
        )

    def create_from_community_post(
        self,
        *,
        user_id: str,
        post_id: str,
        title: str,
        notes: str,
        attachments: list[dict] | None = None,
        attachment_url: str | None = None,
        attachment_name: str | None = None,
    ) -> WrongQuestion:
        """将社区帖子加入错题本；同一用户同一帖子只保留一条。"""
        existing = self.find_community_favorite(post_id, user_id)
        if existing:
            return existing

        cat = self.get_or_create_category(COMMUNITY_FAVORITES_CATEGORY, user_id)
        upload_dir = get_settings().upload_path
        full_notes = f"{community_post_marker(post_id)}\n\n{notes}"

        picked = self._pick_attachment(attachments)
        url = attachment_url or (picked.get("url") if picked else None)
        name = attachment_name or (picked.get("name") if picked else None)

        file_path = ""
        file_type = "document"
        original_filename = name
        content_bytes = self._download_bytes(url) if url else None

        try:
            if content_bytes:
                parsed = urlparse(url or "")
                filename = name or parsed.path.rsplit("/", 1)[-1] or "community_file"
                file_path, file_type = self.save_file(content_bytes, filename, upload_dir)
                original_filename = filename
            else:
                filename = f"收藏_{post_id[:8]}.txt"
                file_path, file_type = self.save_file(
                    full_notes.encode("utf-8"),
                    filename,
                    upload_dir,
                )
                original_filename = filename
        except Exception:
            logger.exception("保存收藏文件失败，回退为文本 post_id=%s", post_id)
            filename = f"收藏_{post_id[:8]}.txt"
            file_path, file_type = self.save_file(
                full_notes.encode("utf-8"),
                filename,
                upload_dir,
            )
            original_filename = filename

        return self.create_question(
            category_id=cat.id,
            file_path=file_path,
            file_type=file_type,
            user_id=user_id,
            title=title[:200] or "社区帖子",
            notes=full_notes,
            original_filename=original_filename,
        )

    def sync_community_favorites(
        self, posts: list[dict], user_id: str
    ) -> dict[str, int]:
        """将多条社区帖子同步到「我的收藏」，已存在则跳过。"""
        created = 0
        skipped = 0
        for post in posts:
            post_id = str(post.get("id") or "")
            if not post_id:
                continue
            if self.find_community_favorite(post_id, user_id):
                skipped += 1
                continue
            title = post.get("title") or "社区帖子"
            content = post.get("content") or ""
            notes = "\n\n".join(
                part
                for part in (
                    title,
                    content,
                    f"— 来自社区帖子《{title}》",
                )
                if part
            )
            self.create_from_community_post(
                user_id=user_id,
                post_id=post_id,
                title=title,
                notes=notes,
                attachments=post.get("attachments") or [],
            )
            created += 1
        return {"created": created, "skipped": skipped, "total": len(posts)}

    def _sync_to_rag(self, q: WrongQuestion) -> None:
        """将资料内容同步到私有向量知识库。"""
        try:
            rag = get_rag_service()
            rag.ingest_wrong_question(
                question_id=q.id,
                title=q.title,
                notes=q.notes or "",
                ai_analysis=q.ai_analysis,
                category_name=q.category.name if q.category else "未分类",
            )
        except Exception:
            pass

    def _resolve_file_path(self, q: WrongQuestion) -> str:
        return q.file_path or q.image_path

    def _to_dict(self, q: WrongQuestion) -> dict:
        file_path = self._resolve_file_path(q)
        file_type = q.file_type or detect_file_type(file_path)
        return {
            "id": q.id,
            "category_id": q.category_id,
            "category_name": q.category.name if q.category else "",
            "title": q.title,
            "image_path": file_path,
            "file_path": file_path,
            "file_type": file_type,
            "original_filename": q.original_filename,
            "notes": q.notes or "",
            "ai_analysis": q.ai_analysis,
            "is_public": bool(q.is_public),
            "created_at": q.created_at,
        }
