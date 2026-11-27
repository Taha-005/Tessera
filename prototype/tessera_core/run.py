"""Command line:
  python3 run.py TERM.json CONSTRAINTS.json [--mode preferences_first|weights] [--relax ID,ID] [--time 60]

--mode preferences_first (default): try to meet every preference; if impossible, list which
  preferences clash and stop, so a person chooses what to relax (then rerun with --relax).
--mode weights: one run, automatic compromise using the preference weights.

Prints a short report and the timetable as a week grid; writes the full result as JSON.
"""

import argparse
import json
from collections import defaultdict

from core.solve import solve, solve_preferences_first
from core.term import to_hhmm


def print_report(res: dict) -> None:
    print(f"\nSTATUS: {res['status']}" + (f"   (mode: {res['mode']})" if res.get("mode") else ""))
    if res.get("relaxed"):
        print(f"  relaxed by you: {', '.join(res['relaxed'])}")
    if res["status"] == "INVALID_INPUT":
        for e in res["errors"]:
            print("  x", e)
        return
    s = res.get("stats")
    if s:
        print(f"  {s['sections']} sections, {s['constraints']} constraints -> "
                  f"{s['variables']} variables, {s['cp_sat_rules']} CP-SAT rules, solved in {s['solve_seconds']}s")
    for u in res.get("unsupported", []):
        print(f"  ! not used (unsupported): {u['id']}: {u['source']}")
    if res["status"] == "PREFERENCES_CLASH":
        print("  Every hard rule fits, but these preferences cannot all be met together:")
        for i, c in enumerate(res["clashes"], 1):
            print(f"\n  Clash {i}:")
            for p in c["preferences"]:
                print(f"   - {p['id']} (weight {p['weight']}): {p.get('source')}")
            print("   Options:")
            for f in c["fixes"]:
                extra = "  <- and then everything else fits" if f["then_everything_else_fits"] else ""
                print(f"     relax {f['relax']}{extra}")
        print(f"\n  Next: {res['next_step']}")
        return
    if res["status"] == "NO_SOLUTION":
        print("  These constraints cannot all hold together:")
        for c in res["conflict"]:
            print(f"   - {c['id']} ({c['type']}): {c.get('source')}")
        if res.get("conflict_note"):
            print("  ", res["conflict_note"])
        return
    if "timetable" not in res:
        print(" ", res.get("note"))
        return
    chk = res["check"]
    print(f"  checker: {'PASS' if chk['passed'] else 'FAIL'} ({len(chk['problems'])} problems)")
    for p in chk["problems"][:20]:
        print("   -", p)
    if res.get("preferences_tried_as_hard"):
        print(f"  all {len(res['preferences_tried_as_hard'])} preferences met: "
              + ", ".join(res["preferences_tried_as_hard"]))
    if res["soft_unmet"]:
        print("  soft preferences not met (sections breaking each):", res["soft_unmet"])

    by_day = defaultdict(list)
    for r in res["timetable"]:
        for d in r["days"]:
            by_day[d].append(r)
    for d, name in zip("MTWRF", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
        print(f"\n{name}")
        rows = sorted(by_day[d], key=lambda r: (r["start"], r["section"]))
        slot = None
        for r in rows:
            label = f"{to_hhmm(r['start'])}-{to_hhmm(r['end'])}"
            prefix = label if label != slot else " " * len(label)
            slot = label
            print(f"  {prefix}  {r['section']:<16} {r['instructor'] or 'TA'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("constraints")
    ap.add_argument("--out", default="result.json")
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--mode", choices=["preferences_first", "weights"], default="preferences_first")
    ap.add_argument("--relax", default="", help="comma-separated preference ids to keep soft")
    a = ap.parse_args()
    cons = json.load(open(a.constraints))
    if a.mode == "weights":
        result = solve(a.term, cons, time_limit=a.time, seed=a.seed)
        result["mode"] = "weights"
    else:
        relaxed = [r.strip() for r in a.relax.split(",") if r.strip()]
        result = solve_preferences_first(a.term, cons, relaxed, time_limit=a.time, seed=a.seed)
    json.dump(result, open(a.out, "w"), indent=1)
    print_report(result)
    print(f"\nfull result: {a.out}")
