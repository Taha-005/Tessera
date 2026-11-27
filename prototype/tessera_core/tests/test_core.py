"""Each constraint type: one test where it holds, one where it is broken on purpose.
Run: python3 -m pytest -q tests"""

import copy

import pytest

from core.checker import check
from core.solve import solve
from core.term import TimeOption, load_term

TERM = {
    "term": "tiny test term",
    "slot_kinds": {
        "MWF": {"day_patterns": ["MWF"], "minutes": 50, "starts": ["08:00", "09:00", "10:00"]},
        "TR": {"day_patterns": ["TR"], "minutes": 75, "starts": ["08:00", "09:30"]},
    },
    "instructors": ["p", "q", "r"],
    "courses": [
        {"id": "A", "component": "lecture", "slot_kinds": ["MWF", "TR"],
         "sections": [{"id": "A-1", "instructor": "p"}, {"id": "A-2", "instructor": "p"}]},
        {"id": "B", "component": "lecture", "slot_kinds": ["MWF", "TR"],
         "sections": [{"id": "B-1", "instructor": "q"}]},
        {"id": "C", "component": "lab", "slot_kinds": ["MWF"],
         "sections": [{"id": "C-1", "instructor": "r"}]},
    ],
}


def con(cid, ctype, hard=True, weight=None, **params):
    c = {"id": cid, "type": ctype, "hard": hard, "params": params, "source": "test"}
    if weight is not None:
        c["weight"] = weight
    return c


def run(constraints, term=TERM):
    return solve(copy.deepcopy(term), constraints, time_limit=10)


def times(res):
    return {r["section"]: r for r in res["timetable"]}


# ------------------------------------------------------------- input check

@pytest.mark.parametrize("bad, expected", [
    (con("X", "instructor_days", instructor_id="nobody", allowed_patterns=["TR"]), "unknown instructor"),
    (con("X", "component_time_window", component="lecture", latest="4pm"), "HH:MM"),
    (con("X", "teleport", course_id="A"), "unknown type"),
    (con("X", "instructor_days", weight=3, instructor_id="p", allowed_patterns=["TR"]),
     "hard constraint has no weight"),
    (con("X", "instructor_days", hard=False, instructor_id="p", allowed_patterns=["TR"]), "needs an integer weight"),
    (con("X", "no_clash_group", cohort_id="E2", course_ids=["A", "Z"]), "unknown course"),
    (con("X", "course_days", course_id="A", allowed_patterns=["MXF"]), "bad day pattern"),
    (con("X", "instructor_days", instructor_id="p", allowed_patterns=["TR"], extra=1), "unexpected param"),
])
def test_bad_input_is_rejected_before_solving(bad, expected):
    res = run([bad])
    assert res["status"] == "INVALID_INPUT"
    assert any(expected in e for e in res["errors"]), res["errors"]


def test_duplicate_ids_rejected():
    c = con("X", "course_days", course_id="A", allowed_patterns=["TR"])
    assert run([c, dict(c)])["status"] == "INVALID_INPUT"


# ------------------------------------------------------------- time filters

def test_instructor_days_holds():
    res = run([con("D1", "instructor_days", instructor_id="p", allowed_patterns=["TR"])])
    assert res["status"] == "SOLVED" and res["check"]["passed"]
    assert all(times(res)[s]["days"] == "TR" for s in ("A-1", "A-2"))


def test_instructor_days_broken():
    # p has 2 sections; TR-only + "before 09:30" leaves one TR slot -> impossible.
    res = run([con("D1", "instructor_days", instructor_id="p", allowed_patterns=["TR"]),
               con("W1", "instructor_time_window", instructor_id="p", latest="09:30"),
               con("OK", "course_days", course_id="B", allowed_patterns=["MWF"])])
    assert res["status"] == "NO_SOLUTION"
    assert {c["id"] for c in res["conflict"]} == {"D1", "W1"}  # OK is not blamed


