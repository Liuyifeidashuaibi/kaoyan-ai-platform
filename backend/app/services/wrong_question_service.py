"""
错题本业务服务 — 分类管理、错题 CRUD、AI 解析、向量化入库。
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import WrongQuestion, WrongQuestionCategory
from app.services.ai_service import get_ai_service
from app.services.rag_service import get_rag_service
from app.utils.file_utils import ensure_dir, save_upload_image


class WrongQuestionService:
    """错题本相关业务逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- 分类 ----------

    def create_category(self, name: str) -> WrongQuestionCategory:
        """创建科目分类（如「数学一」）。"""
        existing = self.db.query(WrongQuestionCategory).filter_by(name=name).first()
        if existing:
            return existing
        cat = WrongQuestionCategory(name=name.strip(), created_at=datetime.utcnow())
        self.db.add(cat)
        self.db.commit()
        self.db.refresh(cat)
        return cat

    def list_categories(self) -> list[dict]:
        """列出所有分类及错题数量。"""
        rows = (
            self.db.query(
                WrongQuestionCategory,
                func.count(WrongQuestion.id).label("question_count"),
            )
            .outerjoin(WrongQuestion)
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

    def get_or_create_category(self, name: str) -> WrongQuestionCategory:
        cat = self.db.query(WrongQuestionCategory).filter_by(name=name).first()
        if cat:
            return cat
        return self.create_category(name)

    # ---------- 错题 CRUD ----------

    def create_question(
        self,
        category_id: int,
        image_path: str,
        title: str = "未命名错题",
        notes: str = "",
    ) -> WrongQuestion:
        """创建错题记录。"""
        q = WrongQuestion(
            category_id=category_id,
            title=title,
            image_path=image_path,
            notes=notes,
            created_at=datetime.utcnow(),
        )
        self.db.add(q)
        self.db.commit()
        # 重新加载关联分类，供 RAG 同步使用
        q = self.get_question(q.id)  # type: ignore[arg-type]
        if q:
            self._sync_to_rag(q)
        return q  # type: ignore[return-value]

    def list_questions(self, category_id: int | None = None) -> list[dict]:
        """按分类筛选错题列表（移动端友好：缩略图 + 标题）。"""
        q = self.db.query(WrongQuestion).join(WrongQuestionCategory)
        if category_id is not None:
            q = q.filter(WrongQuestion.category_id == category_id)
        questions = q.order_by(WrongQuestion.created_at.desc()).all()
        return [self._to_dict(item) for item in questions]

    def get_question(self, question_id: int) -> WrongQuestion | None:
        return (
            self.db.query(WrongQuestion)
            .options(joinedload(WrongQuestion.category))
            .filter_by(id=question_id)
            .first()
        )

    def update_question(
        self,
        question_id: int,
        title: str | None = None,
        notes: str | None = None,
        category_id: int | None = None,
    ) -> WrongQuestion | None:
        q = self.get_question(question_id)
        if not q:
            return None
        if title is not None:
            q.title = title
        if notes is not None:
            q.notes = notes
        if category_id is not None:
            q.category_id = category_id
        self.db.commit()
        self.db.refresh(q)
        self._sync_to_rag(q)
        return q

    def delete_question(self, question_id: int) -> bool:
        q = self.get_question(question_id)
        if not q:
            return False
        self.db.delete(q)
        self.db.commit()
        return True

    async def analyze_question(self, question_id: int) -> str | None:
        """使用 VL + LLM 对错题图片进行 AI 解析。"""
        q = self.get_question(question_id)
        if not q:
            return None

        ai = get_ai_service()
        prompt = (
            f"这是「{q.category.name}」科目的一道错题。"
            "请识别图片中的题目，给出详细的分步骤解析和解题思路。"
            "如果是数学题，请写出完整推导过程。"
        )
        analysis = await ai.analyze_image(q.image_path, prompt)

        q.ai_analysis = analysis
        self.db.commit()
        self._sync_to_rag(q)
        return analysis

    def save_image(self, content: bytes, filename: str, upload_dir) -> str:
        """保存上传的错题图片。"""
        ensure_dir(upload_dir)
        return save_upload_image(
            content, upload_dir, filename, project_root=get_settings().root
        )

    def _sync_to_rag(self, q: WrongQuestion) -> None:
        """将错题内容同步到私有向量知识库。"""
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
            pass  # 向量化失败不阻断主流程

    def _to_dict(self, q: WrongQuestion) -> dict:
        return {
            "id": q.id,
            "category_id": q.category_id,
            "category_name": q.category.name if q.category else "",
            "title": q.title,
            "image_path": q.image_path,
            "notes": q.notes or "",
            "ai_analysis": q.ai_analysis,
            "created_at": q.created_at,
        }
