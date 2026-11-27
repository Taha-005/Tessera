# Tessera core: structured constraints in, timetable out

> **Prototype.** Working end-to-end slice built locally and tested on a 2nd-year example
> (59 sections). It will move into `backend/tessera/` (solver, validator, agent) once the team
> agrees on the structure. All example data here is synthetic (instructors named x, y, z, a, b...).

The deterministic part of Tessera. No LLM in here.

```
term.json + constraints.json  ->  input check  ->  translate  ->  CP-SAT  ->  checker  ->  result.json
```

## Run

```
cd prototype/tessera_core
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install ortools pytest
python3 run.py examples/e2_term.json examples/e2_constraints.json          # -> NO_SOLUTION, blames C2-k
python3 run.py examples/e2_term_fixed.json examples/e2_constraints.json    # -> timetable, checker PASS
python3 -m pytest -q tests                              # 39 tests (agent tests use a fake LLM: no key, no cost)
```

## The agent (LLM) part

Put your key in `.env` in this folder (never commit or share it):
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```
Then:
```
python agent_run.py examples/e2_term.json examples/e2_notes.txt
python agent_run.py examples/e2_term_fixed.json examples/e2_notes_with_prefs.txt
```
1. The agent reads the notes and proposes constraints. They are shown in plain English written by code
   (not by the LLM), with the note each came from, plus questions for vague notes.
2. Every proposal goes through the input checker. Wrong ones get one repair round, then are rejected.
3. You approve. The solver runs (preferences first).
4. If it is impossible, code computes the facts (e.g. "k has 5 labs, only 4 open slots") and the LLM explains
   them and recommends one fix, chosen only from fixes the solver proved. You approve, it solves again.

`agent_log.json` records every LLM call: tokens, cost, seconds. `--yes` approves automatically (demo only).

| File | Job |
| --- | --- |
| `agent/llm.py` | OpenRouter client: retries, timeout, token and cost tracking |
| `agent/extract.py` | notes -> constraints, with the repair round and safety rules |
| `agent/describe.py` | constraint -> plain English (deterministic) |
| `agent/explain.py` | facts + LLM explanation + guarded fix recommendation |
| `agent_run.py` | the whole loop with approvals |

## Two ways to handle preferences (soft constraints)

**`--mode preferences_first` (default).** Every preference is first treated as a hard rule.
- All fit -> timetable with every preference met.
- Some can't fit -> `PREFERENCES_CLASH`: lists each group of preferences that clash and the options
  to relax. Nothing is relaxed automatically. Pick one and rerun:

```
python3 run.py examples/e2_term_fixed.json examples/e2_constraints_with_prefs.json              # -> P1 and P2 clash
python3 run.py examples/e2_term_fixed.json examples/e2_constraints_with_prefs.json --relax P1,P2  # -> timetable
```

A relaxed preference is still tried as much as possible; the report says how many sections break it.

**`--mode weights`.** One run, automatic compromise: each broken preference costs its weight.

```
python3 run.py examples/e2_term_fixed.json examples/e2_constraints_with_prefs.json --mode weights
```

If the real hard rules clash (not the preferences), both modes return `NO_SOLUTION` with the culprits.

## Files

| File | Job |
| --- | --- |
| `core/term.py` | Loads what the department offers: courses, sections, instructors, slot grid. No times. |
| `core/input_check.py` | Rejects bad input (unknown course, bad time, unknown type, missing weight...) before solving. This is where LLM mistakes stop. |
| `core/translate.py` | One function per constraint type: JSON -> CP-SAT rules. Deterministic. |
| `core/solve.py` | Builds the model, runs CP-SAT, finds the smallest conflicting set when impossible, returns the result. |
| `core/checker.py` | Re-checks the timetable independently (no shared code with translate.py). |
| `run.py` | Command line + week-grid printout. |

## Constraint types supported

| Type | Params | Hard/soft |
| --- | --- | --- |
| `instructor_days` | `instructor_id`, `allowed_patterns` (e.g. `["TR"]`) | both |
| `instructor_time_window` | `instructor_id`, `earliest`/`latest` (HH:MM), optional `days` | both |
| `component_time_window` | `component`, optional `course_id`, `earliest`/`latest` | both |
| `course_days` | `course_id`, `allowed_patterns` | both |
| `no_clash_group` | `cohort_id`, `course_ids`, `mode`: `every_section` (default) or `at_least_one` | hard |
| `clash_exception` | `a`, `b` (course or section ids), `reason` | hard |
| `unsupported` | anything; reported, never solved | - |

Built-in rule, always on: no instructor teaches two things at once.

Every constraint: `{"id", "type", "hard", "weight" (soft only), "params", "source"}`.

## Result statuses

`INVALID_INPUT` (with errors), `SOLVED`, `SOLVED_TIME_LIMIT` (valid, maybe not best),
`NO_SOLUTION` (with `conflict`: the smallest set of constraint ids that clash), `PREFERENCES_CLASH` (preferences_first mode only), `UNKNOWN` (time ran out).

## Not in yet

Rooms (capacity, labs, parallel rooms), lecture-lab coupling inside one section, major restrictions,
external blocks, stay-close-to-previous-schedule.
