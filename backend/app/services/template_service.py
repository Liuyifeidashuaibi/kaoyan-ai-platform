"""
模板管理服务 — 商业级文档格式强约束引擎。

核心能力：
  1. 模板 CRUD：创建/读取/更新/删除模板（写 AgentTemplate 表）
  2. 向量化入库：模板 style_rules/validation_rules 向量化写入 Chroma 模板库
  3. 语义匹配：按文档类型+查询语义检索最佳匹配模板
  4. 文件入库：解析上传的模板文件（docx/pdf/txt），自动提取格式规则
  5. 格式校验：按模板 validation_rules 校验生成内容，返回不合格项清单

设计理念：
  - 模板是 Agent 输出版式统一的规则来源
  - 导出前必须检索匹配模板 → 按模板约束生成 → 校验不通过自动返工
  - 实现"AI 不能自由发挥，输出版式高度统一"的商用核心差异化
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.database import AgentTemplate, SessionLocal
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


class TemplateService:
    """
    模板管理服务 — AgentTemplate 表 CRUD + Chroma 向量化。

    写路径：先写 DB，再调 RAGService.ingest_template 向量化
    读路径：DB 查询（精确）/ RAG 语义检索（模糊匹配）
    """

    def __init__(self) -> None:
        self.rag = get_rag_service()

    def _db(self) -> Session:
        return SessionLocal()

    # ── CRUD ───────────────────────────────────────────────

    def create_template(
        self,
        name: str,
        category: str = "general",
        doc_type: str = "pdf",
        description: str = "",
        style_rules: dict | None = None,
        cover_format: dict | None = None,
        validation_rules: dict | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        """
        创建模板 — 写 DB + 向量化入库。

        Args:
            name: 模板名称（如"学术论文模板"）
            category: 分类（论文/报告/标书/报表…）
            doc_type: 文档类型 pdf/docx/xlsx/pptx
            style_rules: 样式规则（字体/字号/行距/标题层级）
            cover_format: 封面格式（字段与排版）
            validation_rules: 校验规则（必含章节/字数/结构）
            source_text: 模板原文（向量化用纯文本）
        """
        style_json = json.dumps(style_rules or {}, ensure_ascii=False)
        cover_json = json.dumps(cover_format or {}, ensure_ascii=False)
        validation_json = json.dumps(validation_rules or {}, ensure_ascii=False)

        db = self._db()
        try:
            tpl = AgentTemplate(
                name=name,
                category=category,
                doc_type=doc_type,
                description=description,
                style_rules=style_json,
                cover_format=cover_json,
                validation_rules=validation_json,
                source_text=source_text[:10000],
                is_active=True,
            )
            db.add(tpl)
            db.commit()
            db.refresh(tpl)
            template_id = tpl.id
        finally:
            db.close()

        # 向量化入库
        try:
            self.rag.ingest_template(
                template_id=template_id,
                name=name,
                category=category,
                doc_type=doc_type,
                style_rules=style_json,
                validation_rules=validation_json,
                source_text=source_text,
            )
            logger.info("模板已向量化入库: id=%d name=%s", template_id, name)
        except Exception as exc:
            logger.warning("模板向量化失败（DB已写入）: %s", exc)

        return self._to_dict(self._get_by_id(template_id))

    def update_template(
        self,
        template_id: int,
        **fields,
    ) -> dict[str, Any] | None:
        """
        更新模板 — 修改 DB + 重新向量化。

        支持更新字段: name, category, doc_type, description,
        style_rules(dict), cover_format(dict), validation_rules(dict),
        source_text(str), is_active(bool)
        """
        db = self._db()
        try:
            tpl = db.query(AgentTemplate).filter_by(id=template_id).first()
            if tpl is None:
                return None

            if "name" in fields:
                tpl.name = fields["name"]
            if "category" in fields:
                tpl.category = fields["category"]
            if "doc_type" in fields:
                tpl.doc_type = fields["doc_type"]
            if "description" in fields:
                tpl.description = fields["description"]
            if "style_rules" in fields:
                tpl.style_rules = json.dumps(fields["style_rules"], ensure_ascii=False)
            if "cover_format" in fields:
                tpl.cover_format = json.dumps(fields["cover_format"], ensure_ascii=False)
            if "validation_rules" in fields:
                tpl.validation_rules = json.dumps(fields["validation_rules"], ensure_ascii=False)
            if "source_text" in fields:
                tpl.source_text = (fields["source_text"] or "")[:10000]
            if "is_active" in fields:
                tpl.is_active = bool(fields["is_active"])

            db.commit()
            db.refresh(tpl)
            updated = self._to_dict(tpl)
        finally:
            db.close()

        # 重新向量化（删旧+插新）
        if updated and updated.get("is_active"):
            try:
                self.rag.ingest_template(
                    template_id=template_id,
                    name=updated["name"],
                    category=updated["category"],
                    doc_type=updated["doc_type"],
                    style_rules=updated["style_rules"],
                    validation_rules=updated["validation_rules"],
                    source_text=updated["source_text"],
                )
                logger.info("模板已重新向量化: id=%d", template_id)
            except Exception as exc:
                logger.warning("模板重新向量化失败: %s", exc)

        return updated

    def delete_template(self, template_id: int) -> bool:
        """删除模板（硬删除 DB 记录，向量库中残留片段不影响检索准确性）。"""
        db = self._db()
        try:
            tpl = db.query(AgentTemplate).filter_by(id=template_id).first()
            if tpl is None:
                return False
            db.delete(tpl)
            db.commit()
            logger.info("模板已删除: id=%d", template_id)
            return True
        finally:
            db.close()

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        """获取模板详情。"""
        tpl = self._get_by_id(template_id)
        return self._to_dict(tpl) if tpl else None

    def list_templates(
        self,
        category: str | None = None,
        doc_type: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """列出模板（支持按分类/文档类型过滤）。"""
        db = self._db()
        try:
            q = db.query(AgentTemplate)
            if active_only:
                q = q.filter(AgentTemplate.is_active == True)  # noqa: E712
            if category:
                q = q.filter(AgentTemplate.category == category)
            if doc_type:
                q = q.filter(AgentTemplate.doc_type == doc_type)
            q = q.order_by(AgentTemplate.created_at.desc())
            return [self._to_dict(t) for t in q.all()]
        finally:
            db.close()

    # ── 语义匹配 ───────────────────────────────────────────

    def match_template(
        self,
        doc_type: str,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        按文档类型+查询语义匹配模板。

        先从向量库检索候选，再用 template_id 回查 DB 补全完整规则。
        """
        candidates = self.rag.retrieve_templates(
            query=query,
            doc_type=doc_type,
            top_k=top_k,
        )
        if not candidates:
            # 向量库无结果时降级为 DB 精确匹配
            return self.list_templates(doc_type=doc_type)

        # 用 template_id 回查 DB 补全完整 style_rules / validation_rules
        results: list[dict[str, Any]] = []
        for c in candidates:
            tid_str = c.get("template_id", "")
            if not tid_str:
                continue
            try:
                tid = int(tid_str)
            except (ValueError, TypeError):
                continue
            full = self.get_template(tid)
            if full and full.get("is_active"):
                full["match_snippet"] = c.get("snippet", "")
                results.append(full)
        return results

    # ── 文件入库 ───────────────────────────────────────────

    def ingest_template_file(
        self,
        file_path: str,
        name: str,
        category: str = "general",
        doc_type: str = "pdf",
    ) -> dict[str, Any]:
        """
        解析上传的模板文件，提取文本内容，创建模板。

        使用 DocumentParser（Unstructured 引擎）解析文件。
        提取的纯文本作为 source_text 存入 DB + 向量化。
        """
        import pathlib

        from app.services.agent_document_parser import get_document_parser

        safe_name = pathlib.Path(file_path).name
        candidates = [
            pathlib.Path(file_path),
        ]
        # 尝试在 uploads/chat/ 下查找
        from app.config import get_settings
        settings = get_settings()
        chat_dir = settings.upload_path.parent / "chat"
        candidates.append(chat_dir / safe_name)

        resolved = None
        for c in candidates:
            if c.is_file():
                resolved = c
                break

        if resolved is None:
            return {"error": f"模板文件不存在: {file_path}"}

        parser = get_document_parser()
        result = parser.parse(resolved, max_chars=15000)

        if "error" in result:
            return result

        source_text = result.get("text", "") or result.get("content", "")

        return self.create_template(
            name=name,
            category=category,
            doc_type=doc_type,
            description=f"从文件 {safe_name} 导入",
            source_text=source_text,
        )

    # ── 格式校验 ───────────────────────────────────────────

    def validate_content(
        self,
        content: str,
        template_id: int,
    ) -> dict[str, Any]:
        """
        按模板 validation_rules 校验生成内容。

        返回:
            {
                "passed": bool,
                "checks": [{"rule": str, "passed": bool, "message": str}],
                "failed_count": int,
                "summary": str,
            }
        """
        tpl = self.get_template(template_id)
        if tpl is None:
            return {"error": f"模板不存在: {template_id}"}

        rules = tpl.get("validation_rules", {})
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
            except json.JSONDecodeError:
                rules = {}

        if not rules:
            return {
                "passed": True,
                "checks": [],
                "failed_count": 0,
                "summary": "模板无校验规则，自动通过",
            }

        checks: list[dict[str, Any]] = []

        # ── 必含章节检查 ──
        required_sections = rules.get("required_sections", [])
        for section in required_sections:
            found = section.lower() in content.lower()
            checks.append({
                "rule": f"必含章节: {section}",
                "passed": found,
                "message": "" if found else f"缺少必含章节: {section}",
            })

        # ── 最低字数检查 ──
        min_chars = rules.get("min_chars", 0)
        if min_chars > 0:
            actual = len(content.replace(" ", "").replace("\n", ""))
            passed = actual >= min_chars
            checks.append({
                "rule": f"最低字数: {min_chars}",
                "passed": passed,
                "message": "" if passed else f"字数不足: {actual}/{min_chars}",
            })

        # ── 最高字数检查 ──
        max_chars = rules.get("max_chars", 0)
        if max_chars > 0:
            actual = len(content.replace(" ", "").replace("\n", ""))
            passed = actual <= max_chars
            checks.append({
                "rule": f"最高字数: {max_chars}",
                "passed": passed,
                "message": "" if passed else f"字数超限: {actual}/{max_chars}",
            })

        # ── 必含关键词检查 ──
        required_keywords = rules.get("required_keywords", [])
        for kw in required_keywords:
            found = kw.lower() in content.lower()
            checks.append({
                "rule": f"必含关键词: {kw}",
                "passed": found,
                "message": "" if found else f"缺少关键词: {kw}",
            })

        # ── 标题层级检查 ──
        required_headings = rules.get("required_heading_levels", [])
        for level in required_headings:
            marker = "#" * int(level)
            found = marker + " " in content
            checks.append({
                "rule": f"标题层级: H{level}",
                "passed": found,
                "message": "" if found else f"缺少 H{level} 级标题",
            })

        # ── 自定义正则检查 ──
        custom_checks = rules.get("custom_checks", [])
        for cc in custom_checks:
            import re
            pattern = cc.get("pattern", "")
            desc = cc.get("description", pattern)
            if pattern:
                try:
                    found = bool(re.search(pattern, content))
                    checks.append({
                        "rule": f"自定义: {desc}",
                        "passed": found,
                        "message": "" if found else f"自定义校验未通过: {desc}",
                    })
                except re.error:
                    checks.append({
                        "rule": f"自定义: {desc}",
                        "passed": True,
                        "message": f"正则无效，跳过: {pattern}",
                    })

        failed = [c for c in checks if not c["passed"]]
        return {
            "passed": len(failed) == 0,
            "checks": checks,
            "failed_count": len(failed),
            "summary": f"校验完成: {len(checks)} 项检查，{len(failed)} 项未通过",
        }

    # ── 内部辅助 ───────────────────────────────────────────

    def _get_by_id(self, template_id: int) -> AgentTemplate | None:
        db = self._db()
        try:
            return db.query(AgentTemplate).filter_by(id=template_id).first()
        finally:
            db.close()

    @staticmethod
    def _to_dict(tpl: AgentTemplate) -> dict[str, Any]:
        return {
            "id": tpl.id,
            "name": tpl.name,
            "category": tpl.category,
            "doc_type": tpl.doc_type,
            "description": tpl.description or "",
            "style_rules": tpl.style_rules or "{}",
            "cover_format": tpl.cover_format or "{}",
            "validation_rules": tpl.validation_rules or "{}",
            "source_text": (tpl.source_text or "")[:500],
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else "",
            "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else "",
        }


# ── 全局单例 ────────────────────────────────────────────

_template_service: TemplateService | None = None


def get_template_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service

