"""
Agent 模式服务 — 商业级 LangGraph StateGraph 状态机引擎。

架构升级（基于 LangGraph StateGraph 真实图引擎）：
  1. LangGraph StateGraph 替代手写 for 循环
     - 节点：think → execute_tools → validate → rework
     - 条件边：route_after_think / route_after_tools / route_after_validate
     - 循环控制：ReAct 循环由图边控制，最大 15 轮
     - 状态持久化：MemorySaver checkpointer + Redis 状态存储
  2. LiteLLM 统一模型接入
     - 多模型负载均衡 + 自动重试 + 模型降级
  3. asyncio.Queue SSE 桥接
     - 图节点内的事件实时推入队列，主生成器排空队列 yield SSE
     - 保留 token 级流式体验，前端零改动
  4. 全链路日志
     - 每步思考、工具调用、结果全部记录到 Postgres

图结构：
  START → think → route_after_think
  route_after_think → execute_tools (有工具调用)
  route_after_think → END (无工具调用 / 达到最大轮次 / 失败)
  execute_tools → route_after_tools
  route_after_tools → validate (导出文件 & 有匹配模板)
  route_after_tools → think (无需校验)
  validate → route_after_validate
  route_after_validate → rework (校验不通过 & 未达返工上限)
  route_after_validate → think (校验通过 / 达到返工上限)
  rework → think

SSE 事件类型：
  - thinking: Agent 正在思考
  - token:    流式文本
  - step:     工具调用步骤
  - file:     文件下载信息
  - validate: 格式校验结果
  - rework:   返工通知
  - done:     任务完成
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, TypedDict

from app.config import get_settings
from app.services.agent_llm_service import get_llm_service
from app.services.agent_state_store import get_state_store
from app.services.agent_storage_service import get_storage_service
from app.services.agent_task_logger import get_task_logger
import app.services.agent_tools  # noqa: F401 — 触发 @register_tool 装饰器注册所有工具
from app.services.agent_tool_registry import ToolContext, execute_tool, get_tool_schemas

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 15
MAX_REWORKS = 2
# LangGraph 递归上限：每轮最多 4 节点(think→tools→validate→rework) × 15 轮 + 余量
GRAPH_RECURSION_LIMIT = 80


def _safe_json_arguments(args_str: str) -> str:
    """确保工具调用参数是合法 JSON 字符串。"""
    args_str = (args_str or "").strip()
    if not args_str:
        return "{}"
    try:
        json.loads(args_str)
        return args_str
    except json.JSONDecodeError:
        pass
    first_brace = args_str.find("{")
    last_brace = args_str.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        fragment = args_str[first_brace : last_brace + 1]
        try:
            json.loads(fragment)
            return fragment
        except json.JSONDecodeError:
            pass
    if ":" in args_str and not args_str.startswith("{"):
        candidate = "{" + args_str + "}"
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    return json.dumps({"raw_input": args_str}, ensure_ascii=False)


# ── LangGraph 状态定义 ──────────────────────────────────


class AgentState(TypedDict, total=False):
    """LangGraph 状态机状态 — 贯穿 think/tools/validate/rework 节点。"""

    messages: list[dict]           # LLM 消息历史
    round_idx: int                 # 当前 ReAct 轮次
    full_content: str              # 当前轮 LLM 输出内容
    tool_calls: list[dict]         # 当前轮工具调用
    tool_results: list[dict]       # 工具执行结果
    files_generated: list[dict]    # 生成的文件（跨轮累积）
    exported_content: str          # 导出工具传入的内容（供 validate 校验）
    exported_format: str           # 导出文件格式
    template_id: int | None        # 匹配的模板 ID（跨轮追踪）
    validation_result: dict        # 最近一次校验结果
    rework_count: int              # 返工次数
    needs_validation: bool         # 是否需要走 validate 节点
    final_output: str              # 最终输出
    status: str                    # running / completed / failed
    error: str                     # 错误信息
    task_id: str                   # 任务 ID
    session_id: str                # 会话 ID
    file_name: str | None          # 上传文件名


# ── 系统提示词 ──────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """你是考研学习 Agent — 一个商业级通用任务执行型 AI 助手。
你能够自主解析用户需求、规划任务步骤、调用工具执行复杂业务链路，生成可交付的专业成果。

## 核心能力

1. **学术内容创作**
   - 政治论述题、材料分析题解答（含原理引用、逻辑展开）
   - 英语大作文、小作文（含模板、高级词汇、长难句）
   - 专业课论文、读书报告、文献综述
   - 数学知识点讲解、解题步骤示范

