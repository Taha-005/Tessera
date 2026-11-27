"""Independent checker: re-checks a finished timetable against every HARD rule.

Written separately from translate.py on purpose (no shared rule code), so a bug
in the solver model shows up here instead of reaching the department.
"""

from __future__ import annotations

from itertools import combinations


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _overlap(a, b) -> bool:
    return any(d in b.days for d in a.days) and a.start < b.end and b.start < a.end


def _days_ok(days: str, patterns: list[str]) -> bool:
    return any(all(d in p for d in days) for p in patterns)


def _window_ok(t, p) -> bool:
    return not ((p.get("earliest") and t.start < _hm(p["earliest"]))
                or (p.get("latest") and t.end > _hm(p["latest"])))


def _full_combo(anchor, courses, by_course, tt, exempt):
    chosen = [anchor] if anchor else []
    rest = [c for c in courses if not anchor or c != anchor.course]

    def ok(s):
        return all(frozenset((s.id, c.id)) in exempt or not _overlap(tt[s.id], tt[c.id]) for c in chosen)

    def go(i):
        if i == len(rest):
            return True
        for s in by_course[rest[i]]:
            if ok(s):
                chosen.append(s)
                if go(i + 1):
                    return True
                chosen.pop()
        return False

    return [s.id for s in chosen] if go(0) else None


def check(term, constraints: list[dict], tt: dict) -> dict:
    problems: list[str] = []

    # Built-in: no instructor in two places at once.
    for a, b in combinations(term.sections, 2):
        if a.instructor and a.instructor == b.instructor and _overlap(tt[a.id], tt[b.id]):
            problems.append(f"built-in: {a.instructor} teaches {a.id} and {b.id} at the same time")

    exempt = set()
    for c in constraints:
        if c["type"] == "clash_exception":
            p = c["params"]
            A = [s for s in term.sections if s.course == p["a"] or s.id == p["a"]]
            B = [s for s in term.sections if s.course == p["b"] or s.id == p["b"]]
            exempt |= {frozenset((a.id, b.id)) for a in A for b in B}

    witnesses = {}
    for c in constraints:
        if not c.get("hard", True):
            continue
        p, t, cid = c["params"], c["type"], c["id"]
        for s in term.sections:
            when = tt[s.id]
            if t == "instructor_days" and s.instructor == p["instructor_id"] \
                    and not _days_ok(when.days, p["allowed_patterns"]):
                problems.append(f"{cid}: {s.id} ({s.instructor}) is on {when.days}")
            elif t == "course_days" and s.course == p["course_id"] and not _days_ok(when.days, p["allowed_patterns"]):
                problems.append(f"{cid}: {s.id} is on {when.days}")
            elif t == "instructor_time_window" and s.instructor == p["instructor_id"]:
                applies = not p.get("days") or any(d in p["days"] for d in when.days)
                if applies and not _window_ok(when, p):
                    problems.append(f"{cid}: {s.id} at {when.label()} is outside {s.instructor}'s window")
            elif t == "component_time_window" and s.component == p["component"] \
                    and (not p.get("course_id") or s.course == p["course_id"]) and not _window_ok(when, p):
                problems.append(f"{cid}: {s.id} at {when.label()} is outside the allowed window")
        if t == "no_clash_group":
            group = p.get("cohort_id") or "this group"
            by_course = {k: [s for s in term.sections if s.course == k] for k in p["course_ids"]}
            if p.get("mode", "every_section") == "every_section":
                for k in p["course_ids"]:
                    for s in by_course[k]:
                        w = _full_combo(s, p["course_ids"], by_course, tt, exempt)
                        if w is None:
                            problems.append(f"{cid}: a student in {s.id} cannot fit all of {group}'s courses")
                        else:
                            witnesses.setdefault(cid, {})[s.id] = w
            else:
                w = _full_combo(None, p["course_ids"], by_course, tt, exempt)
                if w is None:
                    problems.append(f"{cid}: no clash-free combination exists for {group}")
                else:
                    witnesses[cid] = {"example": w}
    return {"passed": not problems, "problems": problems, "example_schedules": witnesses}
