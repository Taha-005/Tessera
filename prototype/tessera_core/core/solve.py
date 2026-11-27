"""The deterministic pipeline: check input -> translate -> CP-SAT -> check result -> report.

Statuses
- INVALID_INPUT: the term or a constraint is wrong; nothing was solved.
- SOLVED: proven best timetable.            - SOLVED_TIME_LIMIT: valid, maybe not the best.
- NO_SOLUTION: impossible; `conflict` lists the smallest set of constraints that clash.
- UNKNOWN: time ran out before any timetable was found.
"""

from __future__ import annotations

import time
from itertools import combinations

from ortools.sat.python import cp_model

from core import checker
from core.input_check import check_constraints, check_term
from core.term import Section, Term, load_term
from core.translate import GROUPS, TIME_FILTERS, apply_time_filter, exempt_pairs


class _Ctx:
    """Everything a translator needs: the model, the time choices and helpers."""

    SOFT_SCALE = 10  # one unit of department preference outweighs 10 "same-time" pairs

    def __init__(self, term: Term, constraints: list[dict]):
        self.term = term
        self.model = cp_model.CpModel()
        self.switch = {c["id"]: self.model.NewBoolVar(f"switch {c['id']}") for c in constraints}
        self.x = {s.id: [self.model.NewBoolVar(f"{s.id} @ {o.label()}") for o in s.options]
                  for s in term.sections}
        for s in term.sections:
            self.model.AddExactlyOne(self.x[s.id])
        self.penalties: list[tuple[int, cp_model.IntVar, str]] = []
        self.exempt = exempt_pairs(constraints, term)
        self._clash: dict[tuple[str, str], cp_model.IntVar] = {}

    def clash(self, a: Section, b: Section) -> cp_model.IntVar:
        """Boolean that is forced to 1 whenever sections a and b overlap."""
        key = tuple(sorted((a.id, b.id)))
        if key not in self._clash:
            v = self.model.NewBoolVar(f"clash {key}")
            for i, oa in enumerate(a.options):
                for j, ob in enumerate(b.options):
                    if oa.overlaps(ob):
                        self.model.AddBoolOr([self.x[a.id][i].Not(), self.x[b.id][j].Not(), v])
            self._clash[key] = v
        return self._clash[key]


def _build(term: Term, constraints: list[dict], optimize: bool) -> _Ctx:
    ctx = _Ctx(term, constraints)
    m = ctx.model

    # Built-in rule (always on): an instructor is never in two places at once.
    for a, b in combinations(term.sections, 2):
        if a.instructor and a.instructor == b.instructor:
            for i, oa in enumerate(a.options):
                for j, ob in enumerate(b.options):
                    if oa.overlaps(ob):
                        m.AddBoolOr([ctx.x[a.id][i].Not(), ctx.x[b.id][j].Not()])

    for con in constraints:
        if con["type"] in TIME_FILTERS:
            apply_time_filter(ctx, con)
        elif con["type"] in GROUPS:
            GROUPS[con["type"]](ctx, con)

    if optimize:
        # Soft preferences first, then spread sections of one course over different times.
        spread = [ctx.clash(a, b) for a, b in combinations(term.sections, 2) if a.course == b.course]
        m.Minimize(sum(w * v for w, v, _ in ctx.penalties) + sum(spread))
    m.AddAssumptions(list(ctx.switch.values()))
    return ctx


def _run(ctx: _Ctx, time_limit: float, seed: int):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = seed
    return solver, solver.Solve(ctx.model)


def _feasible(term: Term, constraints: list[dict], time_limit: float, seed: int) -> bool | None:
    ctx = _build(term, constraints, optimize=False)
    _, st = _run(ctx, time_limit, seed)
    if st == cp_model.INFEASIBLE:
        return False
    return True if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None


def minimal_conflict(term: Term, constraints: list[dict], time_limit: float = 20, seed: int = 1,
                     fixed: list[dict] = ()) -> list[dict]:
    """Smallest set of `constraints` that is still impossible together (drop one at a time).
    `fixed` constraints are always kept and never blamed."""
    keep = list(constraints)
    for con in list(constraints):
        trial = [k for k in keep if k is not con]
        if _feasible(term, list(fixed) + trial, time_limit, seed) is False:
            keep = trial
    return keep