2. **学习规划与总结**
   - 分阶段复习计划（基础/强化/冲刺，精确到周）
   - 知识点思维导图、章节提纲
   - 易错点归纳、重难点清单

3. **文档处理**
   - 读取用户上传的 docx/pdf/txt/csv 文件（Unstructured 引擎解析）
   - 导出 PDF/DOCX/TXT/Excel/PPT 文件（自动封面+页码+排版）
   - 格式化文档（统一标题层级、修复列表格式、段落间距）
   - 数据清洗（去重、缺失值处理、格式标准化）
   - 格式转换（CSV ↔ Markdown ↔ JSON）

4. **知识检索与联网搜索**
   - 从知识库检索参考资料（错题本、院校数据、公共资料）
   - 联网搜索获取互联网参考信息（学术资料、新闻、技术文档）

## 严格执行的信息确认流程（最重要）

当用户要求生成以下类型的文档时，你**必须先询问缺失信息**，收到用户回复后才开始生成。
**绝不自行编造姓名、学号等个人信息。**

### 论文/报告/作业类
必须确认以下信息后才能开始生成：
- 姓名、学号、学校、学院、班级、专业
- 指导老师（如适用）、字数要求、格式要求

### 学习计划类
必须确认：当前复习阶段、目标院校/专业、可用时间、薄弱科目

### 询问方式
用简洁的问题列表一次性询问所有缺失信息，例如：
"好的，我可以帮你生成这篇论文。在此之前，我需要确认以下信息：
1. 姓名
2. 学号
3. 学校
4. 学院/专业
5. 班级
6. 字数要求
请提供以上信息，我将为你生成完整的论文。"

## 工作流程

1. **理解需求**：明确任务类型、主题、字数、格式要求
2. **检查信息**：如缺少姓名/学号/学校等必要信息，先询问用户
3. **读取文件**（如有上传）：调用 read_document 工具读取文件内容
4. **规划结构**：长文档（>500字）先构思大纲，在回复中展示大纲
5. **检索模板**：生成文档前调用 search_template 工具检索匹配模板（如有）
6. **生成内容**：逐段展开，保证专业性和学术规范，按模板 style_rules 约束格式
7. **格式校验**：导出前调用 validate_format 工具校验内容合规性，不通过则返工
8. **导出文件**：用户要求"生成文件/导出/下载"时，调用 export_document 工具
   - 传入 title（标题）、content（正文）、format（格式）、author_info（封面信息）
9. **引用参考**：需要参考资料时，调用 search_knowledge 工具
10. **联网搜索**：知识库无相关信息时，调用 web_search 工具
11. **数据清洗**：数据质量不高时，调用 clean_data 工具预处理
12. **格式转换**：需要转换数据格式时，调用 convert_format 工具
13. **文档格式化**：导出前可调用 format_document 工具规范化格式

## 读取上传文件

- 如果用户消息中包含 [附件文件: xxx]，说明用户上传了文件
- **必须先调用 read_document 工具读取文件内容**，理解格式要求后再生成
- 严格按照文件中的格式要求生成内容

## 导出文档

- 调用 export_document 工具时，**必须传入 author_info 参数**
- author_info 格式：每行一项，如 `姓名：张三\n学号：20240001\n学校：北京大学`
- content 参数只传正文内容（不含封面信息），封面由系统自动生成
- 支持格式：pdf / docx / txt / pptx

## 导出 Excel

- 当用户要求生成表格、报表、数据表时，调用 export_excel 工具
- sheets 参数是 JSON 字符串

## 模板格式约束（导出前必做 — 硬约束）

当用户要求生成文档（论文、报告、标书等）时，**必须**按以下流程执行：

1. **检索模板**：生成前先调用 `search_template` 工具，传入 doc_type 和查询关键词
   - 如果找到匹配模板：严格按模板的 style_rules（字体/字号/行距/标题层级）生成内容
   - 如果未找到模板：可自由生成，但保持专业排版
2. **按模板约束生成**：内容结构、标题层级、段落格式严格遵循模板 style_rules
3. **格式校验**：导出前**必须**调用 `validate_format` 工具，传入内容和 template_id
   - 校验通过 → 调用 export_document/export_excel 导出
   - 校验不通过 → 根据返回的不合格项清单修正内容，重新校验，直至通过
4. **返工机制**：校验不通过时不得跳过，必须修正后重新校验

**这是商业级硬约束：不合格的内容不得导出。**
**系统层也会在导出后自动触发格式校验，不合格将强制返工。**

## 工具使用原则

