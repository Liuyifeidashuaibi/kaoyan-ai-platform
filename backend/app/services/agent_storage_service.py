"""
MinIO 对象存储服务 — 商业级文件资产管理。

核心能力：
  1. 文件上传：上传原稿、中间草稿、最终成品到 MinIO 对象存储
  2. 文件下载：从 MinIO 下载文件
  3. 文件列表：查询指定前缀下的文件列表
  4. 本地降级：MinIO 不可用时自动降级为本地文件系统存储
  5. 预签名URL：生成临时下载链接（可设置过期时间）

配置：
  MINIO_ENDPOINT  — MinIO 服务地址（默认 127.0.0.1:9000）
  MINIO_ACCESS_KEY — 访问密钥
  MINIO_SECRET_KEY — 秘密密钥
  MINIO_BUCKET    — 存储桶名（默认 kaoyan-agent）
  MINIO_SECURE    — 是否使用 HTTPS（默认 False）
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


class StorageService:
    """
    对象存储服务 — MinIO + 本地降级。

    优先使用 MinIO 对象存储，不可用时降级为本地文件系统。
    对上层透明：调用方不关心文件存储在哪里。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._minio_client = None
        self._bucket_name = os.environ.get("MINIO_BUCKET", "kaoyan-agent")
        self._local_root = self.settings.upload_path.parent / "chat"
        ensure_dir(self._local_root)

        # 尝试初始化 MinIO 客户端
        self._init_minio()

    def _init_minio(self) -> None:
        """初始化 MinIO 客户端。"""
        endpoint = os.environ.get("MINIO_ENDPOINT", "")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "")

        if not endpoint or not access_key or not secret_key:
            logger.info("MinIO 未配置，使用本地文件存储")
            return

        try:
            from minio import Minio

            secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
            self._minio_client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )

            # 确保存储桶存在
            if not self._minio_client.bucket_exists(self._bucket_name):
                self._minio_client.make_bucket(self._bucket_name)
                logger.info("MinIO 存储桶已创建: %s", self._bucket_name)

            logger.info("MinIO 对象存储已连接: %s/%s", endpoint, self._bucket_name)
        except Exception as exc:
            logger.warning("MinIO 连接失败，降级为本地存储: %s", exc)
            self._minio_client = None

    @property
    def is_minio_available(self) -> bool:
        """MinIO 是否可用。"""
        return self._minio_client is not None

    def upload_file(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "",
        task_id: str | None = None,
        title: str = "",
        format: str = "",
    ) -> dict[str, Any]:
        """
        上传文件到存储。

        Args:
            data: 文件字节
            filename: 原始文件名
            content_type: MIME 类型
            prefix: 对象存储前缀
            task_id: 关联的 Agent 任务 ID（传入时自动写入文件资产清单）
            title: 文件标题（用于资产清单）
            format: 文件格式（用于资产清单）

        返回:
            {
                "object_name": str,  # 存储路径
                "filename": str,     # 文件名
                "size": int,         # 文件大小
                "url": str,          # 下载 URL
                "storage": str,      # "minio" | "local"
            }
        """
        # 生成唯一对象名
        file_id = uuid.uuid4().hex[:12]
        safe_name = Path(filename).name
        stem = Path(safe_name).stem
        ext = Path(safe_name).suffix
        object_name = f"{prefix}{stem}_{file_id}{ext}" if prefix else f"{stem}_{file_id}{ext}"

        if self.is_minio_available:
            try:
                result = self._upload_to_minio(data, object_name, safe_name, content_type)
            except Exception as exc:
                logger.warning("MinIO 上传失败，降级到本地: %s", exc)
                result = self._upload_to_local(data, object_name, safe_name)
        else:
            result = self._upload_to_local(data, object_name, safe_name)

        # 写入文件资产清单（Agent 任务审计）
        if task_id:
            self._record_file_asset(task_id, result, title=title, format=format)

        return result

    def _record_file_asset(
        self,
        task_id: str,
        upload_result: dict[str, Any],
        title: str = "",
        format: str = "",
    ) -> None:
        """将上传文件记录写入 AgentGeneratedFile 表（审计/资产清单）。"""
        try:
            from app.database import AgentGeneratedFile, SessionLocal

            db = SessionLocal()
            try:
                db_file = AgentGeneratedFile(
                    task_id=task_id,
                    object_name=upload_result.get("object_name", ""),
                    filename=upload_result.get("filename", ""),
                    format=format or Path(upload_result.get("filename", "")).suffix.lstrip("."),
                    title=title,
                    size=upload_result.get("size", 0),
                    storage=upload_result.get("storage", "local"),
                    file_url=upload_result.get("url", ""),
                )
                db.add(db_file)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("文件资产记录写 Postgres 失败: %s", exc)

    def _upload_to_minio(
        self,
        data: bytes,
        object_name: str,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        """上传到 MinIO。"""
        from minio.error import S3Error

        stream = io.BytesIO(data)
        self._minio_client.put_object(
            self._bucket_name,
            object_name,
            stream,
            length=len(data),
            content_type=content_type,
        )

        return {
            "object_name": object_name,
            "filename": filename,
            "size": len(data),
            "url": f"/api/chat/files/{object_name}",
            "storage": "minio",
            "bucket": self._bucket_name,
        }

    def _upload_to_local(
        self,
        data: bytes,
        object_name: str,
        filename: str,
    ) -> dict[str, Any]:
        """上传到本地文件系统。"""
        file_path = self._local_root / object_name
        file_path.write_bytes(data)

        return {
            "object_name": object_name,
            "filename": filename,
            "size": len(data),
            "url": f"/api/chat/files/{object_name}",
            "storage": "local",
            "path": str(file_path),
        }

    def download_file(self, object_name: str) -> bytes | None:
        """从存储下载文件。"""
        if self.is_minio_available:
            try:
                response = self._minio_client.get_object(self._bucket_name, object_name)
                data = response.read()
                response.close()
                response.release_conn()
                return data
            except Exception as exc:
                logger.warning("MinIO 下载失败，尝试本地: %s", exc)

        # 本地下载
        file_path = self._local_root / object_name
        if file_path.is_file():
            return file_path.read_bytes()

        return None

    def get_file_path(self, object_name: str) -> Path | None:
        """获取本地文件路径（用于 FileResponse）。"""
        file_path = self._local_root / object_name
        if file_path.is_file():
            return file_path
        return None

    def list_files(self, prefix: str = "") -> list[dict[str, Any]]:
        """列出存储中的文件。"""
        if self.is_minio_available:
            try:
                objects = self._minio_client.list_objects(
                    self._bucket_name, prefix=prefix, recursive=True,
                )
                return [
                    {
                        "name": obj.object_name,
                        "size": obj.size,
                        "modified": str(obj.last_modified),
                        "storage": "minio",
                    }
                    for obj in objects
                ]
            except Exception:
                pass

        # 本地列表
        results = []
        for f in self._local_root.glob(f"{prefix}*"):
            if f.is_file():
                results.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": str(f.stat().st_mtime),
                    "storage": "local",
                })
        return results

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计。"""
        return {
            "storage_type": "minio" if self.is_minio_available else "local",
            "bucket": self._bucket_name if self.is_minio_available else None,
            "local_root": str(self._local_root),
        }


# 全局单例
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
