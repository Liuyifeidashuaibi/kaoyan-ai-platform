"""
考研 AI 平台 — FastAPI 应用入口。

启动方式（在项目根目录）：
  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import chat, wrong_questions
from app.utils.file_utils import ensure_dir
from app.utils.response import success_response

# 从项目根目录加载 .env
_settings = get_settings()
load_dotenv(_settings.root / ".env")

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
    logger.info("数据库初始化完成")
    logger.info("公共资料目录: %s", settings.public_data_path)
    logger.info("错题上传目录: %s", settings.upload_path)

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
app.include_router(wrong_questions.router)

# 静态文件服务 — 提供上传图片访问（确保目录存在后再挂载）
_uploads_root = get_settings().root / "uploads"
_uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_root)), name="uploads")


@app.get("/api/health")
async def health_check():
    """健康检查接口。"""
    settings = get_settings()
    api_key_ok = bool(settings.dashscope_api_key.strip())
    return success_response(
        {
            "status": "ok",
            "llm_model": settings.llm_model,
            "vl_model": settings.vl_model,
            "max_image_upload_mb": settings.max_image_upload_bytes // (1024 * 1024),
            "api_key_configured": api_key_ok,
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
                "health": "/api/health",
            },
        }
    )
