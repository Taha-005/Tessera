"""Version B: the same agent loop as a LangGraph graph (model node <-> tools node)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from tessera.data.schema import TermData

from common import (
    MAX_STEPS,
    Answer,
    Ask,
    Model,
    Outcome,
    ToolCall,
    model_span,
    outcome_for,
    run_tool,
    timed,
    tool_span,
)

_TURNS = {"tool": ToolCall, "answer": Answer, "ask": Ask}


class State(TypedDict):
    history: Annotated[list[dict], operator.add]  # appended to by each node
    trace: Annotated[list[Any], operator.add]
    steps: int
    turn: dict | None


def build(model: Model, term: TermData, max_steps: int = MAX_STEPS):
    def call_model(state: State) -> dict:
        step = state["steps"] + 1
        turn, ms = timed(model.next_turn, state["history"])
        return {
            "history": [{"role": "assistant", "turn": turn.model_dump()}],
            "trace": [model_span(step, turn, ms)],
            "steps": step,
            "turn": turn.model_dump(),
        }

    def call_tool(state: State) -> dict:
        call = ToolCall(**state["turn"])
        result, ms = timed(run_tool, term, call)
        return {
            "history": [{"role": "tool", "name": call.name, "result": result}],
            "trace": [tool_span(state["steps"], call, result, ms)],
        }

    def after_model(state: State) -> str:
        return "tools" if state["turn"]["kind"] == "tool" else END

    def after_tool(state: State) -> str:
        return END if state["steps"] >= max_steps else "model"

    g = StateGraph(State)
    g.add_node("model", call_model)
    g.add_node("tools", call_tool)
    g.add_edge(START, "model")
    g.add_conditional_edges("model", after_model, ["tools", END])
    g.add_conditional_edges("tools", after_tool, ["model", END])
    return g.compile()


def run(
    request: str, model: Model, term: TermData, max_steps: int = MAX_STEPS
) -> Outcome:
    graph = build(model, term, max_steps)
    final = graph.invoke(
        {
            "history": [{"role": "user", "content": request}],
            "trace": [],
            "steps": 0,
            "turn": None,
        }
    )
    raw = final["turn"]
    turn = _TURNS[raw["kind"]](**raw)
    if isinstance(turn, ToolCall):
        turn = None  # ended on a tool call: the step limit was reached
    return outcome_for(turn, final["trace"], final["history"], max_steps)
