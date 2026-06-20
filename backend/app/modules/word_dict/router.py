"""单词查询路由 — GET /api/word-query"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.word_dict.database import get_word_lib_db
from app.modules.word_dict.service import WordDictService, get_word_dict_service
from app.utils.auth import require_user_id
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/word-query", tags=["WordDict"])


@router.get("")
async def word_query(
    word: str = Query(..., min_length=1, max_length=64),
    mode: str = Query(default="hover", pattern="^(hover|detail)$"),
    _user_id: str = Depends(require_user_id),
    db: Session = Depends(get_word_lib_db),
    service: WordDictService = Depends(get_word_dict_service),
):
    """
    双层查询：优先 ECDICT 本地库；未命中则 Ollama 考研释义并写入 word_lib 永久缓存。
    """
    result = await service.query(db, word, mode=mode)  # type: ignore[arg-type]
    if result is None:
        return error_response(f"未找到单词：{word}")
    return success_response(result.model_dump(), message="ok")
