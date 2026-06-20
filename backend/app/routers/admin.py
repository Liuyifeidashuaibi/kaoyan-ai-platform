"""管理后台 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services import admin_service
from app.utils.admin_audit import log_admin_action
from app.utils.admin_auth import require_admin
from app.utils.response import success_response

AdminId = Annotated[str, Depends(require_admin)]

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AgentPlanRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=500)


class AgentExecuteRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)


class PostModerateRequest(BaseModel):
    action: str = Field(..., pattern="^(hide|show|delete)$")


class BatchModerateRequest(BaseModel):
    post_ids: list[str] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern="^(hide|show|delete)$")


class SchoolUpsertBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    province: str | None = None
    city: str | None = None
    school_type: str | None = None
    level_985: bool | None = None
    level_211: bool | None = None
    double_first_class: str | None = None
    website: str | None = None
    intro: str | None = None


class MajorUpsertBody(BaseModel):
    university_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = None
    college: str | None = None
    subject_category: str | None = None
    degree_type: str | None = None
    study_mode: str | None = None


class MajorPatchBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = None
    college: str | None = None
    subject_category: str | None = None
    degree_type: str | None = None
    study_mode: str | None = None


class CollegeUpsertBody(BaseModel):
    university_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    official_site: str | None = None


class CollegePatchBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    official_site: str | None = None


class AnnouncementUpsertBody(BaseModel):
    university_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=500)
    publish_time: str = Field(..., min_length=4, max_length=32)
    url: str = Field(..., min_length=1, max_length=2000)
    type: str | None = Field(None, max_length=64)
    content: str | None = None


class AnnouncementPatchBody(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    publish_time: str | None = Field(None, min_length=4, max_length=32)
    url: str | None = Field(None, min_length=1, max_length=2000)
    type: str | None = Field(None, max_length=64)
    content: str | None = None


class PdfUpsertBody(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=500)
    file_path: str = Field(..., min_length=1, max_length=2000)
    school_id: str | None = None
    file_type: str | None = Field(None, max_length=128)
    file_size: int | None = None
    source_url: str | None = None
    batch_id: str | None = None


class PdfPatchBody(BaseModel):
    file_name: str | None = Field(None, min_length=1, max_length=500)
    file_path: str | None = Field(None, min_length=1, max_length=2000)
    school_id: str | None = None
    file_size: int | None = None
    source_url: str | None = None


@router.get("/dashboard/metrics")
async def dashboard_metrics(_: Annotated[str, Depends(require_admin)]):
    try:
        data = await admin_service.get_dashboard_metrics()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success_response(data)


@router.get("/dashboard/activity")
async def dashboard_activity(
    _: Annotated[str, Depends(require_admin)],
    limit: int = 10,
):
    data = await admin_service.get_dashboard_activity(limit=limit)
    return success_response(data)


@router.get("/users")
async def list_users(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_users(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.post("/community/posts/batch-moderate")
async def batch_moderate_posts(
    body: BatchModerateRequest,
    admin_id: AdminId,
):
    try:
        data = await admin_service.batch_moderate_posts(body.post_ids, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_admin_action(
        admin_id,
        "posts.batch_moderate",
        detail={"action": body.action, "count": len(body.post_ids)},
    )
    return success_response(data)


@router.get("/community/posts/{post_id}")
async def get_post_detail(
    post_id: str,
    _: AdminId,
):
    data = await admin_service.get_post_detail(post_id)
    if not data:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return success_response(data)


@router.post("/community/posts/{post_id}/moderate")
async def moderate_post(
    post_id: str,
    body: PostModerateRequest,
    admin_id: AdminId,
):
    try:
        data = await admin_service.moderate_post(post_id, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "posts.moderate", post_id, {"action": body.action})
    return success_response(data, message=f"帖子已{body.action}")


@router.delete("/community/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    admin_id: AdminId,
):
    try:
        data = await admin_service.delete_comment(comment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "comments.delete", comment_id)
    return success_response(data, message="评论已删除")


@router.get("/community/posts")
async def list_community_posts(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_posts(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.get("/colleges")
async def list_colleges(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_colleges(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.get("/schools")
async def list_schools(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_schools(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.get("/majors")
async def list_majors(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_majors(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.post("/schools")
async def create_school(
    body: SchoolUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.create_school(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "schools.create", data.get("id", ""), {"name": data.get("name")})
    return success_response(data, message="学校已创建")


@router.patch("/schools/{school_id}")
async def update_school(
    school_id: str,
    body: SchoolUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.update_school(school_id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "schools.update", school_id)
    return success_response(data, message="学校已更新")


@router.post("/majors")
async def create_major(
    body: MajorUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.create_major(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "majors.create", data.get("id", ""))
    return success_response(data, message="专业已创建")


@router.patch("/majors/{major_id}")
async def update_major(
    major_id: str,
    body: MajorPatchBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.update_major(major_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "majors.update", major_id)
    return success_response(data, message="专业已更新")


@router.post("/colleges")
async def create_college(
    body: CollegeUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.create_college(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "colleges.create", data.get("id", ""))
    return success_response(data, message="学院已创建")


@router.patch("/colleges/{college_id}")
async def update_college(
    college_id: str,
    body: CollegePatchBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.update_college(college_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "colleges.update", college_id)
    return success_response(data, message="学院已更新")


@router.get("/audit-logs")
async def audit_logs(_: AdminId, limit: int = 50):
    from app.utils.admin_audit import list_audit_logs

    return success_response(list_audit_logs(limit=min(limit, 200)))


@router.get("/monitoring/health")
async def monitoring_health(_: Annotated[str, Depends(require_admin)]):
    data = await admin_service.get_monitoring_health()
    return success_response(data)


@router.get("/monitoring/{section}")
async def monitoring_section(
    section: str,
    _: Annotated[str, Depends(require_admin)],
):
    if section not in ("api", "database", "agents", "errors", "queue"):
        raise HTTPException(status_code=404, detail="未知监控项")
    data = await admin_service.get_monitoring_detail(section)
    return success_response(data)


@router.get("/community/comments")
async def list_comments(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_comments(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.get("/community/moderation")
async def list_moderation(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.list_moderation_queue(page=page, page_size=page_size)
    return success_response(data)


@router.get("/community/reports")
async def list_reports(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.list_reports(page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/follows")
async def list_follows(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.list_user_follows(page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/favorites")
async def list_favorites(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.list_favorite_stats(page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/post-stats")
async def list_post_stats(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.list_post_stats(page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/{user_id}/posts")
async def get_user_posts(
    user_id: str,
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 10,
):
    data = await admin_service.get_user_posts(user_id, page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/{user_id}/follows")
async def get_user_follows_for(
    user_id: str,
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 10,
):
    data = await admin_service.get_user_follows_for(user_id, page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/{user_id}/favorites")
async def get_user_favorites_for(
    user_id: str,
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 10,
):
    data = await admin_service.get_user_favorites_for(user_id, page=page, page_size=page_size)
    return success_response(data)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    data = await admin_service.get_user_detail(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success_response(data)


@router.get("/schools/announcements")
async def list_announcements(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_announcements(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.post("/schools/announcements")
async def create_announcement(
    body: AnnouncementUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.create_announcement(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "announcements.create", data.get("id", ""))
    return success_response(data, message="公告已创建")


@router.patch("/schools/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    body: AnnouncementPatchBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.update_announcement(
            announcement_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "announcements.update", announcement_id)
    return success_response(data, message="公告已更新")


@router.delete("/schools/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    admin_id: AdminId,
):
    try:
        data = await admin_service.delete_announcement(announcement_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "announcements.delete", announcement_id)
    return success_response(data, message="公告已删除")


@router.get("/schools/pdfs")
async def list_pdfs(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    q: str = "",
):
    data = await admin_service.list_pdfs(page=page, page_size=page_size, q=q)
    return success_response(data)


@router.post("/schools/pdfs")
async def create_pdf(
    body: PdfUpsertBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.create_pdf_record(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "pdfs.create", data.get("id", ""))
    return success_response(data, message="PDF 记录已创建")


@router.patch("/schools/pdfs/{pdf_id}")
async def update_pdf(
    pdf_id: str,
    body: PdfPatchBody,
    admin_id: AdminId,
):
    try:
        data = await admin_service.update_pdf_record(pdf_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "pdfs.update", pdf_id)
    return success_response(data, message="PDF 记录已更新")


@router.delete("/schools/pdfs/{pdf_id}")
async def delete_pdf(
    pdf_id: str,
    admin_id: AdminId,
):
    try:
        data = await admin_service.delete_pdf_record(pdf_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_admin_action(admin_id, "pdfs.delete", pdf_id)
    return success_response(data, message="PDF 记录已删除")


@router.get("/schools/sync-logs")
async def sync_logs(
    _: Annotated[str, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
):
    data = await admin_service.get_sync_logs(page=page, page_size=page_size)
    return success_response(data)


@router.get("/agents/status")
async def agents_status(_: Annotated[str, Depends(require_admin)]):
    return success_response(admin_service.get_agent_status())


@router.get("/agents/tasks/{task_id}")
async def agents_task_detail(
    task_id: str,
    _: Annotated[str, Depends(require_admin)],
):
    task = admin_service.get_agent_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return success_response(task)


@router.post("/agents/tasks/{task_id}/cancel")
async def agents_cancel(
    task_id: str,
    admin_id: AdminId,
):
    try:
        task = admin_service.cancel_agent_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_admin_action(admin_id, "agents.cancel", task_id)
    return success_response(task)


@router.post("/agents/tasks/{task_id}/retry")
async def agents_retry(
    task_id: str,
    admin_id: AdminId,
):
    try:
        task = admin_service.retry_agent_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_admin_action(admin_id, "agents.retry", task_id)
    return success_response(task)


@router.get("/agents/tasks")
async def agents_tasks(_: Annotated[str, Depends(require_admin)]):
    return success_response(admin_service.list_agent_tasks())


@router.post("/agents/plan")
async def agents_plan(
    body: AgentPlanRequest,
    admin_id: AdminId,
):
    plan = admin_service.create_agent_plan(body.intent.strip())
    log_admin_action(admin_id, "agents.plan", plan.get("id", ""), {"intent": body.intent[:200]})
    return success_response(plan)


@router.post("/agents/execute")
async def agents_execute(
    body: AgentExecuteRequest,
    admin_id: AdminId,
):
    try:
        task = admin_service.execute_agent_plan(body.plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_admin_action(admin_id, "agents.execute", body.plan_id, {"task_id": task.get("id", "")})
    return success_response(task)
