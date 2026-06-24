"""
向量存储基础设施 — 抽象接口 + Chroma 实现。
"""

from app.infrastructure.vector.base import VectorStore, VectorDocument, VectorQueryResult
from app.infrastructure.vector.chroma_impl import ChromaVectorStore, get_chroma_store
from app.infrastructure.vector.temp_paper import TempPaperStore, get_temp_paper_store
from app.infrastructure.vector.kaoyan_bank import KaoyanBankStore, get_kaoyan_bank_store
