"""
考研 AI 平台 — FastAPI 应用入口。

启动方式（在项目根目录）：
  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 必须先加载 .env，再初始化 Settings（避免读到旧环境变量）
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")
load_dotenv(_project_root / ".env.local")
load_dotenv(_project_root / "crawler" / ".env")

from app.config import get_settings
from app.database import init_db
from app.routers import admin, chat, community, schools, settings, tasks, translator, wrong_questions
from app.modules.en_learn.router import router as en_learn_router
from app.modules.tts.router import router as tts_router
from app.modules.word_dict.router import router as word_dict_router
from app.modules.word_dict.database import init_word_lib_db
from app.services.vector_sync_service import get_vector_sync_service
from app.utils.admin_auth import require_admin
from app.utils.file_utils import ensure_dir
from app.utils.response import success_response

# Settings 已在上方 load_dotenv 后导入
_settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库与必要目录。"""
    settings = get_settings()

    # 确保关键目录存在
    ensure_dir(settings.public_data_path)
    ensure_dir(settings.upload_path)
    ensure_dir(settings.upload_path.parent / "chat")   # uploads/chat/ 聊天图片
    ensure_dir(settings.chroma_path)

    init_db()
    try:
        init_word_lib_db()
        logger.info("word_lib 词库初始化完成")
    except Exception as exc:
        logger.warning("word_lib 初始化失败（可先导入 ECDICT）: %s", exc)
    logger.info("数据库初始化完成")
    logger.info("公共资料目录: %s", settings.public_data_path)
    logger.info("错题上传目录: %s", settings.upload_path)

    # Redis 连通性探测（失败则自动降级，不阻断启动）
    try:
        from app.infrastructure.cache.redis_client import is_redis_enabled

        if settings.redis_url.strip():
            logger.info("Redis 已配置: %s", settings.redis_url.split("@")[-1])
            logger.info("Redis 可用: %s", is_redis_enabled())
        else:
            logger.info("未配置 REDIS_URL，缓存与 Celery 将使用内存降级")
    except Exception as exc:
        logger.warning("Redis 初始化探测失败: %s", exc)

    yield
    logger.info("服务关闭")


app = FastAPI(
    title="考研 AI 平台 API",
    description="AI 聊天 + 错题本 + RAG 知识库",
    version="0.1.1",
    lifespan=lifespan,
)

# CORS — 允许 Next.js 前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(schools.router)
app.include_router(wrong_questions.router)
app.include_router(translator.router)
app.include_router(settings.router)
app.include_router(community.router)
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(en_learn_router)
app.include_router(tts_router)
app.include_router(word_dict_router)

# 静态文件服务 — 提供上传图片访问（确保目录存在后再挂载）
_uploads_root = get_settings().root / "uploads"
_uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_root)), name="uploads")


@app.post("/api/admin/vector-sync")
async def trigger_vector_sync(admin_id: str = Depends(require_admin)):
    """手动触发 Supabase → Chroma 增量向量同步（需管理员权限）。"""
    from app.utils.admin_audit import log_admin_action

    settings = get_settings()
    if not settings.effective_supabase_url or not settings.effective_supabase_service_key:
        return {"success": False, "message": "未配置 Supabase"}
    if not settings.dashscope_api_key:
        return {"success": False, "message": "未配置 DASHSCOPE_API_KEY"}
    try:
        result = get_vector_sync_service().sync()
        log_admin_action(admin_id, "vector_sync.execute", detail=result)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.exception("向量同步失败")
        return {"success": False, "message": str(exc)}


@app.get("/api/health")
async def health_check():
    """健康检查接口。"""
    settings = get_settings()
    api_key_ok = bool(settings.dashscope_api_key.strip())
    redis_ok = False
    try:
        from app.infrastructure.cache.redis_client import is_redis_enabled

        redis_ok = is_redis_enabled()
    except Exception:
        pass
    return success_response(
        {
            "status": "ok",
            "llm_model": settings.llm_model,
            "vl_model": settings.vl_model,
            "asr_model": settings.asr_model,
            "embedding_model": settings.embedding_model,
            "rag_top_k": settings.rag_top_k,
            "max_image_upload_mb": settings.max_image_upload_bytes // (1024 * 1024),
            "max_audio_seconds": settings.max_audio_seconds,
            "api_key_configured": api_key_ok,
            "redis_configured": bool(settings.redis_url.strip()),
            "redis_available": redis_ok,
            "public_data_dir": str(settings.public_data_path),
        }
    )


@app.post("/api/debug/echo")
async def debug_echo(request: Request):
    """
    调试接口：打印收到的所有表单字段和文件，返回摘要，不调用 AI 模型。
    用法：在浏览器 DevTools → Network 里观察请求体是否包含 image_file。
    """
    form = await request.form()
    result: dict = {}
    for key in form:
        value = form[key]
        if hasattr(value, "filename"):  # UploadFile
            content = await value.read()
            result[key] = {
                "type": "file",
                "filename": value.filename,
                "content_type": value.content_type,
                "size_bytes": len(content),
                "first_20_bytes_hex": content[:20].hex() if content else "",
            }
        else:
            result[key] = {"type": "field", "value": str(value)[:200]}
    return success_response(result, message="echo ok")


@app.get("/")
async def root():
    """根路径说明。"""
    return success_response(
        {
            "name": "考研 AI 平台 API",
            "docs": "/docs",
            "endpoints": {
                "chat": "/api/chat",
                "wrong_questions": "/api/wrong-questions",
                "translator": "/api/translator",
                "en_learn": "/api/en-learn",
                "word_query": "/api/word-query",
                "tts": "/api/tts",
                "community": "/api/community",
                "schools": "/api/schools",
                "majors": "/api/majors",
                "statistics": "/api/statistics",
                "admissions": "/api/admissions",
                "score_lines": "/api/score-lines",
                "health": "/api/health",
                "tasks": "/api/tasks",
            },
        }
    )
