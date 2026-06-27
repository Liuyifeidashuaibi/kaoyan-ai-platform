"""
Agent 工具注册中心 — 商业级插件架构。

核心设计：
  1. 装饰器 @register_tool 自动注册工具，无需手动维护字典
  2. 从函数签名 + type hints 自动生成 OpenAI function-calling JSON Schema
  3. 工具可无限扩展：新业务只需写一个函数 + 装饰器即可接入
  4. 支持工具分类（文档/数据/搜索/代码），便于权限管控和UI分组
  5. 内置错误隔离：单个工具崩溃不影响其他工具

使用方式：
    from app.services.agent_tool_registry import register_tool, ToolContext

    @register_tool(
        name="my_tool",
        description="做某件事",
        category="document",
    )
    def my_tool(ctx: ToolContext, param1: str, param2: int = 0) -> dict:
        '''参数说明会自动提取到 schema description 中。'''
        return {"result": "done"}
"""

from __future__ import annotations

import inspect
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

logger = logging.getLogger(__name__)

# ── Python type → JSON Schema 类型映射 ──────────────────

_PY_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "Any": "string",
}


def _py_type_to_json(python_type: type | str) -> str:
    """将 Python 类型名映射到 JSON Schema 类型。"""
    type_str = python_type if isinstance(python_type, str) else getattr(python_type, "__name__", "str")
    return _PY_TYPE_MAP.get(type_str, "string")


def _extract_param_docs(docstring: str | None) -> dict[str, str]:
    """从 docstring 中提取参数说明（Args:/Parameters: 段落）。"""
    if not docstring:
        return {}
    result: dict[str, str] = {}
    in_args = False
    current_param = None
    current_desc: list[str] = []
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith(("args:", "parameters:", "params:", "参数:")):
            in_args = True
            continue
        if in_args:
            # 新参数行：param_name: description
            m = re.match(r"^(\w+)\s*[:：]\s*(.*)", stripped)
            if m:
                if current_param:
                    result[current_param] = " ".join(current_desc).strip()
                current_param = m.group(1)
                current_desc = [m.group(2)]
            elif stripped:
                current_desc.append(stripped)
            else:
                if current_param:
                    result[current_param] = " ".join(current_desc).strip()
                current_param = None
                current_desc = []
    if current_param:
        result[current_param] = " ".join(current_desc).strip()
    return result


def _build_schema_from_signature(
    func: Callable,
    name: str,
    description: str,
) -> dict[str, Any]:
    """
    从函数签名自动生成 OpenAI function-calling JSON Schema。

    支持 type hints + 默认值 + docstring 参数说明。
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
    param_docs = _extract_param_docs(func.__doc__)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("ctx", "context", "self"):
            continue  # 跳过上下文参数

        param_type = hints.get(param_name, str)
        json_type = _py_type_to_json(param_type)
        param_desc = param_docs.get(param_name, "")

        prop: dict[str, Any] = {"type": json_type, "description": param_desc or f"Parameter {param_name}"}

        # 枚举类型（Literal 或特定字符串）
        type_origin = getattr(param_type, "__origin__", None)
        if type_origin is not None:
            args = getattr(param_type, "__args__", [])
            if args and all(isinstance(a, str) for a in args):
                prop["enum"] = list(args)

        properties[param_name] = prop

        # 有默认值的参数不是 required
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required if required else [],
            },
        },
    }


# ── 工具上下文 ──────────────────────────────────────────


@dataclass
class ToolContext:
    """
    工具执行上下文 — 传递运行时信息给工具函数。

    工具函数可以通过 ctx 访问：
    - session_id: 当前会话ID
    - task_id: 当前 Agent 任务 ID（用于文件资产追踪）
    - file_name: 用户上传的文件名
    - user_id: 用户 ID
    - extra: 扩展数据
    """
    session_id: str = ""
    task_id: str = ""
    file_name: str | None = None
    user_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ── 注册中心 ────────────────────────────────────────────


@dataclass
class ToolEntry:
    """已注册工具的元数据。"""
    name: str
    description: str
    category: str
    func: Callable
    schema: dict[str, Any]
    max_retries: int = 2


class ToolRegistry:
    """工具注册中心 — 全局单例。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        description: str,
        category: str = "general",
        max_retries: int = 2,
    ) -> Callable:
        """
        装饰器：注册一个工具函数。

        参数:
            name: 工具唯一名称（与 LLM function name 一致）
            description: 工具描述（LLM 据此决定是否调用）
            category: 工具分类（document/data/search/code/utility）
            max_retries: 工具执行失败时的最大重试次数
        """
        def decorator(func: Callable) -> Callable:
            schema = _build_schema_from_signature(func, name, description)
            entry = ToolEntry(
                name=name,
                description=description,
                category=category,
                func=func,
                schema=schema,
                max_retries=max_retries,
            )
            self._tools[name] = entry
            logger.info("工具已注册: %s (category=%s)", name, category)
            return func

        return decorator

    def get(self, name: str) -> ToolEntry | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """返回所有已注册工具名。"""
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> list[ToolEntry]:
        """按分类过滤工具。"""
        return [e for e in self._tools.values() if e.category == category]

    def get_schemas(self, categories: list[str] | None = None) -> list[dict[str, Any]]:
        """
        返回 OpenAI function-calling 格式的工具定义列表。

        参数:
            categories: 只返回指定分类的工具，None 表示全部
        """
        if categories:
            return [e.schema for e in self._tools.values() if e.category in categories]
        return [e.schema for e in self._tools.values()]

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        ctx: ToolContext | None = None,
    ) -> dict[str, Any]:
        """
        执行指定工具，返回结果字典。

        内置错误隔离和重试机制：
        - 工具抛异常时，自动重试（最多 max_retries 次）
        - 所有重试都失败时，返回 {"error": ...} 而非崩溃
        """
        entry = self._tools.get(name)
        if entry is None:
            return {"error": f"未知工具: {name}"}

        ctx = ctx or ToolContext()
        last_error: str = ""

        for attempt in range(entry.max_retries + 1):
            try:
                # 检查函数签名是否接受 ctx 参数
                sig = inspect.signature(entry.func)
                kwargs = dict(args)
                if "ctx" in sig.parameters:
                    kwargs["ctx"] = ctx
                elif "context" in sig.parameters:
                    kwargs["context"] = ctx

                result = entry.func(**kwargs)

                # 确保返回 dict
                if isinstance(result, dict):
                    return result
                if isinstance(result, str):
                    return {"result": result}
                return {"result": str(result)}

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "工具 %s 第 %d/%d 次执行失败: %s",
                    name, attempt + 1, entry.max_retries + 1, exc,
                )
                if attempt < entry.max_retries:
                    import time
                    time.sleep(0.5 * (attempt + 1))  # 指数退避
                    continue

        return {"error": f"工具 {name} 执行失败（已重试 {entry.max_retries} 次）: {last_error}"}


# ── 全局单例 ────────────────────────────────────────────

_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心。"""
    return _registry


def register_tool(
    name: str,
    description: str,
    category: str = "general",
    max_retries: int = 2,
) -> Callable:
    """装饰器快捷方式。"""
    return _registry.register(name, description, category, max_retries)


def get_tool_schemas() -> list[dict[str, Any]]:
    """返回所有已注册工具的 OpenAI function-calling schema。"""
    return _registry.get_schemas()


def execute_tool(name: str, args: dict[str, Any], ctx: ToolContext | None = None) -> dict[str, Any]:
    """执行工具（兼容旧接口）。"""
    return _registry.execute(name, args, ctx)
