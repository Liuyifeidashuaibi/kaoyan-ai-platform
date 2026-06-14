"""
社区路由 — 帖子、评论、关注、收藏、搜索。
"""

import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.community import CommentCreate, PostCreate, PostUpdate, UserProfileUpdate
from app.services.community_service import get_community_service
from app.services.wrong_question_service import WrongQuestionService
from app.utils.auth import optional_user_id, require_user_id
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/community", tags=["社区"])
logger = logging.getLogger(__name__)

FAVORITES_WQ_CATEGORY = "我的收藏"


def _post_notes_for_wrong_questions(post: dict) -> str:
    lines = [post.get("title") or "", post.get("content") or ""]
    lines.append(f"— 来自社区帖子《{post.get('title', '')}》")
    return "\n\n".join(line for line in lines if line)


def _sync_post_to_wrong_questions(db: Session, post: dict, user_id: str):
    wq_service = WrongQuestionService(db)
    post_id = str(post.get("id") or "")
    if not post_id:
        raise ValueError("帖子 ID 无效")
    return wq_service.create_from_community_post(
        user_id=user_id,
        post_id=post_id,
        title=post.get("title") or "社区帖子",
        notes=_post_notes_for_wrong_questions(post),
        attachments=post.get("attachments") or [],
    )


def _svc():
    return get_community_service()


# ==================== 帖子 ====================


@router.get("/posts")
async def list_posts(
    sort: str = Query(default="latest", pattern="^(latest|hot)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    post_type: str | None = Query(default=None),
    subject_category: str | None = Query(default=None),
    author_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    viewer_id: str | None = Depends(optional_user_id),
):
    try:
        data = _svc().list_posts(
            sort=sort,
            page=page,
            page_size=page_size,
            post_type=post_type,
            subject_category=subject_category,
            author_id=author_id,
            q=q,
            viewer_id=viewer_id,
        )
        return success_response(data)
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    viewer_id: str | None = Depends(optional_user_id),
):
    try:
        post = _svc().get_post(post_id, viewer_id=viewer_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not post:
        return error_response("帖子不存在")
    return success_response(post)


@router.post("/posts")
async def create_post(
    body: PostCreate,
    user_id: str = Depends(require_user_id),
):
    try:
        post = _svc().create_post(user_id, body)
        return success_response(post, message="发布成功")
    except ValueError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("发帖失败 user_id=%s", user_id)
        return error_response(f"发帖失败：{exc}")


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: str,
    body: PostUpdate,
    user_id: str = Depends(require_user_id),
):
    try:
        post = _svc().update_post(post_id, user_id, body)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not post:
        return error_response("帖子不存在或无权修改")
    return success_response(post, message="更新成功")


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    user_id: str = Depends(require_user_id),
):
    try:
        ok = _svc().delete_post(post_id, user_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not ok:
        return error_response("帖子不存在或无权删除")
    return success_response(message="帖子已删除")


# ==================== 评论 ====================


@router.get("/posts/{post_id}/comments")
async def list_comments(post_id: str):
    try:
        return success_response(_svc().list_comments(post_id))
    except RuntimeError as exc:
        return error_response(str(exc))


@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str,
    body: CommentCreate,
    user_id: str = Depends(require_user_id),
):
    try:
        comment = _svc().create_comment(
            post_id, user_id, body.content, body.parent_id
        )
        return success_response(comment, message="评论成功")
    except ValueError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("评论失败 post_id=%s user_id=%s", post_id, user_id)
        return error_response(f"评论失败：{exc}")


# ==================== 收藏 ====================


@router.post("/posts/{post_id}/favorite")
async def toggle_favorite(
    post_id: str,
    user_id: str = Depends(require_user_id),
):
    try:
        result = _svc().toggle_favorite(post_id, user_id)
        return success_response(
            result,
            message="已收藏" if result.get("favorited") else "已取消收藏",
        )
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("收藏失败 post_id=%s user_id=%s", post_id, user_id)
        return error_response(f"收藏失败：{exc}")


@router.get("/favorites")
async def list_favorites(
    page: int = Query(default=1, ge=1),
    user_id: str = Depends(require_user_id),
):
    try:
        return success_response(_svc().list_favorites(user_id, page=page))
    except RuntimeError as exc:
        return error_response(str(exc))


# ==================== 关注 ====================


@router.post("/users/{target_id}/follow")
async def follow_user(
    target_id: str,
    user_id: str = Depends(require_user_id),
):
    try:
        result = _svc().follow_user(user_id, target_id)
        return success_response(result, message="已关注")
    except ValueError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))


@router.delete("/users/{target_id}/follow")
async def unfollow_user(
    target_id: str,
    user_id: str = Depends(require_user_id),
):
    try:
        result = _svc().unfollow_user(user_id, target_id)
        return success_response(result, message="已取消关注")
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/following")
async def list_following(
    user: str | None = Query(default=None, description="查看指定用户的关注列表"),
    user_id: str = Depends(require_user_id),
):
    try:
        target = user or user_id
        return success_response(_svc().list_following(target))
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/followers")
async def list_followers(
    user: str | None = Query(default=None, description="查看指定用户的粉丝列表"),
    user_id: str = Depends(require_user_id),
):
    try:
        target = user or user_id
        return success_response(_svc().list_followers(target))
    except RuntimeError as exc:
        return error_response(str(exc))


# ==================== 用户 ====================


@router.get("/users/me")
async def get_my_profile(user_id: str = Depends(require_user_id)):
    try:
        profile = _svc().get_user_profile(user_id, viewer_id=user_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not profile:
        _svc().ensure_user_row(user_id)
        profile = _svc().get_user_profile(user_id, viewer_id=user_id)
    if not profile:
        return error_response("用户不存在")
    return success_response(profile)


@router.get("/users/{identifier}")
async def get_user_profile(
    identifier: str,
    viewer_id: str | None = Depends(optional_user_id),
):
    try:
        profile = _svc().get_user_profile(identifier, viewer_id=viewer_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not profile:
        return error_response("用户不存在")
    return success_response(profile)


@router.patch("/users/me")
async def update_my_profile(
    body: UserProfileUpdate,
    user_id: str = Depends(require_user_id),
):
    try:
        profile = _svc().update_user_profile(
            user_id,
            subject_category=body.subject_category,
            avatar_url=body.avatar_url,
        )
        return success_response(profile, message="资料已更新")
    except ValueError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))


# ==================== 搜索 ====================


@router.get("/search")
async def search(q: str = Query(min_length=1)):
    try:
        return success_response(_svc().search(q))
    except RuntimeError as exc:
        return error_response(str(exc))


# ==================== 附件上传 ====================


@router.post("/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    user_id: str = Depends(require_user_id),
):
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return error_response("文件不能超过 10MB")
    try:
        result = _svc().upload_attachment(
            user_id,
            file.filename or "file",
            content,
            file.content_type or "",
        )
        return success_response(result, message="上传成功")
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"上传失败：{exc}")


@router.post("/posts/{post_id}/add-to-wrong-questions")
async def add_post_to_wrong_questions(
    post_id: str,
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """将社区帖子加入错题本（下载附件或保存正文为笔记）。"""
    try:
        post = _svc().get_post(post_id, viewer_id=user_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not post:
        return error_response("帖子不存在")

    wq_service = WrongQuestionService(db)
    try:
        question = _sync_post_to_wrong_questions(db, post, user_id)
    except Exception as exc:
        return error_response(f"加入错题本失败：{exc}")

    data = wq_service._to_dict(question)
    data["created_at"] = data["created_at"].isoformat()
    return success_response(data, message="已加入错题本")
