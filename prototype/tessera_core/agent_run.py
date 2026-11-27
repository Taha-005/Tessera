"""The full loop, with a person approving each step.

  python agent_run.py TERM.json NOTES.txt [--time 30] [--yes]

1. Agent reads the notes -> proposed constraints (shown in plain English) + questions.
2. You approve (y), stop (n), or edit proposed_constraints.json and press e.
3. Solver runs (preferences first). If impossible, the agent explains why and recommends a fix.
4. You approve the fix (y) or name another id to relax; solver runs again.
--yes approves everything automatically (for demos/tests; not for real use).
Writes: proposed_constraints.json, agent_log.json (LLM calls, tokens, cost), result.json
"""

import argparse
import json
from pathlib import Path

from agent.describe import describe
from agent.explain import explain, reassign
from agent.extract import extract
from agent.llm import LLMError, OpenRouterLLM
from core.solve import solve_preferences_first
from run import print_report


def ask(prompt: str, auto: bool, valid: set[str], default: str = "y") -> str:
    """Ask until the answer is exactly one of `valid` (case-insensitive). Nothing is approved by accident:
    an empty answer, a typo or another keyboard layout just asks again."""
    if auto:
        print(f"{prompt} [{default}] (auto)")
        return default
    lower = {v.lower(): v for v in valid}
    while True:
        a = input(f"{prompt} ").strip()
        if a.lower() in lower:
            return lower[a.lower()]
        print(f"   please type one of: {', '.join(sorted(valid))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("notes")
    ap.add_argument("--time", type=float, default=30)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()

    term = json.loads(Path(a.term).read_text(encoding="utf-8"))
    notes = Path(a.notes).read_text(encoding="utf-8")
    try:
        llm = OpenRouterLLM(model=a.model)
    except LLMError as e:
        print("x", e)
        return
    print(f"model: {llm.model}")

    # ---- 1. notes -> constraints
    print("\n[1] Reading your notes...")
    try:
        ex = extract(notes, term, llm)
    except LLMError as e:
        print("x LLM unavailable:", e, "\n  (you can still run the solver on an approved constraints file with run.py)")
        return
    cons = ex["constraints"]
    print(f"\nProposed constraints ({len(cons)}){' (after one repair round)' if ex['repaired'] else ''}:")
    for c in cons:
        print(f"  {c['id']:4} {describe(c)}")
        print(f"       from: \"{c.get('source')}\"")
    for r in ex["rejected"]:
        print(f"  REJECTED by checker: {r['constraint'].get('source')} -> {'; '.join(r['errors'])}")
    for q in ex["questions"]:
        print(f"  QUESTION: \"{q.get('note')}\" -> {q.get('question')}")
    for i in ex["ignored"]:
        print(f"  ignored: \"{i.get('note')}\" ({i.get('why')})")
    Path("proposed_constraints.json").write_text(json.dumps(cons, indent=1), encoding="utf-8")

    ans = ask("\nApprove these constraints? (y = yes, n = stop, e = I edited proposed_constraints.json)",
              a.yes, {"y", "n", "e"})
    if ans == "n":
        print("Stopped. Nothing was solved.")
        return _save_log(llm)
    if ans == "e":
        cons = json.loads(Path("proposed_constraints.json").read_text(encoding="utf-8"))

    # ---- 2. solve, explain, relax, repeat
    relaxed: list[str] = []
    for round_no in range(1, 6):
        print(f"\n[2] Solving (round {round_no})...")
        res = solve_preferences_first(term, cons, relaxed, time_limit=a.time)
        if res["status"] not in ("NO_SOLUTION", "PREFERENCES_CLASH"):
            break
        print_report(res)
        try:
            ex2 = explain(res, term, llm, cons)["explanations"]
        except LLMError as e:
            print("x explainer unavailable:", e)
            ex2 = []
        if not ex2:
            break
        picks = []
        changes = {}
        for e in ex2:
            print(f"\n  Why: {e['explanation']}")
            for f in e["facts"]:
                print(f"    fact: {f}")
            print("  Options:")
            for o in e["options"]:
                star = "   <- recommended" if o["relax"] == e["recommended_relax"] else ""
                print(f"    {o['relax']:5} {o.get('meaning', 'relax this preference')}{star}")
            if e.get("alternative_change"):
                print(f"  Other idea (not tested): {e['alternative_change']}")
            ids = {o["relax"] for o in e["options"]}
            ans = ask(f"  Apply {e['recommended_relax']}? (y / n = stop / or type another option id)",
                      a.yes, {"y", "n"} | ids)
            if ans == "n":
                print("Stopped. Change the input and run again.")
                return _save_log(llm)
            picks.append(e["recommended_relax"] if ans == "y" else ans)
            changes.update({ch["id"]: ch for ch in e.get("changes", [])})
        for pk in picks:
            if pk in changes:  # an offering change: edit the term, keep every rule
                ch = changes[pk]
                term = reassign(term, ch["section"], ch["to"])
                print(f"  changed offering: {ch['meaning']}")
            elif res["status"] == "PREFERENCES_CLASH":
                relaxed.append(pk)
            else:  # a hard rule must go (the person approved this exact id)
                dropped = [c for c in cons if c["id"] == pk]
                cons = [c for c in cons if c["id"] != pk]
                print("  dropped hard rule:", ", ".join(describe(c) for c in dropped))

    print_report(res)
    Path("result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    _save_log(llm)


def _save_log(llm):
    u = llm.usage
    Path("agent_log.json").write_text(json.dumps(u.__dict__, indent=1), encoding="utf-8")
    print(f"\nLLM: {u.calls} calls, {u.prompt_tokens}+{u.completion_tokens} tokens, "
          f"${u.cost_usd:.4f}, {u.seconds:.1f}s  (details in agent_log.json)")


if __name__ == "__main__":
    main()
