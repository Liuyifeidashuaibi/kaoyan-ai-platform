#!/usr/bin/env python3
"""验证 langgraph StateGraph API 可用性。"""
import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


class TestState(TypedDict, total=False):
    messages: list
    count: int


def increment(state):
    c = state.get("count", 0) + 1
    return {"count": c}


def route(state):
    if state.get("count", 0) >= 3:
        return END
    return "loop"


g = StateGraph(TestState)
g.add_node("loop", increment)
g.set_entry_point("loop")
g.add_conditional_edges("loop", route)
compiled = g.compile(checkpointer=MemorySaver())
print("Graph compiled OK")


async def test():
    config = {"configurable": {"thread_id": "test1"}}
    async for state in compiled.astream({"count": 0, "messages": []}, config):
        c = state.get("count")
        print(f"State: count={c}")
    print("Graph execution OK")


asyncio.run(test())