def test_instructor_time_window_broken():
    res = run([con("W1", "instructor_time_window", instructor_id="q", earliest="12:00")])
    assert res["status"] == "NO_SOLUTION" and [c["id"] for c in res["conflict"]] == ["W1"]


def test_instructor_time_window_only_on_given_days():
    res = run([con("W1", "instructor_time_window", instructor_id="q", earliest="12:00", days="TR")])
    assert res["status"] == "SOLVED" and times(res)["B-1"]["days"] == "MWF"


def test_component_time_window():
    res = run([con("T1", "component_time_window", component="lecture", earliest="09:00")])
    assert res["status"] == "SOLVED" and res["check"]["passed"]
    assert all(r["start"] >= 540 for r in res["timetable"] if r["component"] == "lecture")
    res = run([con("T1", "component_time_window", component="lab", earliest="11:00")])
    assert res["status"] == "NO_SOLUTION" and [c["id"] for c in res["conflict"]] == ["T1"]


def test_course_days():
    res = run([con("K1", "course_days", course_id="B", allowed_patterns=["TR"])])
    assert times(res)["B-1"]["days"] == "TR"


# ------------------------------------------------------------- groups

def test_no_clash_group_holds():
    res = run([con("G1", "no_clash_group", cohort_id="E", course_ids=["A", "B", "C"])])
    assert res["status"] == "SOLVED" and res["check"]["passed"]
    assert len(res["check"]["example_schedules"]["G1"]) == 4  # every section has a full schedule


def test_no_clash_group_broken():
    # Force B and C into the same 08:00 MWF slot -> they always clash.
    pin = [con("P1", "course_days", course_id="B", allowed_patterns=["MWF"]),
           con("P2", "component_time_window", component="lecture", course_id="B", latest="08:50"),
           con("P3", "component_time_window", component="lab", latest="08:50")]
    res = run(pin + [con("G1", "no_clash_group", cohort_id="E", course_ids=["B", "C"])])
    assert res["status"] == "NO_SOLUTION"
    assert "G1" in {c["id"] for c in res["conflict"]}


def test_clash_exception_lifts_the_clash():
    pin = [con("P1", "course_days", course_id="B", allowed_patterns=["MWF"]),
           con("P2", "component_time_window", component="lecture", course_id="B", latest="08:50"),
           con("P3", "component_time_window", component="lab", latest="08:50")]
    res = run(pin + [con("G1", "no_clash_group", cohort_id="E", course_ids=["B", "C"]),
                     con("X1", "clash_exception", a="B", b="C", reason="students take C in summer")])
    assert res["status"] == "SOLVED" and res["check"]["passed"]


# ------------------------------------------------------------- soft, unsupported, built-in

def test_soft_preference_is_followed_when_possible():
    res = run([con("S1", "instructor_time_window", hard=False, weight=5, instructor_id="q", earliest="09:00")])
    assert res["status"] == "SOLVED" and times(res)["B-1"]["start"] >= 540 and not res["soft_unmet"]


def test_soft_preference_broken_is_reported_not_fatal():
    res = run([con("S1", "instructor_time_window", hard=False, weight=5, instructor_id="q", earliest="12:00")])
    assert res["status"] == "SOLVED" and res["soft_unmet"] == {"S1": 1}


def test_unsupported_is_reported_and_ignored():
    res = run([{"id": "U1", "type": "unsupported", "params": {}, "source": "Dr p likes quiet rooms"}])
    assert res["status"] == "SOLVED" and res["unsupported"][0]["id"] == "U1"


def test_builtin_instructor_overload():
    term = copy.deepcopy(TERM)
    term["courses"][2]["sections"] = [{"id": f"C-{i}", "instructor": "r"} for i in range(1, 5)]  # 4 labs, 3 slots
    res = run([], term)
    assert res["status"] == "NO_SOLUTION" and res["conflict"] == [] and "built-in" in res["conflict_note"]


# ------------------------------------------------------------- determinism and checker independence

