"""Measures the two versions side by side and prints a Markdown report (pasted into RESULTS.md).

Run from this folder:  PYTHONPATH=../../backend uv run python compare.py
"""

from __future__ import annotations

import ast
import statistics
import subprocess
import sys
import time
import traceback
from importlib.metadata import distributions
from pathlib import Path

import langgraph_agent
import plain_loop
from common import ScriptedModel
from test_spike import clashing_term, happy_script

HERE = Path(__file__).parent
LOOPS = {
    "plain loop": (plain_loop.run, "plain_loop.py"),
    "LangGraph": (langgraph_agent.run, "langgraph_agent.py"),
}


def code_lines(path: Path) -> int:
    """Lines of code, not counting blank lines, comments and docstrings."""
    src = path.read_text()
    doc_lines: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        body = getattr(node, "body", None)
        first = body[0] if isinstance(body, list) and body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            doc_lines.update(range(first.lineno, first.end_lineno + 1))
    return sum(
        1
        for i, line in enumerate(src.splitlines(), 1)
        if line.strip() and not line.strip().startswith("#") and i not in doc_lines
    )


def import_ms(module: str) -> float:
    code = f"import time; t=time.perf_counter(); import {module}; print((time.perf_counter()-t)*1000)"
    runs = [
        float(
            subprocess.check_output([sys.executable, "-c", code], cwd=HERE, text=True)
        )
        for _ in range(3)
    ]
    return statistics.median(runs)


def per_run_ms(run, n: int = 300) -> float:
    term = clashing_term()
    t = time.perf_counter()
    for _ in range(n):
        run("q", ScriptedModel(happy_script()), term)
    return (time.perf_counter() - t) * 1000 / n


def traceback_frames(run) -> int:
    """How deep the stack is when the model itself fails (what you read when debugging)."""

    class Broken:
        def next_turn(self, history):
            raise RuntimeError("model failed")

    try:
        run("q", Broken(), clashing_term())
    except RuntimeError as e:
        return len(traceback.extract_tb(e.__traceback__))
    return 0


def dependency_count() -> int:
    """Packages that langgraph pulls in beyond pydantic (which the backend already has)."""
    reqs: dict[str, list[str]] = {}
    for d in distributions():
        name = d.metadata["Name"].lower().replace("_", "-")
        reqs[name] = [
            r.split(";")[0]
            .split("[")[0]
            .split(">")[0]
            .split("<")[0]
            .split("=")[0]
            .split("~")[0]
            .split("!")[0]
            .strip()
            .lower()
            .replace("_", "-")
            for r in (d.requires or [])
            if "extra ==" not in r
        ]

    def closure(root: str) -> set[str]:
        seen, todo = set(), [root]
        while todo:
            n = todo.pop()
            if n in seen or n not in reqs:
                continue
            seen.add(n)
            todo.extend(reqs[n])
        return seen

    return len(closure("langgraph") - closure("pydantic"))


def trace_table(run) -> str:
    out = run(
        "Do SYN 101 and SYN 102 clash?", ScriptedModel(happy_script()), clashing_term()
    )
    rows = ["| step | kind | name | status |", "|---|---|---|---|"]
    rows += [f"| {s.step} | {s.kind} | {s.name} | {s.status} |" for s in out.trace]
    return "\n".join(rows) + f"\n\nOutcome: **{out.status}**: {out.text}"


def main() -> None:
    print("## Measurements\n")
    print("| | plain loop | LangGraph |\n|---|---|---|")
    p, g = (LOOPS[k] for k in LOOPS)
    print(
        f"| Lines of loop code | {code_lines(HERE / p[1])} | {code_lines(HERE / g[1])} |"
    )
    print(f"| Extra packages to install | 0 | {dependency_count()} |")
    print(
        f"| Import time (ms, median of 3) | {import_ms('plain_loop'):.0f} | {import_ms('langgraph_agent'):.0f} |"
    )
    print(
        f"| Time per request, scripted model (ms) | {per_run_ms(p[0]):.2f} | {per_run_ms(g[0]):.2f} |"
    )
    print(
        f"| Stack frames when the model fails | {traceback_frames(p[0])} | {traceback_frames(g[0])} |"
    )
    print("\n## Trace of the same request (identical for both)\n")
    print(trace_table(p[0]))
    print("\n## What LangGraph gives without extra code\n")
    graph = langgraph_agent.build(ScriptedModel(happy_script()), clashing_term())
    print("Per-node streaming (`graph.stream(..., stream_mode='updates')`):\n")
    init = {
        "history": [{"role": "user", "content": "q"}],
        "trace": [],
        "steps": 0,
        "turn": None,
    }
    for ev in graph.stream(init, stream_mode="updates"):
        node, upd = next(iter(ev.items()))
        print(f"- `{node}` → step {upd.get('steps', '·')}, {upd['trace'][0].name}")
    print("\nDiagram (`graph.get_graph().draw_mermaid()`):\n\n```mermaid")
    print(graph.get_graph().draw_mermaid().strip())
    print("```")


if __name__ == "__main__":
    main()
