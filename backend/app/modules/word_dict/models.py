"""word_lib ORM — 字段对齐 ECDICT。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.modules.word_dict.database import WordLibBase


class WordLibEntry(WordLibBase):
    __tablename__ = "word_lib"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(128), nullable=False, index=True)
    phonetic = Column(String(128))
    definition = Column(Text)
    translation = Column(Text)
    pos = Column(String(64))
    collins = Column(Integer, default=0)
    oxford = Column(Integer, default=0)
    tag = Column(String(128))
    bnc = Column(Integer, default=0)
    frq = Column(Integer, default=0)
    exchange = Column(Text)
    detail = Column(Text)
    audio = Column(Text)
    ai_generated = Column(Integer, default=0)
    kaoyan_gloss = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
