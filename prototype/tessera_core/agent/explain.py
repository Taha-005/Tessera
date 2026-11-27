"""Agent step 2: explain a failed solve in plain words and propose the smallest fix.

The facts (how many sections, how many allowed time slots) are computed by plain code.
The LLM only explains them and picks ONE fix from the options the solver already proved
work. A suggestion outside those options is thrown away.
"""

from __future__ import annotations

import json

from agent.describe import describe
import copy

from core.solve import _feasible
from core.term import load_term
from core.translate import TIME_FILTERS


def reassign(term_raw: dict, section_id: str, to: str) -> dict:
    """Copy of the term with one section taught by `to` instead."""
    t = copy.deepcopy(term_raw)
    for c in t["courses"]:
        for s in c["sections"]:
            if s["id"] == section_id:
                s["instructor"] = to
    return t


def change_options(term_raw: dict, constraints: list[dict], conflict: list[dict],
                   time_limit: float = 15, limit: int = 3) -> list[dict]:
    """Offering changes that make the problem solvable, each PROVEN by re-running the solver:
    move one section of a blamed instructor to another instructor of the same course."""
    term = load_term(term_raw)
    people = {c["params"].get("instructor_id") for c in conflict} - {None}
    out = []
    for who in sorted(people):
        for course in sorted({s.course for s in term.sections if s.instructor == who}):
            sec = [s for s in term.sections if s.course == course and s.instructor == who][-1]
            others = sorted({s.instructor for s in term.sections
                             if s.course == course and s.instructor and s.instructor != who})
            for to in others:
                trial = reassign(term_raw, sec.id, to)
                if _feasible(load_term(trial), constraints, time_limit, 1) is True:
                    out.append({"id": f"R{len(out) + 1}", "section": sec.id, "from": who, "to": to,
                                "meaning": f"move {sec.id} from {who} to {to} (keeps every rule)"})
                if len(out) >= limit:
                    return out
    return out


def facts(term_raw: dict, conflict: list[dict]) -> list[str]:
    """Counting facts that usually explain an impossible schedule."""
    term = load_term(term_raw)
    out = []
    people = {c["params"].get("instructor_id") for c in conflict} - {None}
    for who in sorted(people):
        secs = [s for s in term.sections if s.instructor == who]
        cons = [c for c in conflict if c["type"] in TIME_FILTERS]
        allowed = set()
        for s in secs:
            for o in s.options:
                if all(TIME_FILTERS[c["type"]](c["params"], s, o) for c in cons):
                    allowed.add(o)
        # Count slots that do not overlap each other (greedy by end time).
        free = []
        for o in sorted(allowed, key=lambda o: (o.days, o.end)):
            if not any(o.overlaps(f) for f in free):
                free.append(o)
        out.append(f"{who} teaches {len(secs)} sections ({', '.join(sorted({s.course for s in secs}))}); "
                   f"under these rules only {len(free)} non-overlapping time slots are open to them: "
                   + ", ".join(o.label() for o in free))
    return out


def explain(result: dict, term_raw: dict, llm, constraints: list[dict] | None = None) -> dict:
    changes = []
    if result["status"] == "NO_SOLUTION":
        if constraints is not None:
            changes = change_options(term_raw, constraints, result["conflict"])
        groups = [{"constraints": result["conflict"],
                   "options": [{"relax": c["id"], "meaning": "drop this rule"} for c in result["conflict"]]
                   + [{"relax": ch["id"], "meaning": ch["meaning"]} for ch in changes]}]
        kind = ("The HARD rules below cannot all hold together. "
                "Relaxing or changing any one of them removes the problem.")
    elif result["status"] == "PREFERENCES_CLASH":
        groups = [{"constraints": c["preferences"],
                   "options": [{"relax": f["relax"], "then_everything_else_fits": f["then_everything_else_fits"]}
                               for f in c["fixes"]]} for c in result["clashes"]]
        kind = ("All hard rules fit, but these PREFERENCES cannot all be met. "
                "Relaxing a preference means it is still tried but may be broken for some sections.")
    else:
        return {"explanations": []}

    out = []
    for g in groups:
        payload = {
            "situation": kind,
            "constraints": [{"id": c["id"], "meaning": describe({**c, "hard": c.get("weight") is None}),
                             "original_note": c.get("source")} for c in g["constraints"]],
            "facts_computed_by_code": facts(term_raw, g["constraints"]),
            "fix_options": g["options"],
        }
        msg = [{"role": "system", "content":
                "You explain timetable conflicts to a university department scheduler in 2-4 short, plain "
                "sentences. Use the computed facts (numbers) to say WHY. Then recommend exactly ONE option "
                "from fix_options. Prefer options that keep every rule (ids starting with R, e.g. moving a "
                "section to another instructor) over dropping a rule; for preferences prefer one where "
                "then_everything_else_fits is true and the weight is lower. In alternative_change, name one "
                "other concrete change in words. Never invent ids. Return JSON: "
                '{"explanation": "...", "recommended_relax": "<id from fix_options>", '
                '"alternative_change": "..."}'},
               {"role": "user", "content": json.dumps(payload, indent=1)}]
        r = llm.chat_json(msg, step="explain")
        valid = {o["relax"] for o in g["options"]}
        rec = r.get("recommended_relax")
        if rec not in valid:  # never act on an id the solver didn't offer
            rec = g["options"][0]["relax"]
            r["note"] = "LLM suggested an id that was not an option; replaced with the first valid option"
        out.append({"options": g["options"], "changes": changes,
                    "constraint_ids": [c["id"] for c in g["constraints"]],
                    "facts": payload["facts_computed_by_code"],
                    "explanation": r.get("explanation", ""), "recommended_relax": rec,
                    "alternative_change": r.get("alternative_change", ""),
                    **({"note": r["note"]} if "note" in r else {})})
    return {"explanations": out}
