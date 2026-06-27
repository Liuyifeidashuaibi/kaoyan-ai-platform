"""
Agent 工具集 — 商业级通用任务工具。

使用 @register_tool 装饰器注册，自动生成 OpenAI function-calling schema。
新增工具只需写函数 + 装饰器，无需修改任何其他文件。

工具分类：
  - document: 文档读取与导出（read_document, export_document, export_excel, format_document）
  - data:     数据处理与分析（analyze_data, clean_data, convert_format）
  - search:   知识检索（search_knowledge, web_search）
  - system:   系统功能（create_task_plan）

商业级集成：
  - DocumentParser: Unstructured 文档解析（多格式 + 表格提取 + 编码检测）
  - StorageService: MinIO 对象存储（文件上传/下载 + 本地降级）
  - 容错重试: 每个工具可配置 max_retries，失败自动重试
"""

from __future__ import annotations

import csv
import io
import json
import logging
import pathlib
import re
from typing import Any

from app.config import get_settings
from app.services.agent_document_parser import get_document_parser
from app.services.agent_storage_service import get_storage_service
from app.services.agent_tool_registry import (
    ToolContext,
    execute_tool,
    get_tool_schemas,
    register_tool,
)
from app.services.export_attachment_service import build_attachment, build_excel
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

# ── 文档工具 ────────────────────────────────────────────


@register_tool(
    name="read_document",
    description=(
        "读取用户上传的文档文件，提取文本内容和结构信息。"
        "支持 docx、pdf、txt、md、csv 格式。"
        "使用 Unstructured 引擎解析，自动提取标题层级、表格、列表等结构。"
        "当用户上传了文件并要求基于文件内容生成时，先调用此工具。"
    ),
    category="document",
    max_retries=1,
)
def _read_document(
    file_path: str,
    ctx: ToolContext,
) -> dict[str, Any]:
    """
    读取上传的文档文件。

    Args:
        file_path: 用户上传时附带的文件名
        ctx: 工具执行上下文（自动注入）
    """
    if not file_path.strip():
        return {"error": "文件路径为空"}

    settings = get_settings()
    chat_dir = settings.upload_path.parent / "chat"

    safe_name = pathlib.Path(file_path).name
    candidates = [
        chat_dir / safe_name,
        chat_dir / file_path,
        pathlib.Path(file_path),
    ]

    resolved: pathlib.Path | None = None
    for c in candidates:
        try:
            if c.is_file():
                resolved = c
                break
        except Exception:
            continue

    if resolved is None or not resolved.is_file():
        return {"error": f"文件不存在: {file_path}"}

    # 使用商业级文档解析器（Unstructured + 降级方案）
    parser = get_document_parser()
    result = parser.parse(resolved, max_chars=15000)

    if "error" in result:
        return result

    result["file_path"] = str(resolved)
    return result


