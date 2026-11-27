"""Checks term data and constraints BEFORE solving. Anything wrong -> clear error, nothing runs.

This is the safety boundary for LLM output: a constraint that names an unknown
course, a bad time or an unknown type is rejected, never guessed.
"""

from __future__ import annotations

import re

from core.term import DAY_LETTERS

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
COMPONENTS = {"lecture", "lab", "recitation", "in-lecture lab"}

# Allowed params per constraint type: name -> required?
SCHEMAS: dict[str, dict[str, bool]] = {
    "instructor_days": {"instructor_id": True, "allowed_patterns": True},
    "instructor_time_window": {"instructor_id": True, "earliest": False, "latest": False, "days": False},
    "component_time_window": {"component": True, "course_id": False, "earliest": False, "latest": False},
    "course_days": {"course_id": True, "allowed_patterns": True},
    "no_clash_group": {"cohort_id": False, "course_ids": True, "mode": False},
    "clash_exception": {"a": True, "b": True, "reason": True},
}
NO_CLASH_MODES = {"every_section", "at_least_one"}


def check_term(raw: dict) -> list[str]:
    errors = []
    kinds = raw.get("slot_kinds", {})
    for name, k in kinds.items():
        for p in k.get("day_patterns", []):
            if not p or any(d not in DAY_LETTERS for d in p):
                errors.append(f"slot kind {name}: bad day pattern {p!r}")
        for s in k.get("starts", []):
            if not _TIME.match(s):
                errors.append(f"slot kind {name}: bad start time {s!r}")
        if not isinstance(k.get("minutes"), int) or k["minutes"] <= 0:
            errors.append(f"slot kind {name}: minutes must be a positive integer")
    seen = set()
    instructors = set(raw.get("instructors", []))
    for c in raw.get("courses", []):
        if c["id"] in seen:
            errors.append(f"course {c['id']} listed twice")
        seen.add(c["id"])
        if c.get("component") not in COMPONENTS:
            errors.append(f"course {c['id']}: unknown component {c.get('component')!r}")
        for k in c.get("slot_kinds", []):
            if k not in kinds:
                errors.append(f"course {c['id']}: unknown slot kind {k!r}")
        if not c.get("sections"):
            errors.append(f"course {c['id']}: no sections")
        for s in c.get("sections", []):
            if s.get("instructor") and s["instructor"] not in instructors:
                errors.append(f"section {s['id']}: instructor {s['instructor']!r} not in instructor list")
    return errors


def check_constraints(constraints: list[dict], raw_term: dict) -> list[str]:
    errors = []
    courses = {c["id"] for c in raw_term.get("courses", [])}
    instructors = set(raw_term.get("instructors", []))
    sections = {s["id"] for c in raw_term.get("courses", []) for s in c["sections"]}
    ids = set()
    for i, c in enumerate(constraints):
        where = f"constraint {c.get('id', f'#{i}')}"
        if not c.get("id"):
            errors.append(f"{where}: missing id")
        elif c["id"] in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(c.get("id"))
        t = c.get("type")
        if t == "unsupported":
            continue  # kept for the human, never solved
        if t not in SCHEMAS:
            errors.append(f"{where}: unknown type {t!r} (known: {', '.join(SCHEMAS)}, unsupported)")
            continue
        hard = c.get("hard", True)
        if hard and c.get("weight") is not None:
            errors.append(f"{where}: a hard constraint has no weight")
        if not hard and not (isinstance(c.get("weight"), int) and c["weight"] >= 1):
            errors.append(f"{where}: a soft constraint needs an integer weight >= 1")
        if not hard and t in ("no_clash_group", "clash_exception"):
            errors.append(f"{where}: {t} can only be hard for now")
        p = c.get("params", {})
        schema = SCHEMAS[t]
        for name in p:
            if name not in schema:
                errors.append(f"{where}: unexpected param {name!r}")
        for name, required in schema.items():
            if required and name not in p:
                errors.append(f"{where}: missing param {name!r}")
        # References must exist in the term.
        if "instructor_id" in p and p["instructor_id"] not in instructors:
            errors.append(f"{where}: unknown instructor {p['instructor_id']!r}")
        if p.get("course_id") and p["course_id"] not in courses:
            errors.append(f"{where}: unknown course {p['course_id']!r}")
        for cid in p.get("course_ids", []):
            if cid not in courses:
                errors.append(f"{where}: unknown course {cid!r}")
        if t == "no_clash_group":
            if len(set(p.get("course_ids", []))) < 2:
                errors.append(f"{where}: needs at least 2 different courses")
            if p.get("mode", "every_section") not in NO_CLASH_MODES:
                errors.append(f"{where}: mode must be one of {sorted(NO_CLASH_MODES)}")
        if t == "clash_exception":
            for key in ("a", "b"):
                if p.get(key) not in courses | sections:
                    errors.append(f"{where}: {key}={p.get(key)!r} is not a course or section")
        if "component" in p and p["component"] not in COMPONENTS:
            errors.append(f"{where}: unknown component {p['component']!r}")
        for key in ("earliest", "latest"):
            if key in p and not _TIME.match(str(p[key])):
                errors.append(f"{where}: {key} must be HH:MM, got {p[key]!r}")
        if p.get("earliest") and p.get("latest") and p["earliest"] >= p["latest"]:
            errors.append(f"{where}: earliest must be before latest")
        if t.endswith("time_window") and not (p.get("earliest") or p.get("latest")):
            errors.append(f"{where}: give earliest, latest or both")
        for pat in p.get("allowed_patterns", []) + ([p["days"]] if p.get("days") else []):
            if not pat or any(d not in DAY_LETTERS for d in pat):
                errors.append(f"{where}: bad day pattern {pat!r}")
    return errors