def solve(term_source, constraints: list[dict], time_limit: float = 60, seed: int = 1) -> dict:
    t0 = time.perf_counter()
    raw = term_source if isinstance(term_source, dict) else load_term(term_source).raw
    errors = check_term(raw) + check_constraints(constraints, raw)
    if errors:
        return {"status": "INVALID_INPUT", "errors": errors}

    term = load_term(raw)
    unsupported = [c for c in constraints if c["type"] == "unsupported"]
    active = [c for c in constraints if c["type"] != "unsupported"]

    ctx = _build(term, active, optimize=True)
    solver, st = _run(ctx, time_limit, seed)
    out: dict = {
        "term": term.name,
        "stats": {"sections": len(term.sections), "constraints": len(active),
                  "variables": len(ctx.model.Proto().variables),
                  "cp_sat_rules": len(ctx.model.Proto().constraints),
                  "solve_seconds": round(solver.WallTime(), 2), "seed": seed},
        "unsupported": [{"id": c["id"], "source": c.get("source")} for c in unsupported],
    }

    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        tt = {}
        for s in term.sections:
            k = next(k for k, v in enumerate(ctx.x[s.id]) if solver.BooleanValue(v))
            tt[s.id] = s.options[k]
        out["status"] = "SOLVED" if st == cp_model.OPTIMAL else "SOLVED_TIME_LIMIT"
        out["timetable"] = [{"section": s.id, "course": s.course, "component": s.component,
                             "instructor": s.instructor, "time": tt[s.id].label(),
                             "days": tt[s.id].days, "start": tt[s.id].start, "end": tt[s.id].end}
                            for s in term.sections]
        unmet = {}
        for w, v, cid in ctx.penalties:
            if solver.BooleanValue(v):
                unmet[cid] = unmet.get(cid, 0) + 1
        out["soft_unmet"] = unmet  # soft constraint id -> how many sections break it
        out["check"] = checker.check(term, active, tt)
    elif st == cp_model.INFEASIBLE:
        out["status"] = "NO_SOLUTION"
        conflict = minimal_conflict(term, active, seed=seed)
        out["conflict"] = [{"id": c["id"], "type": c["type"], "params": c["params"],
                            "source": c.get("source")} for c in conflict]
        if not conflict:
            out["conflict_note"] = ("impossible even with no department constraints: the built-in rule "
                                    "(no instructor in two places at once) cannot be met with this offering")
    else:
        out["status"] = "UNKNOWN"
        out["note"] = "time limit reached before any timetable was found; try a longer limit"
    out["stats"]["total_seconds"] = round(time.perf_counter() - t0, 2)
    return out


# ---------------------------------------------------------------- preferences-first mode


def _as_hard(c: dict) -> dict:
    h = {k: v for k, v in c.items() if k != "weight"}
    h["hard"] = True
    return h


def solve_preferences_first(term_source, constraints: list[dict], relaxed: list[str] = (),
                            time_limit: float = 60, seed: int = 1, max_clashes: int = 5) -> dict:
    """Try to meet EVERY preference. Only if that is impossible, say which preferences clash.

    1. Every soft constraint (preference) is treated as a hard rule, except the ids in
       `relaxed`, which stay soft (still tried, may be broken).
    2. Possible -> normal result, every non-relaxed preference met.
    3. Impossible because of the real hard rules -> NO_SOLUTION (same as solve()).
    4. Impossible only because of preferences -> PREFERENCES_CLASH with:
       - clashes: groups of preferences that cannot all hold together
       - fixes: for each preference in a clash, whether relaxing it alone removes that clash
       Nothing is relaxed automatically: the department (or the agent, for approval) picks.
    """
    raw = term_source if isinstance(term_source, dict) else load_term(term_source).raw
    errors = check_term(raw) + check_constraints(constraints, raw)
    unknown = [r for r in relaxed if r not in {c.get("id") for c in constraints}]
    errors += [f"--relax: no constraint with id {r!r}" for r in unknown]
    if errors:
        return {"status": "INVALID_INPUT", "errors": errors}

    prefs = [c for c in constraints if c["type"] != "unsupported" and not c.get("hard", True)
             and c["id"] not in relaxed]
    hardened = [_as_hard(c) if c in prefs else c for c in constraints]
    res = solve(raw, hardened, time_limit, seed)
    res["mode"] = "preferences_first"
    res["preferences_tried_as_hard"] = [c["id"] for c in prefs]
    res["relaxed"] = list(relaxed)
    if res["status"] != "NO_SOLUTION":
        return res

    term = load_term(raw)
    hard = [c for c in constraints if c["type"] != "unsupported" and c.get("hard", True)]
    pref_ids = {c["id"] for c in prefs}
    if not any(c["id"] in pref_ids for c in res["conflict"]):
        return res  # the real hard rules clash; preferences are not the problem

    # Collect independent groups of clashing preferences.
    still_relaxed_soft = [c for c in constraints if c.get("id") in relaxed]
    fixed = hard + still_relaxed_soft
    remaining = [_as_hard(c) for c in prefs]
    clashes = []
    while remaining and len(clashes) < max_clashes:
        if _feasible(term, fixed + remaining, time_limit, seed) is not False:
            break
        group = minimal_conflict(term, remaining, time_limit, seed, fixed=fixed)
        if not group:
            break
        # Relaxing any one member removes THIS clash (the group is minimal). Also say whether
        # relaxing it alone makes every other preference fit, so the cheapest fix is visible.
        all_prefs = [_as_hard(c) for c in prefs]
        fixes = []
        for p in group:
            rest = [q for q in all_prefs if q["id"] != p["id"]]
            fixes.append({"relax": p["id"],
                          "then_everything_else_fits": _feasible(term, fixed + rest, time_limit, seed) is True})
        original = {c["id"]: c for c in prefs}
        clashes.append({"preferences": [{"id": p["id"], "type": p["type"], "params": p["params"],
                                         "source": p.get("source"), "weight": original[p["id"]].get("weight")}
                                        for p in group],
                        "fixes": fixes})
        ids = {p["id"] for p in group}
        remaining = [r for r in remaining if r["id"] not in ids]
    return {"status": "PREFERENCES_CLASH", "mode": "preferences_first", "term": term.name,
            "relaxed": list(relaxed), "clashes": clashes,
            "next_step": "pick a preference to relax in each clash and run again with --relax ID "
                         "(or run with --mode weights for an automatic compromise)"}
