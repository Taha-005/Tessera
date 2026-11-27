"""JSON constraint -> CP-SAT rules. Deterministic: same JSON, same rules, every time.

Two families:
- time filters (instructor_days, instructor_time_window, component_time_window,
  course_days): say which time options a section may take. Hard -> forbidden
  options are switched off. Soft -> each forbidden option chosen costs `weight`.
- groups (no_clash_group, clash_exception): rules between sections.

To add a new type: write one function here, register it, add its params to
input_check.SCHEMAS, add a check in checker.py and a test that breaks it.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations

from core.term import Section, TimeOption, to_min

# ------------------------------------------------------------------ time filters
# Each returns True if `opt` is allowed for `sec` (or the constraint doesn't apply to sec).


def _fits_patterns(opt: TimeOption, patterns: list[str]) -> bool:
    # A single-day lab on T fits a TR-only instructor, so test "days are a subset".
    return any(set(opt.days) <= set(p) for p in patterns)


def _in_window(opt: TimeOption, p: dict) -> bool:
    if p.get("earliest") and opt.start < to_min(p["earliest"]):
        return False
    if p.get("latest") and opt.end > to_min(p["latest"]):
        return False
    return True


def instructor_days(p: dict, sec: Section, opt: TimeOption) -> bool:
    return sec.instructor != p["instructor_id"] or _fits_patterns(opt, p["allowed_patterns"])


def instructor_time_window(p: dict, sec: Section, opt: TimeOption) -> bool:
    if sec.instructor != p["instructor_id"]:
        return True
    if p.get("days") and not set(opt.days) & set(p["days"]):
        return True  # window only applies on the given days
    return _in_window(opt, p)


def component_time_window(p: dict, sec: Section, opt: TimeOption) -> bool:
    if sec.component != p["component"] or (p.get("course_id") and sec.course != p["course_id"]):
        return True
    return _in_window(opt, p)


def course_days(p: dict, sec: Section, opt: TimeOption) -> bool:
    return sec.course != p["course_id"] or _fits_patterns(opt, p["allowed_patterns"])


TIME_FILTERS: dict[str, Callable[[dict, Section, TimeOption], bool]] = {
    "instructor_days": instructor_days,
    "instructor_time_window": instructor_time_window,
    "component_time_window": component_time_window,
    "course_days": course_days,
}


def apply_time_filter(ctx, con: dict) -> None:
    rule = TIME_FILTERS[con["type"]]
    for sec in ctx.term.sections:
        for k, opt in enumerate(sec.options):
            if rule(con["params"], sec, opt):
                continue
            var = ctx.x[sec.id][k]
            if con.get("hard", True):
                ctx.model.Add(var == 0).OnlyEnforceIf(ctx.switch[con["id"]])
            else:
                ctx.penalties.append((con["weight"] * ctx.SOFT_SCALE, var, con["id"]))


# ------------------------------------------------------------------ groups


def exempt_pairs(constraints: list[dict], term) -> set[frozenset]:
    """Section pairs allowed to clash because of a clash_exception (course or section ids)."""
    out = set()
    for c in constraints:
        if c["type"] != "clash_exception":
            continue
        a_secs = term.sections_of(c["params"]["a"]) or [term.section(c["params"]["a"])]
        b_secs = term.sections_of(c["params"]["b"]) or [term.section(c["params"]["b"])]
        out |= {frozenset((a.id, b.id)) for a in a_secs for b in b_secs}
    return out


def apply_no_clash_group(ctx, con: dict) -> None:
    """Students in this group must be able to take one section of every course without clashes.

    mode every_section: whichever section a student lands in, a clash-free full
    combination containing it exists (one "witness" combination per section).
    mode at_least_one: at least one clash-free full combination exists.
    """
    p = con["params"]
    groups = {c: ctx.term.sections_of(c) for c in p["course_ids"]}
    members = [s for c in p["course_ids"] for s in groups[c]]
    anchors = members if p.get("mode", "every_section") == "every_section" else [None]
    on = ctx.switch[con["id"]]
    for anchor in anchors:
        tag = anchor.id if anchor else "any"
        pick = {s.id: ctx.model.NewBoolVar(f"{con['id']} {tag} picks {s.id}") for s in members}
        for course, secs in groups.items():
            if anchor and course == anchor.course:
                ctx.model.Add(pick[anchor.id] == 1)
            else:
                ctx.model.AddExactlyOne(pick[s.id] for s in secs)
        for a, b in combinations(members, 2):
            if a.course == b.course or frozenset((a.id, b.id)) in ctx.exempt:
                continue
            ctx.model.AddBoolOr([pick[a.id].Not(), pick[b.id].Not(), ctx.clash(a, b).Not()]).OnlyEnforceIf(on)


GROUPS = {"no_clash_group": apply_no_clash_group}