def test_same_input_same_timetable():
    cs = [con("G1", "no_clash_group", cohort_id="E", course_ids=["A", "B", "C"])]
    assert times(run(cs)) == times(run(cs))


def test_checker_catches_a_bad_timetable():
    term = load_term(copy.deepcopy(TERM))
    slot = TimeOption("MWF", 480, 530)
    tt = {s.id: slot for s in term.sections}  # everything at the same time
    cs = [con("D1", "instructor_days", instructor_id="p", allowed_patterns=["TR"]),
          con("G1", "no_clash_group", cohort_id="E", course_ids=["A", "B"])]
    rep = check(term, cs, tt)
    assert not rep["passed"]
    text = " ".join(rep["problems"])
    assert "built-in" in text and "D1" in text and "G1" in text


# ------------------------------------------------------------- preferences-first mode

from core.solve import solve_preferences_first  # noqa: E402


def pf(constraints, relaxed=(), term=TERM):
    return solve_preferences_first(copy.deepcopy(term), constraints, list(relaxed), time_limit=10)


def test_prefs_first_all_preferences_met_when_possible():
    res = pf([con("S1", "instructor_time_window", hard=False, weight=1, instructor_id="q", earliest="09:00"),
              con("S2", "course_days", hard=False, weight=1, course_id="A", allowed_patterns=["TR"])])
    assert res["status"] == "SOLVED" and res["check"]["passed"]
    assert set(res["preferences_tried_as_hard"]) == {"S1", "S2"} and not res["soft_unmet"]


def test_prefs_first_reports_clash_and_does_not_relax_by_itself():
    # q prefers before 09:00 AND after 09:00 -> impossible together; S3 fits and must not be blamed.
    cs = [con("S1", "instructor_time_window", hard=False, weight=1, instructor_id="q", latest="09:00"),
          con("S2", "instructor_time_window", hard=False, weight=2, instructor_id="q", earliest="09:00"),
          con("S3", "course_days", hard=False, weight=1, course_id="A", allowed_patterns=["TR"])]
    res = pf(cs)
    assert res["status"] == "PREFERENCES_CLASH" and "timetable" not in res
    assert len(res["clashes"]) == 1
    assert {p["id"] for p in res["clashes"][0]["preferences"]} == {"S1", "S2"}
    assert all(f["then_everything_else_fits"] for f in res["clashes"][0]["fixes"])


def test_prefs_first_relax_then_solves():
    cs = [con("S1", "instructor_time_window", hard=False, weight=1, instructor_id="q", latest="09:00"),
          con("S2", "instructor_time_window", hard=False, weight=2, instructor_id="q", earliest="09:00")]
    res = pf(cs, relaxed=["S1"])
    assert res["status"] == "SOLVED" and res["soft_unmet"] == {"S1": 1}
    assert times(res)["B-1"]["start"] >= 540  # S2 (kept as a rule) is met


def test_prefs_first_two_independent_clashes():
    cs = [con("S1", "instructor_time_window", hard=False, weight=1, instructor_id="q", latest="09:00"),
          con("S2", "instructor_time_window", hard=False, weight=1, instructor_id="q", earliest="09:00"),
          con("S3", "instructor_time_window", hard=False, weight=1, instructor_id="r", earliest="11:00")]
    res = pf(cs)
    groups = [{p["id"] for p in c["preferences"]} for c in res["clashes"]]
    assert {"S1", "S2"} in groups and {"S3"} in groups


def test_prefs_first_hard_conflict_is_still_no_solution():
    res = pf([con("H1", "instructor_time_window", instructor_id="r", earliest="11:00"),
              con("S1", "course_days", hard=False, weight=1, course_id="A", allowed_patterns=["TR"])])
    assert res["status"] == "NO_SOLUTION" and [c["id"] for c in res["conflict"]] == ["H1"]


def test_prefs_first_unknown_relax_id_rejected():
    assert pf([], relaxed=["NOPE"])["status"] == "INVALID_INPUT"
