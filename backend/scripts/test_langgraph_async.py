#!/usr/bin/env python3
"""验证 langgraph async 节点 + asyncio.Queue 桥接 SSE 事件。"""
import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


class TestState(TypedDict, total=False):
    messages: list
    count: int
    done: bool


async def async_increment(state):
    await asyncio.sleep(0.01)  # 模拟异步操作
    c = state.get("count", 0) + 1
    return {"count": c, "done": c >= 3}


def route(state):
    if state.get("done"):
        return END
    return "loop"


g = StateGraph(TestState)
g.add_node("loop", async_increment)
g.set_entry_point("loop")
g.add_conditional_edges("loop", route)
compiled = g.compile(checkpointer=MemorySaver())
print("Async graph compiled OK")


async def test():
    # 用 asyncio.Queue 桥接图内事件到外部流
    event_queue = asyncio.Queue()

    async def run_graph():
        config = {"configurable": {"thread_id": "test2"}}
        async for state in compiled.astream(
            {"count": 0, "messages": [], "done": False}, config,
            stream_mode="updates",
        ):
            await event_queue.put(f"update: {state}")
        await event_queue.put(None)  # done

    task = asyncio.create_task(run_graph())
    while True:
        evt = await event_queue.get()
        if evt is None:
            break
        print(evt)
    await task
    print("Async + Queue bridge OK")


asyncio.run(test())
