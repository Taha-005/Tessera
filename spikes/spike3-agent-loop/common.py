"""Parts shared by both versions of the SPIKE-3 agent: two tools, a scripted model, the trace.

Both loops (plain_loop.py and langgraph_agent.py) use exactly these, so any difference
in behavior or traceability comes from the loop itself.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError
from tessera.data.schema import NoClashGroup, TermData
from tessera.data.term_io import load_json
from tessera.rules import load_rules
from tessera.rules.standin_h1 import check_h1

TERM_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "synthetic"
    / "example_term"
    / "term.json"
)
MAX_STEPS = 6  # model calls per request (the real loop's bound is set in T-068)


def load_term() -> TermData:
    return load_json(TERM_PATH)


# ---------------------------------------------------------------- what the model can say


class ToolCall(BaseModel):
    kind: Literal["tool"] = "tool"
    name: str
    args: dict[str, Any]


class Answer(BaseModel):
    kind: Literal["answer"] = "answer"
    text: str


class Ask(BaseModel):
    kind: Literal["ask"] = "ask"
    question: str


Turn = ToolCall | Answer | Ask


class Model(Protocol):
    """What a loop needs from a model. A real provider client (T-059) would implement this."""

    def next_turn(self, history: list[dict]) -> Turn: ...


class ScriptedModel:
    """A fake LLM that returns pre-written turns in order and records what it was shown."""

    def __init__(self, turns: list[Turn]):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []

    def next_turn(self, history: list[dict]) -> Turn:
        self.seen.append([dict(m) for m in history])
        if not self.turns:
            raise RuntimeError("scripted model ran out of turns")
        return self.turns.pop(0)


class LoopingModel:
    """A fake LLM that never stops calling tools, to test the step limit."""

    def __init__(self):
        self.calls = 0

    def next_turn(self, history: list[dict]) -> Turn:
        self.calls += 1
        return ToolCall(name="query_data", args={"course_id": "SYN 102"})


# ---------------------------------------------------------------- the two tools


class QueryDataArgs(BaseModel):
    course_id: str


class CheckClashArgs(BaseModel):
    course_a: str
    course_b: str


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _known(term: TermData, course_id: str) -> None:
    if course_id not in {c.id for c in term.courses}:
        raise ToolError("UNKNOWN_ENTITY", f"no course {course_id!r} in this term")


def query_data(term: TermData, args: QueryDataArgs) -> dict:
    """Placed meetings of one course's sections (simplified `query_data`)."""
    _known(term, args.course_id)
    meetings, unplaced = [], 0
    for s in term.sections:
        if s.course_id != args.course_id:
            continue
        for m in s.meetings:
            if m.placement is None:
                unplaced += 1
                continue
            p = m.placement
            meetings.append(
                {
                    "section": s.id,
                    "meeting": m.id,
                    "component": m.component,
                    "days": p.days,
                    "start": p.start,
                    "end": p.end,
                    "rooms": list(p.room_ids),
                }
            )
    return {"course_id": args.course_id, "meetings": meetings, "unplaced": unplaced}


def check_clash(term: TermData, args: CheckClashArgs) -> dict:
    """Do two courses' placed meetings overlap? Reuses the stand-in H1 check (PR #8)."""
    _known(term, args.course_a)
    _known(term, args.course_b)
    group = NoClashGroup(
        id="QUERY",
        cohort_id=term.cohorts[0].id,
        course_ids=[args.course_a, args.course_b],
        source="spike query",
    )
    findings = check_h1(
        term.model_copy(update={"no_clash_groups": [group]}), load_rules()
    )
    return {"clash": bool(findings), "details": [f.detail for f in findings]}


TOOLS: dict[str, tuple[type[BaseModel], Any]] = {
    "query_data": (QueryDataArgs, query_data),
    "check_clash": (CheckClashArgs, check_clash),
}


def run_tool(term: TermData, call: ToolCall) -> dict:
    """Run a tool call; errors come back as data for the model, never as a crash."""
    if call.name not in TOOLS:
        return {
            "ok": False,
            "error": "UNKNOWN_TOOL",
            "message": f"no tool {call.name!r}",
        }
    args_model, fn = TOOLS[call.name]
    try:
        args = args_model.model_validate(call.args)
    except ValidationError as e:
        return {
            "ok": False,
            "error": "INVALID_ARGS",
            "message": str(e.errors()[0]["msg"]),
        }
    try:
        return {"ok": True, "output": fn(term, args)}
    except ToolError as e:
        return {"ok": False, "error": e.code, "message": str(e)}


# ---------------------------------------------------------------- trace and outcome


@dataclass
class Span:
    step: int
    kind: Literal["model", "tool"]
    name: str
    input: Any
    output: Any
    status: Literal["ok", "error"]
    ms: float


@dataclass
class Outcome:
    status: Literal["answered", "asked_user", "step_limit"]
    text: str
    trace: list[Span]
    history: list[dict]


def timed(fn, *args):
    t = time.perf_counter()
    out = fn(*args)
    return out, (time.perf_counter() - t) * 1000


def model_span(step: int, turn: Turn, ms: float) -> Span:
    name = turn.name if isinstance(turn, ToolCall) else turn.kind
    return Span(step, "model", name, None, turn.model_dump(), "ok", ms)


def tool_span(step: int, call: ToolCall, result: dict, ms: float) -> Span:
    return Span(
        step,
        "tool",
        call.name,
        call.args,
        result,
        "ok" if result["ok"] else "error",
        ms,
    )


def outcome_for(
    turn: Turn | None, trace: list[Span], history: list[dict], max_steps: int
):
    if isinstance(turn, Answer):
        return Outcome("answered", turn.text, trace, history)
    if isinstance(turn, Ask):
        return Outcome("asked_user", turn.question, trace, history)
    return Outcome("step_limit", f"stopped after {max_steps} steps", trace, history)
