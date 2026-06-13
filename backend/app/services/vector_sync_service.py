"""
Supabase 招生数据 → Chroma 向量库增量同步。

仅处理 last_updated 变更或 content_hash 变化的数据；切片去重；单条失败隔离。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from supabase import Client, create_client

from app.config import get_settings

logger = logging.getLogger(__name__)

COLLECTION_SCHOOL = "school_knowledge"
STATE_FILENAME = "vector_sync_state.json"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text or not text.strip():
        return []
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    doc = Document(text=text.strip())
    return [n.get_content() for n in splitter.get_nodes_from_documents([doc])]


class VectorSyncService:
    """后台增量向量化 Supabase 院校/招生数据。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._sb: Client | None = None
        self._chroma: chromadb.PersistentClient | None = None
        self._embed: DashScopeEmbedding | None = None
        self._state_path = self.settings.chroma_path / STATE_FILENAME

    def _get_supabase(self) -> Client:
        if self._sb is None:
            if not self.settings.supabase_url or not self.settings.supabase_service_key:
                raise RuntimeError("未配置 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
            self._sb = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_key,
            )
        return self._sb

    def _get_chroma(self) -> chromadb.PersistentClient:
        if self._chroma is None:
            self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        return self._chroma

    def _get_embed(self) -> DashScopeEmbedding:
        if self._embed is None:
            self._embed = DashScopeEmbedding(
                model_name=self.settings.embedding_model,
                api_key=self.settings.dashscope_api_key,
            )
        return self._embed

    def _load_state(self) -> dict[str, Any]:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"last_sync_at": None, "synced_records": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _existing_chunk_hashes(self, collection: chromadb.Collection) -> set[str]:
        try:
            data = collection.get(include=["metadatas"])
            metas = data.get("metadatas") or []
            return {
                m["chunk_hash"]
                for m in metas
                if m and m.get("chunk_hash")
            }
        except Exception:
            return set()

    def _fetch_rows(
        self,
        table: str,
        select: str,
        *,
        since: str | None,
    ) -> list[dict]:
        sb = self._get_supabase()
        q = sb.table(table).select(select)
        if since:
            if table == "announcements":
                q = q.gt("last_updated", since)
            else:
                q = q.gt("updated_at", since)
        res = q.execute()
        return res.data or []

    def _row_to_text(self, table: str, row: dict, uni_name: str = "") -> str:
        if table == "announcements":
            return (
                f"【{uni_name}·{row.get('type', '公告')}】{row.get('title', '')}\n"
                f"发布时间：{row.get('publish_time', '')}\n"
                f"{row.get('content') or ''}"
            ).strip()
        if table == "universities":
            tags = []
            if row.get("level_985"):
                tags.append("985")
            if row.get("level_211"):
                tags.append("211")
            if row.get("double_first_class"):
                tags.append(str(row["double_first_class"]))
            return (
                f"【院校】{row.get('name', '')}（{'/'.join(tags)}）\n"
                f"省份：{row.get('province', '')} {row.get('city', '')}\n"
                f"类型：{row.get('school_type', '')}\n"
                f"{row.get('intro') or ''}"
            ).strip()
        if table == "majors":
            return (
                f"【专业·{uni_name}】{row.get('name', '')}（{row.get('code', '')}）\n"
                f"学院：{row.get('college', '')} | {row.get('degree_type', '')} | "
                f"{row.get('study_mode', '')}\n"
                f"招生人数：{row.get('enrollment_count') or '未知'}"
            ).strip()
        return ""

    def sync(self) -> dict[str, Any]:
        """
        增量同步入口。返回统计信息。
        某条失败仅记录日志，不中断整体流程，不对失败条目重试。
        """
        state = self._load_state()
        since = state.get("last_sync_at")
        synced_records: dict[str, str] = dict(state.get("synced_records") or {})

        client = self._get_chroma()
        collection = client.get_or_create_collection(COLLECTION_SCHOOL)
        known_chunks = self._existing_chunk_hashes(collection)
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
            embed_model=self._get_embed(),
        )

        stats = {
            "scanned": 0,
            "skipped_unchanged": 0,
            "chunks_new": 0,
            "chunks_reused": 0,
            "errors": 0,
        }

        sb = self._get_supabase()
        uni_res = sb.table("universities").select("id,name").execute()
        uni_map = {u["id"]: u["name"] for u in (uni_res.data or [])}

        tables: list[tuple[str, str]] = [
            (
                "announcements",
                "id,university_id,title,type,publish_time,content,content_hash,last_updated",
            ),
            (
                "universities",
                "id,name,province,city,school_type,level_985,level_211,"
                "double_first_class,intro,updated_at",
            ),
            (
                "majors",
                "id,university_id,name,code,college,degree_type,study_mode,"
                "enrollment_count,updated_at",
            ),
        ]

        new_nodes = []
        chunk_size = self.settings.vector_chunk_size
        overlap = self.settings.vector_chunk_overlap

        for table, select in tables:
            try:
                rows = self._fetch_rows(table, select, since=since)
            except Exception as exc:
                logger.error("拉取 %s 失败: %s", table, exc)
                stats["errors"] += 1
                continue

            for row in rows:
                stats["scanned"] += 1
                record_id = str(row.get("id", ""))
                record_key = f"{table}:{record_id}"
                content_hash = row.get("content_hash") or _md5(
                    json.dumps(row, ensure_ascii=False, sort_keys=True)
                )
                last_sig = synced_records.get(record_key)
                if last_sig == content_hash:
                    stats["skipped_unchanged"] += 1
                    continue

                uni_name = uni_map.get(row.get("university_id", ""), "")
                text = self._row_to_text(table, row, uni_name)
                if not text or len(text) < 20:
                    synced_records[record_key] = content_hash
                    continue

                try:
                    chunks = _chunk_text(text, chunk_size, overlap)
                    for i, chunk in enumerate(chunks):
                        chunk_hash = _md5(chunk)
                        if chunk_hash in known_chunks:
                            stats["chunks_reused"] += 1
                            continue
                        doc = Document(
                            text=chunk,
                            metadata={
                                "source_table": table,
                                "record_id": record_id,
                                "chunk_index": i,
                                "chunk_hash": chunk_hash,
                                "content_hash": content_hash,
                                "university": uni_name or row.get("name", ""),
                            },
                        )
                        node = SentenceSplitter(
                            chunk_size=len(chunk) + 1,
                            chunk_overlap=0,
                        ).get_nodes_from_documents([doc])[0]
                        new_nodes.append(node)
                        known_chunks.add(chunk_hash)
                        stats["chunks_new"] += 1
                    synced_records[record_key] = content_hash
                except Exception as exc:
                    logger.error("向量化失败 %s: %s", record_key, exc)
                    stats["errors"] += 1

        if new_nodes:
            index.insert_nodes(new_nodes)

        state["last_sync_at"] = datetime.now(timezone.utc).isoformat()
        state["synced_records"] = synced_records
        self._save_state(state)

        logger.info(
            "向量同步完成: scanned=%d new_chunks=%d reused=%d skipped=%d errors=%d",
            stats["scanned"],
            stats["chunks_new"],
            stats["chunks_reused"],
            stats["skipped_unchanged"],
            stats["errors"],
        )
        return stats


_vector_sync: VectorSyncService | None = None


def get_vector_sync_service() -> VectorSyncService:
    global _vector_sync
    if _vector_sync is None:
        _vector_sync = VectorSyncService()
    return _vector_sync
