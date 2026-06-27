"""
Agent 模板管理路由 — 文档/行业模板 CRUD + 语义匹配 + 文件入库 + 格式校验。

端点：
  GET    /api/agent/templates              列出模板（支持 category/doc_type 过滤）
  POST   /api/agent/templates              创建模板（写 DB + 向量化）
  GET    /api/agent/templates/{id}         获取模板详情
  PUT    /api/agent/templates/{id}         更新模板
  DELETE /api/agent/templates/{id}         删除模板
  POST   /api/agent/templates/ingest       上传模板文件向量化入库
  POST   /api/agent/templates/match        语义匹配模板
  POST   /api/agent/templates/validate     格式校验
"""

import logging
import pathlib

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.config import get_settings
from app.schemas.agent import (
    TemplateCreate,
    TemplateMatchRequest,
    TemplateUpdate,
    TemplateValidateRequest,
)
from app.services.template_service import get_template_service
from app.utils.file_utils import ensure_dir
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/agent/templates", tags=["Agent模板管理"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("")
async def list_templates(
    category: str | None = Query(default=None, description="按分类过滤"),
    doc_type: str | None = Query(default=None, description="按文档类型过滤"),
    active_only: bool = Query(default=True, description="仅返回启用中的模板"),
):
    """列出所有模板（支持按分类/文档类型过滤）。"""
    svc = get_template_service()
    templates = svc.list_templates(
        category=category,
        doc_type=doc_type,
        active_only=active_only,
    )
    return success_response(templates)


@router.post("")
async def create_template(body: TemplateCreate):
    """创建模板 — 写 DB + 向量化入库。"""
    svc = get_template_service()
    result = svc.create_template(
        name=body.name,
        category=body.category,
        doc_type=body.doc_type,
        description=body.description,
        style_rules=body.style_rules,
        cover_format=body.cover_format,
        validation_rules=body.validation_rules,
        source_text=body.source_text,
    )
    if "error" in result:
        return error_response(result["error"])
    return success_response(result, message="模板创建成功")


@router.get("/{template_id}")
async def get_template(template_id: int):
    """获取模板详情。"""
    svc = get_template_service()
    tpl = svc.get_template(template_id)
    if tpl is None:
        return error_response("模板不存在")
    return success_response(tpl)


@router.put("/{template_id}")
async def update_template(template_id: int, body: TemplateUpdate):
    """更新模板 — 修改 DB + 重新向量化。"""
    svc = get_template_service()
    # 只传非 None 的字段
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return error_response("未提供任何更新字段")
    result = svc.update_template(template_id, **fields)
    if result is None:
        return error_response("模板不存在")
    return success_response(result, message="模板更新成功")


@router.delete("/{template_id}")
async def delete_template(template_id: int):
    """删除模板。"""
    svc = get_template_service()
    ok = svc.delete_template(template_id)
    if not ok:
        return error_response("模板不存在")
    return success_response(message="模板已删除")


@router.post("/ingest")
async def ingest_template_file(
    name: str = Form(..., description="模板名称"),
    file: UploadFile = File(..., description="模板文件（docx/pdf/txt/md）"),
    category: str = Form(default="general"),
    doc_type: str = Form(default="pdf"),
):
    """
    上传模板文件，解析内容后向量化入库。

    支持 docx/pdf/txt/md 格式，使用 DocumentParser（Unstructured 引擎）解析。
    提取的纯文本作为 source_text 存入 DB + 向量化。
    """
    try:
        file_bytes = await file.read()
    except Exception as exc:
        return error_response(f"读取文件失败: {exc}")

    if not file_bytes:
        return error_response("文件为空")

    # 保存到 uploads/chat/
    chat_upload_dir = settings.upload_path.parent / "chat"
    ensure_dir(chat_upload_dir)

    import uuid as _uuid
    safe_name = pathlib.Path(file.filename or "template.docx").name
    stem = pathlib.Path(safe_name).stem
    ext = pathlib.Path(safe_name).suffix
    file_id = _uuid.uuid4().hex[:8]
    saved_name = f"{stem}_{file_id}{ext}"
    saved_path = chat_upload_dir / saved_name
    saved_path.write_bytes(file_bytes)
    logger.info("[Template] 模板文件已保存: %s", saved_name)

    svc = get_template_service()
    result = svc.ingest_template_file(
        file_path=str(saved_path),
        name=name,
        category=category,
        doc_type=doc_type,
    )
    if "error" in result:
        return error_response(result["error"])
    return success_response(result, message="模板文件入库成功")


@router.post("/match")
async def match_template(body: TemplateMatchRequest):
    """
    语义匹配模板 — 按文档类型+查询关键词召回最佳匹配模板。

    Agent 导出前调用此接口（或通过 search_template 工具）获取格式约束。
    """
    svc = get_template_service()
    matches = svc.match_template(
        doc_type=body.doc_type,
        query=body.query,
    )
    return success_response(matches)


@router.post("/validate")
async def validate_format(body: TemplateValidateRequest):
    """
    格式校验 — 按模板 validation_rules 检查内容合规性。

    返回不合格项清单，Agent 据此返工修正。
    """
    svc = get_template_service()
    result = svc.validate_content(
        content=body.content,
        template_id=body.template_id,
    )
    if "error" in result:
        return error_response(result["error"])
    return success_response(result)
