# Agent loop: plain Python loop (proposed)

**Date:** 2026-11-15 · **Proposed by:** Mohamad El Ajouz · **Task:** TESS-37 (T-031, SPIKE-3) · **Open item:** O-13 · **Status:** PROPOSED, for team decision

## Question

Should the bounded agent loop (Section 13.2, T-068) be written as a plain Python loop or with LangGraph? Section 22 asks to compare traceability and testability.

## What was done

The same small agent (two tools on the synthetic term, a scripted model) was built both ways in `spikes/spike3-agent-loop/`. The same 14 tests pass on both and confirm identical behavior and traces. Full numbers in `spikes/spike3-agent-loop/RESULTS.md`.

## Options considered

| Option | Traceability | Testability | Cost | Verdict |
|---|---|---|---|---|
| **Plain loop** | Same spans as LangGraph (our own trace records); Langfuse via `@observe()` | Same tests pass | 31 lines, no new dependency | **Proposed** |
| LangGraph | Same spans, plus free per-node streaming and diagram | Same tests pass | 69 lines, 33 extra packages, 4x import time, deeper stack traces, team learning time | Not needed for one bounded agent |

## Proposal

Use a plain loop for T-068. LangGraph's main extras (pause and resume from checkpoints, parallel branches, multi-agent graphs) are not in our design: "ask the user" ends a request, and approval happens in the app through proposals. Revisit if that changes.

## Not covered

O-24 (ReAct framing options): wording to be confirmed by the team before options are laid out.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** The agent loop is a plain Python loop with a step limit, Pydantic-validated tool arguments, tool errors returned to the model, and an explicit trace (SPIKE-3). Resolves O-13.
- **Section 8 (Tech stack):** remove "LangGraph or a plain loop"; keep "plain agent loop".
