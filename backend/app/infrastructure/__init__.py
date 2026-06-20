"""
基础设施层 — Redis 缓存、Celery 异步任务。

与 chat / translator / schools / wrong-questions / community 核心业务解耦，
仅通过 Facade 与 Router 薄层接入，不修改各 Service 内部逻辑。
"""
