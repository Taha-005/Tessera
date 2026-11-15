"""Version A: the agent loop as a plain Python loop."""

from __future__ import annotations

from tessera.data.schema import TermData

from common import (
    MAX_STEPS,
    Model,
    Outcome,
    ToolCall,
    model_span,
    outcome_for,
    run_tool,
    timed,
    tool_span,
)


def run(
    request: str, model: Model, term: TermData, max_steps: int = MAX_STEPS
) -> Outcome:
    history: list[dict] = [{"role": "user", "content": request}]
    trace = []
    turn = None
    for step in range(1, max_steps + 1):
        turn, ms = timed(model.next_turn, history)
        trace.append(model_span(step, turn, ms))
        history.append({"role": "assistant", "turn": turn.model_dump()})
        if not isinstance(turn, ToolCall):
            break  # an answer or a question for the user ends the request
        result, ms = timed(run_tool, term, turn)
        trace.append(tool_span(step, turn, result, ms))
        history.append({"role": "tool", "name": turn.name, "result": result})
    else:
        turn = None  # the step limit was reached without an answer
    return outcome_for(turn, trace, history, max_steps)