@register_tool(
    name="export_document",
    description=(
        "将内容导出为 PDF / DOCX / TXT / PPTX 文件并返回下载链接。"
        "PDF 和 DOCX 自动生成封面页（标题+作者信息+日期）和页码。"
        "PPTX 自动生成标题幻灯片+内容幻灯片（Markdown ## 转为幻灯片标题）。"
        "文件自动上传到 MinIO 对象存储（或本地降级），返回永久下载链接。"
        "用户要求生成文件、导出文档、下载论文时调用此工具。"
    ),
    category="document",
    max_retries=2,
)
def _export_document(
    content: str,
    title: str,
    format: str = "pdf",
    author_info: str = "",
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    """
    导出文档为文件。

    Args:
        content: 文档正文内容（Markdown 或纯文本，不含封面信息）
        title: 文档标题（显示在封面页和文件名）
        format: 导出格式 pdf / docx / txt / pptx
        author_info: 封面作者信息，每行一项（如"姓名：张三\n学号：20240001"）
        ctx: 工具上下文（自动注入，用于文件资产追踪）
    """
    if not content.strip():
        return {"error": "内容为空，无法导出"}

    try:
        file_bytes, filename, mime = build_attachment(content, format, title, author_info)
    except Exception as exc:
        logger.error("导出失败: %s", exc, exc_info=True)
        return {"error": f"导出失败: {exc}"}

    # 使用商业级存储服务（MinIO + 本地降级 + 文件资产记录）
    storage = get_storage_service()
    upload = storage.upload_file(
        data=file_bytes,
        filename=filename,
        content_type=mime,
        task_id=ctx.task_id if ctx else None,
        title=title,
        format=format,
    )

    return {
        "filename": upload["filename"],
        "file_url": upload["url"],
        "file_path": upload.get("object_name", ""),
        "file_size": upload["size"],
        "format": format,
        "title": title,
        "storage": upload.get("storage", "local"),
    }


@register_tool(
    name="export_excel",
    description=(
        "将表格数据导出为 Excel (.xlsx) 文件并返回下载链接。"
        "支持多 sheet、表头样式、冻结首行、自动列宽。"
        "文件自动上传到 MinIO 对象存储（或本地降级）。"
        "用户要求生成表格、报表、数据表时调用此工具。"
    ),
    category="document",
    max_retries=2,
)
def _export_excel(
    title: str,
    sheets: str,
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    """
    导出 Excel 文件。

    Args:
        title: 文件标题（用于文件名）
        sheets: JSON 字符串，定义多个工作表。
            格式: [{"name": "Sheet1", "headers": ["列1","列2"], "rows": [["a","b"],["c","d"]]}]
            每个元素包含: name(工作表名), headers(列头列表), rows(数据行列表)
        ctx: 工具上下文（自动注入，用于文件资产追踪）
    """
    if not sheets.strip():
        return {"error": "工作表数据为空"}

    try:
        sheets_data = json.loads(sheets) if isinstance(sheets, str) else sheets
    except json.JSONDecodeError as exc:
        return {"error": f"sheets JSON 格式错误: {exc}"}

    if not isinstance(sheets_data, list) or not sheets_data:
        return {"error": "sheets 必须是非空数组"}

    try:
        file_bytes, filename = build_excel(sheets_data, title)
    except Exception as exc:
        logger.error("Excel 导出失败: %s", exc, exc_info=True)
        return {"error": f"Excel 导出失败: {exc}"}

    # 使用商业级存储服务（MinIO + 本地降级 + 文件资产记录）
    storage = get_storage_service()
    upload = storage.upload_file(
        data=file_bytes,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        task_id=ctx.task_id if ctx else None,
        title=title,
        format="xlsx",
    )

    return {
        "filename": upload["filename"],
        "file_url": upload["url"],
        "file_path": upload.get("object_name", ""),
        "file_size": upload["size"],
        "format": "xlsx",
        "title": title,
        "sheets_count": len(sheets_data),
        "storage": upload.get("storage", "local"),
    }


@register_tool(
    name="format_document",
    description=(
        "格式化 Markdown 文档：统一标题层级、修复列表格式、添加段落间距。"
        "支持学术、商业、日常三种风格。"
        "生成内容后、导出前调用此工具进行格式规范化。"
    ),
    category="document",
    max_retries=0,
)
def _format_document(
    content: str,
    style: str = "academic",
) -> dict[str, Any]:
    """
    格式化 Markdown 文档。

    Args:
        content: Markdown 文档内容
        style: 格式风格: academic(学术) / business(商业) / casual(日常)
    """
    if not content.strip():
        return {"error": "内容为空"}

    lines = content.split("\n")
    formatted: list[str] = []

    for line in lines:
        # 修复标题格式：确保 # 后有空格
        if re.match(r"^#{1,6}[^#\s]", line):
            line = re.sub(r"^(#{1,6})", r"\1 ", line)

        # 修复列表格式：确保 - 后有空格
        if re.match(r"^-\S", line):
            line = re.sub(r"^-", "- ", line)

        # 修复数字列表：确保 . 后有空格
        if re.match(r"^\d+\.\S", line):
            line = re.sub(r"^(\d+\.)", r"\1 ", line)

        # 学术风格：段落后添加空行
        if style == "academic":
            if line.strip() and not line.startswith("#") and not line.startswith("-"):
                if formatted and formatted[-1].strip() and not formatted[-1].startswith("#") and not formatted[-1].startswith("-"):
                    formatted.append("")

        formatted.append(line)

    result = "\n".join(formatted)
    # 清理多余空行（最多连续2个）
    result = re.sub(r"\n{3,}", "\n\n", result)
    # 确保文件末尾有换行
    result = result.rstrip() + "\n"

    return {
        "formatted_content": result,
        "original_length": len(content),
        "formatted_length": len(result),
        "style": style,
        "summary": f"文档已格式化（{style} 风格，{len(content)} → {len(result)} 字符）",
    }


# ── 数据工具 ────────────────────────────────────────────


@register_tool(
    name="analyze_data",
    description=(
        "对 CSV/表格文本数据进行统计分析，返回汇总结果。"
        "支持计算均值、总和、最大/最小值、计数等。"
        "当用户要求数据分析、统计汇总时调用此工具。"
    ),
    category="data",
    max_retries=1,
)
def _analyze_data(
    data: str,
    operation: str = "summary",
) -> dict[str, Any]:
    """
    分析表格数据。

    Args:
        data: CSV 格式数据（第一行为列头，后续为数据行）
        operation: 分析类型 summary / count / stats
    """
    if not data.strip():
        return {"error": "数据为空"}

    try:
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
    except Exception as exc:
        return {"error": f"CSV 解析失败: {exc}"}

    if len(rows) < 2:
        return {"error": "数据行不足（至少需要列头 + 1 行数据）"}

    headers = rows[0]
    data_rows = rows[1:]

    result: dict[str, Any] = {
        "headers": headers,
        "row_count": len(data_rows),
        "col_count": len(headers),
    }

    if operation == "summary":
        col_stats: list[dict] = []
        for col_idx, header in enumerate(headers):
            values: list[str] = []
            for row in data_rows:
                if col_idx < len(row):
                    values.append(row[col_idx])

            nums: list[float] = []
            for v in values:
                try:
                    nums.append(float(v))
                except (ValueError, TypeError):
                    pass

            stats: dict[str, Any] = {"column": header, "type": "text", "count": len(values)}
            if nums and len(nums) == len(values):
                stats.update({
                    "type": "number",
                    "sum": round(sum(nums), 2),
                    "mean": round(sum(nums) / len(nums), 2),
                    "min": min(nums),
                    "max": max(nums),
                })
            col_stats.append(stats)

        result["columns"] = col_stats
        result["summary"] = f"共 {len(data_rows)} 行 × {len(headers)} 列"

    elif operation == "count":
        from collections import Counter
        first_col = [row[0] if row else "" for row in data_rows]
        counts = Counter(first_col)
        result["groups"] = dict(counts.most_common(20))
        result["summary"] = f"按第一列分组，共 {len(counts)} 组"

    else:
        result["summary"] = f"共 {len(data_rows)} 行 × {len(headers)} 列"

    return result


@register_tool(
    name="clean_data",
    description=(
        "清洗 CSV/表格数据：去重、处理缺失值、文本修剪、格式标准化。"
        "当用户数据质量不高、需要预处理时调用此工具。"
    ),
    category="data",
    max_retries=1,
)
def _clean_data(
    data: str,
    operations: str = "deduplicate,fill_missing,trim",
) -> dict[str, Any]:
    """
    清洗表格数据。

    Args:
        data: CSV 格式数据（第一行为列头）
        operations: 清洗操作(逗号分隔): deduplicate(去重) / fill_missing(填充缺失) / trim(修剪空白) / normalize(标准化)
    """
    if not data.strip():
        return {"error": "数据为空"}

    try:
        import pandas as pd
        df = pd.read_csv(io.StringIO(data))
    except Exception as exc:
        return {"error": f"CSV 解析失败: {exc}"}

    ops = [o.strip() for o in operations.split(",")]
    changes: list[str] = []
    original_rows = len(df)

    if "deduplicate" in ops:
        before = len(df)
        df = df.drop_duplicates()
        if before != len(df):
            changes.append(f"去重: 移除 {before - len(df)} 行")

    if "fill_missing" in ops:
        filled = 0
        for col in df.columns:
            if df[col].isnull().any():
                if df[col].dtype in ("int64", "float64"):
                    df[col] = df[col].fillna(0)
                else:
                    df[col] = df[col].fillna("")
                filled += 1
        if filled:
            changes.append(f"缺失值已填充（{filled} 列）")

    if "trim" in ops:
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.strip()
        changes.append("文本已修剪空白")

    if "normalize" in ops:
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.replace(r"\s+", " ", regex=True)
        changes.append("空白已标准化")

    output = io.StringIO()
    df.to_csv(output, index=False)
    cleaned = output.getvalue()

    return {
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "operations": ops,
        "changes": changes,
        "cleaned_data": cleaned,
        "summary": f"清洗完成: {original_rows} → {len(df)} 行",
    }


@register_tool(
    name="convert_format",
    description=(
        "格式转换：CSV ↔ Markdown 表格、JSON ↔ CSV 等。"
        "当用户需要将数据从一种格式转为另一种格式时调用。"
    ),
    category="data",
    max_retries=0,
)
def _convert_format(
    data: str,
    from_format: str,
    to_format: str,
) -> dict[str, Any]:
    """
    格式转换。

    Args:
        data: 原始数据内容
        from_format: 源格式: csv / json / markdown
        to_format: 目标格式: csv / json / markdown
    """
    # 解析输入
    rows: list[list[str]] = []
    if from_format == "csv":
        reader = csv.reader(io.StringIO(data))
        rows = [list(r) for r in reader]
    elif from_format == "json":
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            return {"error": f"JSON 解析失败: {exc}"}
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            headers = list(parsed[0].keys())
            rows = [headers] + [[str(item.get(h, "")) for h in headers] for item in parsed]
        else:
            return {"error": "JSON 格式不支持：需要对象数组"}
    elif from_format == "markdown":
        for line in data.split("\n"):
            if line.startswith("|"):
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if cells and not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
    else:
        return {"error": f"不支持的源格式: {from_format}"}

    if not rows:
        return {"error": "解析后无数据"}

    # 转换为目标格式
    if to_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
        result = output.getvalue()
    elif to_format == "json":
        headers = rows[0]
        result = json.dumps(
            [dict(zip(headers, row)) for row in rows[1:]],
            ensure_ascii=False, indent=2,
        )
    elif to_format == "markdown":
        headers = rows[0]
        result = "| " + " | ".join(headers) + " |\n"
        result += "|" + "|".join(["---" for _ in headers]) + "|\n"
        for row in rows[1:]:
            result += "| " + " | ".join(row) + " |\n"
    else:
        return {"error": f"不支持的目标格式: {to_format}"}

    return {
        "converted_data": result,
        "from_format": from_format,
        "to_format": to_format,
        "rows_count": len(rows) - 1,
        "summary": f"已将 {from_format} 转换为 {to_format}（{len(rows) - 1} 行数据）",
    }


# ── 搜索工具 ────────────────────────────────────────────


@register_tool(
    name="search_knowledge",
    description=(
        "从知识库检索参考资料（错题本、院校数据、公共考研资料）。"
        "需要引用已有知识、查找参考信息时调用。"
    ),
    category="search",
    max_retries=1,
)
def _search_knowledge(query: str) -> dict[str, Any]:
    """
    检索知识库。

    Args:
        query: 检索关键词或问题
    """
    if not query.strip():
        return {"error": "检索关键词为空"}

    try:
        rag = get_rag_service()
        context = rag.retrieve(query)
    except Exception as exc:
        logger.error("知识库检索失败: %s", exc)
        return {"error": f"检索失败: {exc}"}

    if not context:
        return {"results": "", "summary": "未找到相关参考资料"}

    return {
        "results": context,
        "char_count": len(context),
        "summary": f"找到相关参考资料（{len(context)} 字符）",
    }


@register_tool(
    name="web_search",
    description=(
        "搜索互联网获取参考信息。支持学术资料、新闻、技术文档等。"
        "当知识库中没有相关信息、需要联网查找时调用此工具。"
    ),
    category="search",
    max_retries=2,
)
def _web_search(
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    联网搜索。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数量
    """
    if not query.strip():
        return {"error": "搜索关键词为空"}

    try:
        import httpx
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return {"error": f"联网搜索失败: {exc}"}

    results: list[dict] = []

    # DuckDuckGo Instant Answer
    if data.get("AbstractText"):
        results.append({
            "title": data.get("Heading", query),
            "content": data.get("AbstractText", ""),
            "source": data.get("AbstractURL", ""),
        })

    # 相关主题
    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({
                "title": topic["Text"][:80],
                "content": topic["Text"],
                "source": topic.get("FirstURL", ""),
            })
        elif isinstance(topic, dict) and topic.get("Topics"):
            for sub in topic["Topics"]:
                if len(results) >= max_results:
                    break
                if sub.get("Text"):
                    results.append({
                        "title": sub["Text"][:80],
                        "content": sub["Text"],
                        "source": sub.get("FirstURL", ""),
                    })

    if not results:
        return {
            "query": query,
            "results": [],
            "count": 0,
            "summary": "未找到相关结果，建议换用更具体的关键词",
        }

    return {
        "query": query,
        "results": results[:max_results],
        "count": len(results[:max_results]),
        "summary": f"找到 {len(results[:max_results])} 条相关结果",
    }


# ── 模板工具 ────────────────────────────────────────────


@register_tool(
    name="search_template",
    description=(
        "检索文档/行业模板与格式规范。"
        "当用户要求生成特定类型的文档（论文、报告、标书等）时，先调用此工具获取格式约束。"
        "返回模板的样式规则、封面格式、校验规则等。"
        "导出文档前必须先调用此工具检索匹配模板，按模板约束生成内容。"
    ),
    category="search",
    max_retries=1,
)
def _search_template(
    doc_type: str,
    query: str,
) -> dict[str, Any]:
    """
    检索匹配模板。

    Args:
        doc_type: 文档类型 pdf/docx/xlsx/pptx
        query: 检索关键词（如"学术论文"、"毕业论文"、"项目报告"）
    """
    if not query.strip():
        return {"error": "检索关键词为空"}

    try:
        from app.services.template_service import get_template_service

        svc = get_template_service()
        matches = svc.match_template(doc_type=doc_type, query=query, top_k=3)
    except Exception as exc:
        logger.error("模板检索失败: %s", exc)
        return {"error": f"模板检索失败: {exc}"}

    if not matches:
        return {
            "results": [],
            "count": 0,
            "summary": f"未找到 {doc_type} 类型匹配模板，可自由生成",
        }

    # 精简返回（避免过长的 source_text 占用上下文）
    results = [
        {
            "template_id": m.get("id"),
            "name": m.get("name", ""),
            "category": m.get("category", ""),
            "doc_type": m.get("doc_type", ""),
            "style_rules": m.get("style_rules", "{}"),
            "cover_format": m.get("cover_format", "{}"),
            "validation_rules": m.get("validation_rules", "{}"),
        }
        for m in matches
    ]

    return {
        "results": results,
        "count": len(results),
        "summary": f"找到 {len(results)} 个匹配模板，请按模板 style_rules 约束生成内容",
    }


@register_tool(
    name="validate_format",
    description=(
        "按模板校验规则检查生成内容的格式合规性。"
        "在导出文件前调用此工具，确保内容符合模板要求。"
        "校验不通过时返回不合格项清单，应根据清单修正内容后重新校验。"
        "导出前必须调用此工具校验，不合格需返工修正。"
    ),
    category="document",
    max_retries=0,
)
def _validate_format(
    content: str,
    template_id: int,
) -> dict[str, Any]:
    """
    校验内容格式。

    Args:
        content: 待校验的文档内容（Markdown 或纯文本）
        template_id: 模板ID（从 search_template 结果获取）
    """
    if not content.strip():
        return {"error": "内容为空，无法校验"}

    try:
        from app.services.template_service import get_template_service

        svc = get_template_service()
        result = svc.validate_content(content=content, template_id=template_id)
    except Exception as exc:
        logger.error("格式校验失败: %s", exc)
        return {"error": f"格式校验失败: {exc}"}

    return result


# ── 系统工具 ────────────────────────────────────────────


@register_tool(
    name="create_task_plan",
    description=(
        "为复杂任务创建分步执行计划。"
        "当任务涉及多步骤、多文件、需要先后顺序时，先调用此工具规划。"
        "规划后按步骤逐步执行，每步完成后进入下一步。"
    ),
    category="system",
    max_retries=0,
)
def _create_task_plan(
    task_description: str,
    steps: str,
) -> dict[str, Any]:
    """
    创建任务执行计划。

    Args:
        task_description: 任务总体描述
        steps: JSON 数组字符串，每个元素包含 step(步骤号)、action(动作描述)、tool(建议工具)、details(详情)
            格式: [{"step":1,"action":"读取文件","tool":"read_document","details":"读取用户上传的模板"},...]
    """
    if not task_description.strip():
        return {"error": "任务描述为空"}

    try:
        steps_data = json.loads(steps) if isinstance(steps, str) else steps
    except json.JSONDecodeError:
        steps_data = [{"step": 1, "action": steps, "tool": "", "details": ""}]

    if not isinstance(steps_data, list):
        steps_data = [steps_data]

    return {
        "plan_created": True,
        "task": task_description,
        "total_steps": len(steps_data),
        "steps": steps_data,
        "summary": f"已创建 {len(steps_data)} 步执行计划",
    }


# ── 兼容性导出 ────────────────────────────────────────────

__all__ = [
    "execute_tool",
    "get_tool_schemas",
    "ToolContext",
]
