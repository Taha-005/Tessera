# SPIKE-3: plain loop vs. LangGraph (T-031, O-13)

Question: should the agent loop (T-068) be written as a plain Python loop or with LangGraph? The plan says to build the same small agent both ways and compare traceability and testability (Section 22). **Results and proposal: [`RESULTS.md`](RESULTS.md).**

Not used by the application (see `spikes/README.md`).

| File | What it is |
|---|---|
| `common.py` | Shared by both: the two tools, a scripted fake model (no API key), the trace records |
| `plain_loop.py` | Version A: a `for` loop |
| `langgraph_agent.py` | Version B: a LangGraph graph with a model node and a tools node |
| `test_spike.py` | 14 tests run on both versions: normal run, step limit, tool error then ask the user, bad arguments, unknown tool, identical behavior |
| `compare.py` | Measures code size, dependencies, import time, speed, stack depth; prints the report in `RESULTS.md` |

The two tools are simplified versions of the real ones, on the synthetic example term: `query_data` (a course's placed meetings) and `check_clash` (reuses the stand-in H1 check). No real department data.

```
cd spikes/spike3-agent-loop
uv sync
uv run pytest
PYTHONPATH=../../backend uv run python compare.py
```

A real LLM can replace the scripted model by implementing `next_turn(history)`; not done here because the team has no API key yet (Q-T4).