- **先思考再调用**：明确需要什么信息再调用工具
- **一次只调一个**：复杂任务分多轮执行
- **观察结果再继续**：工具返回后仔细阅读结果
- **信息不足先问**：缺少关键信息时先询问用户

## 内容质量要求

- 政治答题：引用马原/毛中特等基本原理，逻辑严密，联系实际
- 英语作文：用词准确、句式多样、衔接自然
- 论文/报告：完整结构（摘要、正文、结论、参考文献），格式规范
- 使用 Markdown 格式：## 二级标题，### 三级标题，**加粗**，- 列表"""


# ── Agent 服务 ──────────────────────────────────────────


class AgentModeService:
    """
    商业级 Agent 服务 — LangGraph StateGraph 引擎。

    集成：
      - LangGraph StateGraph（状态持久化 + 条件分支 + 校验/返工节点）
      - LiteLLM 统一模型接入（自动重试 + 模型降级）
      - asyncio.Queue SSE 桥接（token 级流式，前端零改动）
      - Unstructured 文档解析
      - MinIO 对象存储
      - Redis 状态持久化 + MemorySaver checkpointer
      - 全链路任务日志（Postgres）
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = get_llm_service()
        self.state_store = get_state_store()
        self.storage = get_storage_service()
        self.task_logger = get_task_logger()
        self._compiled_graph = None

    # ── 图构建 ────────────────────────────────────────────

    @property
    def compiled_graph(self):
        """懒加载编译后的 LangGraph（失败时返回 None，调用方降级）。"""
        if self._compiled_graph is None:
            self._compiled_graph = self._build_graph()
        return self._compiled_graph

    def _build_graph(self):
        """
        构建 LangGraph StateGraph — 真实图引擎。

        节点使用闭包定义，捕获 self 以访问 llm/task_logger/state_store。
        条件边控制 ReAct 循环 + 格式校验/返工分支。
        """
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_core.runnables import RunnableConfig

        graph = StateGraph(AgentState)
        checkpointer = MemorySaver()

        # ── 节点：think — LLM 推理 + 流式 token 输出 ──

        async def think_node(state: AgentState, config: RunnableConfig) -> dict:
            """think 节点：调用 LLM，流式输出 token，收集工具调用。"""
            configurable = (config or {}).get("configurable", {})
            queue: asyncio.Queue | None = configurable.get("event_queue")
            task_id = state.get("task_id", "")
            round_idx = state.get("round_idx", 0)
            messages = state.get("messages", [])

            if queue:
                await queue.put({"type": "thinking", "round": round_idx + 1, "task_id": task_id})

            # 保存状态到 Redis（断点续跑）
            self.state_store.save_state(task_id, {
                "messages": messages,
                "round_idx": round_idx,
                "session_id": state.get("session_id", ""),
                "status": "running",
            })

            # 调用 LiteLLM 统一模型接入层
            tools = get_tool_schemas()
            content_parts: list[str] = []
            tool_calls_list: list[dict] = []
            llm_error = ""

            try:
                async for chunk_type, chunk_data in self.llm.stream_completion(messages, tools=tools):
                    if chunk_type == "content":
                        content_parts.append(chunk_data)
                        if queue:
                            await queue.put({"type": "token", "token": chunk_data})
                    elif chunk_type == "tool_call":
                        tool_calls_list.append(chunk_data)
                    elif chunk_type == "done":
                        logger.info(
                            "Agent LLM 调用完成: model=%s, round=%d/%d",
                            chunk_data.get("model", "?"), round_idx + 1, MAX_TOOL_ROUNDS,
                        )
                    elif chunk_type == "error":
                        llm_error = chunk_data.get("error", "未知错误")
                        break
            except Exception as exc:
                llm_error = str(exc)

            if llm_error:
                logger.error("Agent LLM 调用失败: %s", llm_error)
                if queue:
                    await queue.put({"type": "error", "error": f"Agent 调用失败: {llm_error}"})
                return {"status": "failed", "error": llm_error, "round_idx": round_idx + 1}

            full_content = "".join(content_parts)

            # 无工具调用 → 任务完成
            if not tool_calls_list:
                self.state_store.save_state(task_id, {
                    "messages": messages,
                    "final_output": full_content,
                    "status": "completed",
                })
                return {
                    "full_content": full_content,
                    "tool_calls": [],
                    "final_output": full_content,
                    "status": "completed",
                    "round_idx": round_idx + 1,
                }

            # 有工具调用 → 追加 assistant 消息（含 tool_calls）
            updated_messages = list(messages)
            updated_messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {
                        "id": tc.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": _safe_json_arguments(tc.get("arguments", "")),
                        },
                    }
                    for i, tc in enumerate(tool_calls_list)
                ],
            })

            return {
                "full_content": full_content,
                "tool_calls": tool_calls_list,
                "messages": updated_messages,
                "round_idx": round_idx + 1,
                "status": "running",
            }

        # ── 条件边：route_after_think ──

        def route_after_think(state: AgentState) -> str:
            """think 后路由：有工具调用 → execute_tools；否则 → END。"""
            if state.get("status") == "failed":
                return END
            if not state.get("tool_calls"):
                return END
            if state.get("round_idx", 0) >= MAX_TOOL_ROUNDS:
                return END
            return "execute_tools"

        # ── 节点：execute_tools — 执行工具调用 ──

        async def execute_tools_node(state: AgentState, config: RunnableConfig) -> dict:
            """execute_tools 节点：逐个执行工具，记录日志，推送 SSE。"""
            configurable = (config or {}).get("configurable", {})
            queue: asyncio.Queue | None = configurable.get("event_queue")
            task_id = state.get("task_id", "")
            session_id = state.get("session_id", "")
            file_name = state.get("file_name")
            round_idx = state.get("round_idx", 0)
            messages = list(state.get("messages", []))
            tool_calls_list = state.get("tool_calls", [])
            files_generated = list(state.get("files_generated", []))
            template_id = state.get("template_id")

            ctx = ToolContext(
                session_id=session_id,
                task_id=task_id,
                file_name=file_name,
            )

            exported_content = state.get("exported_content", "")
            exported_format = state.get("exported_format", "")
            needs_validation = False

            for i, tc in enumerate(tool_calls_list):
                tool_name = tc.get("name", "")
                tc["arguments"] = _safe_json_arguments(tc.get("arguments", ""))

                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                step_id = round_idx * 10 + i + 1
                if queue:
                    await queue.put({
                        "type": "step",
                        "step_id": step_id,
                        "tool": tool_name,
                        "args": args,
                        "status": "running",
                    })

                t_start = time.time()
                result = await asyncio.to_thread(execute_tool, tool_name, args, ctx)
                duration_ms = round((time.time() - t_start) * 1000, 1)

                # 记录到任务日志（Postgres 持久化）
                self.task_logger.log_step(
                    task_id=task_id,
                    step_id=step_id,
                    round_idx=round_idx,
                    tool_name=tool_name,
                    args=args,
                    result=result,
                    status="error" if "error" in result else "done",
                    error=result.get("error", ""),
                    duration_ms=duration_ms,
                )

                if queue:
                    await queue.put({
                        "type": "step",
                        "step_id": step_id,
                        "tool": tool_name,
                        "result": result,
                        "status": "done",
                        "duration_ms": duration_ms,
                    })

                # 文件导出 → 推送 file 事件 + 提取校验内容
                if tool_name in ("export_document", "export_excel") and "file_url" in result:
                    files_generated.append(result)
                    if queue:
                        await queue.put({"type": "file", "file": result})
                    exported_content = args.get("content", "")
                    exported_format = args.get("format", "xlsx" if tool_name == "export_excel" else "pdf")
                    if template_id:
                        needs_validation = True

                # 从 search_template 结果追踪 template_id（跨轮持久化到 state）
                if tool_name == "search_template" and "results" in result:
                    results = result.get("results", [])
                    if results and not template_id:
                        first = results[0]
                        tid = first.get("template_id")
                        if tid:
                            try:
                                template_id = int(tid)
                            except (ValueError, TypeError):
                                pass

                # 工具结果回传 LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id") or f"call_{i}",
                    "content": json.dumps(result, ensure_ascii=False),
                })

            return {
                "messages": messages,
                "tool_results": [],
                "files_generated": files_generated,
                "exported_content": exported_content,
                "exported_format": exported_format,
                "template_id": template_id,
                "needs_validation": needs_validation,
            }

        # ── 条件边：route_after_tools ──

        def route_after_tools(state: AgentState) -> str:
            """工具执行后路由：导出文件 & 有模板 → validate；否则 → think。"""
            if state.get("needs_validation") and state.get("template_id"):
                return "validate"
            return "think"

        # ── 节点：validate — 格式校验 ──

        async def validate_node(state: AgentState, config: RunnableConfig) -> dict:
            """validate 节点：按模板校验规则检查导出内容，推送 validate SSE。"""
            configurable = (config or {}).get("configurable", {})
            queue: asyncio.Queue | None = configurable.get("event_queue")
            task_id = state.get("task_id", "")
            content = state.get("exported_content", "")
            template_id = state.get("template_id")

            if not content or not template_id:
                return {"needs_validation": False}

            try:
                from app.services.template_service import get_template_service

                svc = get_template_service()
                result = svc.validate_content(content=content, template_id=template_id)
            except Exception as exc:
                logger.error("格式校验失败: %s", exc)
                result = {
                    "passed": True,
                    "checks": [],
                    "failed_count": 0,
                    "summary": f"校验异常(跳过): {exc}",
                }

            # 记录校验步骤到任务日志
            round_idx = state.get("round_idx", 0)
            self.task_logger.log_step(
                task_id=task_id,
                step_id=round_idx * 10 + 99,
                round_idx=round_idx,
                tool_name="validate_format",
                args={"template_id": template_id, "content_length": len(content)},
                result=result,
                status="done" if result.get("passed") else "error",
                error="" if result.get("passed") else result.get("summary", ""),
                duration_ms=0.0,
            )

            if queue:
                await queue.put({
                    "type": "validate",
                    "template_id": template_id,
                    "passed": result.get("passed", True),
                    "failed_count": result.get("failed_count", 0),
                    "checks": result.get("checks", []),
                    "summary": result.get("summary", ""),
                })

            return {
                "validation_result": result,
                "needs_validation": False,
            }

        # ── 条件边：route_after_validate ──

        def route_after_validate(state: AgentState) -> str:
            """校验后路由：不通过 & 未达上限 → rework；否则 → think。"""
            vr = state.get("validation_result", {})
            if not vr.get("passed", True) and state.get("rework_count", 0) < MAX_REWORKS:
                return "rework"
            return "think"

        # ── 节点：rework — 不合格返工 ──

        async def rework_node(state: AgentState, config: RunnableConfig) -> dict:
            """rework 节点：追加返工指令到消息，回到 think 重新生成。"""
            configurable = (config or {}).get("configurable", {})
            queue: asyncio.Queue | None = configurable.get("event_queue")
            messages = list(state.get("messages", []))
            vr = state.get("validation_result", {})
            rework_count = state.get("rework_count", 0) + 1

            failed_checks = [c for c in vr.get("checks", []) if not c.get("passed")]
            failed_msgs = "\n".join(
                f"- {c['message']}" for c in failed_checks if c.get("message")
            )

            rework_msg = (
                f"[格式校验未通过] 以下内容不符合模板要求，请修正后重新导出：\n"
                f"{failed_msgs}\n\n"
                f"请根据以上问题修正内容，然后重新调用 export_document 导出。"
            )

            messages.append({"role": "user", "content": rework_msg})

            if queue:
                await queue.put({
                    "type": "rework",
                    "rework_count": rework_count,
                    "failed_checks": failed_checks,
                })

            logger.info("返工触发: rework_count=%d, failed=%d", rework_count, len(failed_checks))
            return {
                "messages": messages,
                "rework_count": rework_count,
            }

        # ── 组装图 ──
        graph.add_node("think", think_node)
        graph.add_node("execute_tools", execute_tools_node)
        graph.add_node("validate", validate_node)
        graph.add_node("rework", rework_node)

        graph.set_entry_point("think")

        graph.add_conditional_edges("think", route_after_think)
        graph.add_conditional_edges("execute_tools", route_after_tools)
        graph.add_conditional_edges("validate", route_after_validate)
        graph.add_edge("rework", "think")

        compiled = graph.compile(checkpointer=checkpointer)
        logger.info(
            "LangGraph StateGraph 已编译: think→execute_tools→validate→rework→END"
        )
        return compiled

    # ── SSE 辅助 ────────────────────────────────────────────

    @staticmethod
    def _sse(obj: dict[str, Any]) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

    def _build_messages(
        self,
        user_content: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """构建 LLM 消息列表。"""
        messages: list[dict] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_initial_state(
        self,
        messages: list[dict],
        round_start: int,
        task_id: str,
        session_id: str,
        file_name: str | None,
    ) -> AgentState:
        """构建 LangGraph 初始状态。"""
        return AgentState(
            messages=messages,
            round_idx=round_start,
            tool_calls=[],
            tool_results=[],
            files_generated=[],
            exported_content="",
            exported_format="",
            template_id=None,
            validation_result={},
            rework_count=0,
            needs_validation=False,
            final_output="",
            status="running",
            error="",
            task_id=task_id,
            session_id=session_id,
            file_name=file_name,
        )

    # ── 流式回复（LangGraph 图引擎 + asyncio.Queue 桥接）──

    async def stream_agent_reply(
        self,
        user_content: str,
        history: list[dict] | None = None,
        file_name: str | None = None,
        session_id: str = "",
        resume_task_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Agent 模式流式回复 — LangGraph StateGraph + asyncio.Queue SSE 桥接。

        图节点内的事件（thinking/token/step/file/validate/rework/done）实时推入
        asyncio.Queue，主生成器排空队列 yield SSE 字符串，保留 token 级流式体验。

        Args:
            resume_task_id: 传入时尝试断点续跑（从 Redis 恢复上次状态）。
        """
        if not self.settings.dashscope_api_key:
            yield self._sse({"error": "未配置 DASHSCOPE_API_KEY"})
            return

        # 图引擎不可用时降级到旧版循环
        if self.compiled_graph is None:
            logger.warning("LangGraph 编译失败，降级到旧版 ReAct 循环")
            async for chunk in self._stream_agent_reply_legacy(
                user_content, history, file_name, session_id, resume_task_id
            ):
                yield chunk
            return

        # ── 断点续跑：从 Redis 恢复上次中断的状态 ──
        if resume_task_id:
            saved_state = self.state_store.resume(resume_task_id)
            if saved_state:
                messages = saved_state.get("messages", [])
                round_start = saved_state.get("round_idx", 0) + 1
                task_log = self.task_logger.get_task(resume_task_id) or self.task_logger.create_task(
                    saved_state.get("session_id", session_id), user_content or "[断点续跑]"
                )
                yield self._sse({"type": "resumed", "task_id": resume_task_id})
            else:
                yield self._sse({"type": "resume_failed", "task_id": resume_task_id})
                resume_task_id = ""
                messages = self._build_messages(user_content, history)
                round_start = 0
                task_log = self.task_logger.create_task(session_id, user_content)
        else:
            effective_content = user_content
            if file_name:
                effective_content = (
                    f"{user_content}\n\n[附件文件: {file_name}]"
                    f"\n请先使用 read_document 工具读取该文件内容，理解格式要求后再生成。"
                    f"\n如果文件中有封面格式要求（如学号、姓名、学校、班级等），必须先询问用户这些信息再生成。"
                )
            messages = self._build_messages(effective_content, history)
            round_start = 0
            task_log = self.task_logger.create_task(session_id, user_content)

        task_start_time = time.time()
        task_id = task_log["task_id"]

        initial_state = self._build_initial_state(
            messages, round_start, task_id, session_id, file_name
        )

        # ── asyncio.Queue SSE 桥接 ──
        event_queue: asyncio.Queue = asyncio.Queue()

        async def _run_graph():
            """后台运行图，节点事件推入队列，完成后推送 done/error。"""
            config = {
                "configurable": {
                    "thread_id": task_id,
                    "event_queue": event_queue,
                },
                "recursion_limit": GRAPH_RECURSION_LIMIT,
            }
            try:
                final_state = await self.compiled_graph.ainvoke(initial_state, config)
                status = final_state.get("status", "running")

                if status == "failed":
                    self.task_logger.finish_task(
                        task_id, error=final_state.get("error", ""), success=False
                    )
                    # error 事件已由 think_node 推送
                else:
                    total_ms = round((time.time() - task_start_time) * 1000, 1)
                    final_output = (
                        final_state.get("final_output", "")
                        or final_state.get("full_content", "")
                    )
                    files = final_state.get("files_generated", [])
                    self.task_logger.finish_task(
                        task_id, final_output=final_output, files=files, success=True
                    )
                    if status == "running":
                        # 达到最大轮次（route_after_think → END 因 round_idx 超限）
                        await event_queue.put(
                            {"type": "token", "token": "\n\n[已达到最大工具调用轮次限制]"}
                        )
                    await event_queue.put(
                        {"type": "done", "task_id": task_id, "duration_ms": total_ms}
                    )
            except Exception as exc:
                logger.exception("LangGraph 执行失败: %s", exc)
                self.task_logger.finish_task(task_id, error=str(exc), success=False)
                await event_queue.put({"type": "error", "error": f"图执行失败: {exc}"})
            finally:
                await event_queue.put(None)  # 信号：图已完成

        # 启动图执行（后台任务，与队列排空并发运行）
        graph_task = asyncio.create_task(_run_graph())

        # ── 排空队列，yield SSE 事件 ──
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield self._sse(event)
        except Exception as exc:
            logger.error("SSE 事件队列异常: %s", exc)
            yield self._sse({"type": "error", "error": str(exc)})
        finally:
            if not graph_task.done():
                graph_task.cancel()
                try:
                    await graph_task
                except (asyncio.CancelledError, Exception):
                    pass

    # ── 非流式执行（供 Celery 批量任务调用）──

    async def run_once(
        self,
        user_content: str,
        history: list[dict] | None = None,
        file_name: str | None = None,
        session_id: str = "",
    ) -> dict[str, Any]:
        """
        非流式执行 — 图跑完返回结果（供 M5 批量任务调用）。

        不使用 asyncio.Queue 桥接，节点内跳过事件推送，直接运行图到完成。
        """
        if not self.settings.dashscope_api_key:
            return {"error": "未配置 DASHSCOPE_API_KEY", "success": False}

        if self.compiled_graph is None:
            return {"error": "LangGraph 编译失败", "success": False}

        effective_content = user_content
        if file_name:
            effective_content = (
                f"{user_content}\n\n[附件文件: {file_name}]"
                f"\n请先使用 read_document 工具读取该文件内容，理解格式要求后再生成。"
            )
        messages = self._build_messages(effective_content, history)
        task_log = self.task_logger.create_task(session_id, user_content)

        initial_state = self._build_initial_state(
            messages, 0, task_log["task_id"], session_id, file_name
        )

        config = {
            "configurable": {"thread_id": task_log["task_id"]},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

        try:
            final_state = await self.compiled_graph.ainvoke(initial_state, config)
            status = final_state.get("status", "running")
            final_output = (
                final_state.get("final_output", "")
                or final_state.get("full_content", "")
            )
            files = final_state.get("files_generated", [])
            success = status != "failed"
            self.task_logger.finish_task(
                task_log["task_id"],
                final_output=final_output,
                files=files,
                success=success,
                error=final_state.get("error", "") if not success else "",
            )
            return {
                "task_id": task_log["task_id"],
                "final_output": final_output,
                "files": files,
                "success": success,
                "error": final_state.get("error", ""),
            }
        except Exception as exc:
            logger.exception("run_once 图执行失败: %s", exc)
            self.task_logger.finish_task(task_log["task_id"], error=str(exc), success=False)
            return {
                "task_id": task_log["task_id"],
                "final_output": "",
                "files": [],
                "success": False,
                "error": str(exc),
            }

    # ── 旧版 ReAct 循环（fallback）──

    async def _stream_agent_reply_legacy(
        self,
        user_content: str,
        history: list[dict] | None = None,
        file_name: str | None = None,
        session_id: str = "",
        resume_task_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        旧版手写 ReAct 循环 — LangGraph 不可用时的 fallback。

        保留原有 for-round 循环逻辑，流式 + 重试 + 模型降级已稳定。
        """
        if not self.settings.dashscope_api_key:
            yield 'data: {"error": "未配置 DASHSCOPE_API_KEY"}\n\n'
            return

        if resume_task_id:
            saved_state = self.state_store.resume(resume_task_id)
            if saved_state:
                messages = saved_state.get("messages", [])
                round_start = saved_state.get("round_idx", 0) + 1
                task_log = self.task_logger.get_task(resume_task_id) or self.task_logger.create_task(
                    saved_state.get("session_id", session_id), user_content or "[断点续跑]"
                )
                yield 'data: {"type": "resumed", "task_id": "' + resume_task_id + '"}\n\n'
            else:
                yield 'data: {"type": "resume_failed", "task_id": "' + resume_task_id + '"}\n\n'
                resume_task_id = ""
                messages = self._build_messages(user_content, history)
                round_start = 0
                task_log = self.task_logger.create_task(session_id, user_content)
        else:
            messages = self._build_messages(user_content, history)
            round_start = 0
            task_log = self.task_logger.create_task(session_id, user_content)

        task_start_time = time.time()
        tools = get_tool_schemas()

        if not resume_task_id:
            effective_content = user_content
            if file_name:
                effective_content = (
                    f"{user_content}\n\n[附件文件: {file_name}]"
                    f"\n请先使用 read_document 工具读取该文件内容，理解格式要求后再生成。"
                    f"\n如果文件中有封面格式要求（如学号、姓名、学校、班级等），必须先询问用户这些信息再生成。"
                )
            messages = self._build_messages(effective_content, history)

        ctx = ToolContext(
            session_id=session_id,
            task_id=task_log["task_id"],
            file_name=file_name,
        )

        def _sse_legacy(obj: dict[str, Any]) -> str:
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        for round_idx in range(round_start, MAX_TOOL_ROUNDS):
            yield _sse_legacy({"type": "thinking", "round": round_idx + 1, "task_id": task_log["task_id"]})

            self.state_store.save_state(task_log["task_id"], {
                "messages": messages,
                "round_idx": round_idx,
                "session_id": session_id,
                "status": "running",
            })

            content_parts: list[str] = []
            tool_calls_list: list[dict] = []
            llm_error = ""

            try:
                async for chunk_type, chunk_data in self.llm.stream_completion(messages, tools=tools):
                    if chunk_type == "content":
                        content_parts.append(chunk_data)
                        yield _sse_legacy({"type": "token", "token": chunk_data})
                    elif chunk_type == "tool_call":
                        tool_calls_list.append(chunk_data)
                    elif chunk_type == "done":
                        logger.info(
                            "Agent LLM 调用完成: model=%s, round=%d/%d",
                            chunk_data.get("model", "?"), round_idx + 1, MAX_TOOL_ROUNDS,
                        )
                    elif chunk_type == "error":
                        llm_error = chunk_data.get("error", "未知错误")
                        break
            except Exception as exc:
                llm_error = str(exc)

            if llm_error:
                logger.error("Agent LLM 调用失败: %s", llm_error)
                self.task_logger.finish_task(task_log["task_id"], error=llm_error, success=False)
                yield _sse_legacy({"error": f"Agent 调用失败: {llm_error}"})
                return

            full_content = "".join(content_parts)

            if not tool_calls_list:
                self.state_store.save_state(task_log["task_id"], {
                    "messages": messages,
                    "final_output": full_content,
                    "status": "completed",
                })
                total_ms = round((time.time() - task_start_time) * 1000, 1)
                self.task_logger.finish_task(task_log["task_id"], final_output=full_content, success=True)
                yield _sse_legacy({"type": "done", "task_id": task_log["task_id"], "duration_ms": total_ms})
                return

            for tc in tool_calls_list:
                tc["arguments"] = _safe_json_arguments(tc["arguments"])

            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {
                        "id": tc["id"] or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for i, tc in enumerate(tool_calls_list)
                ],
            })

            for i, tc in enumerate(tool_calls_list):
                tool_name = tc["name"]
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                step_id = round_idx * 10 + i + 1
                yield _sse_legacy({
                    "type": "step",
                    "step_id": step_id,
                    "tool": tool_name,
                    "args": args,
                    "status": "running",
                })

                t_start = time.time()
                result = await asyncio.to_thread(execute_tool, tool_name, args, ctx)
                duration_ms = round((time.time() - t_start) * 1000, 1)

                self.task_logger.log_step(
                    task_id=task_log["task_id"],
                    step_id=step_id,
                    round_idx=round_idx,
                    tool_name=tool_name,
                    args=args,
                    result=result,
                    status="error" if "error" in result else "done",
                    error=result.get("error", ""),
                    duration_ms=duration_ms,
                )

                yield _sse_legacy({
                    "type": "step",
                    "step_id": step_id,
                    "tool": tool_name,
                    "result": result,
                    "status": "done",
                    "duration_ms": duration_ms,
                })

                if tool_name in ("export_document", "export_excel") and "file_url" in result:
                    yield _sse_legacy({"type": "file", "file": result})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"] or f"call_{i}",
                    "content": json.dumps(result, ensure_ascii=False),
                })

        self.state_store.save_state(task_log["task_id"], {
            "messages": messages,
            "status": "completed",
            "note": "达到最大轮次",
        })
        total_ms = round((time.time() - task_start_time) * 1000, 1)
        self.task_logger.finish_task(task_log["task_id"], success=True)
        yield _sse_legacy({"type": "token", "token": "\n\n[已达到最大工具调用轮次限制]"})
        yield _sse_legacy({"type": "done", "task_id": task_log["task_id"], "duration_ms": total_ms})

    # ── 系统统计 ────────────────────────────────────────────

    def get_system_stats(self) -> dict[str, Any]:
        """获取 Agent 系统统计（商业级监控面板）。"""
        return {
            "llm": self.llm.get_stats(),
            "storage": self.storage.get_stats(),
            "state_store": self.state_store.get_stats(),
            "task_logger": {
                "recent_tasks": self.task_logger.get_recent_tasks(limit=5),
            },
            "graph_engine": "langgraph_stategraph" if self.compiled_graph else "legacy_loop",
            "max_tool_rounds": MAX_TOOL_ROUNDS,
            "max_reworks": MAX_REWORKS,
            "model": self.settings.llm_model,
        }


# 全局单例
_agent_service: AgentModeService | None = None


def get_agent_mode_service() -> AgentModeService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentModeService()
    return _agent_service
