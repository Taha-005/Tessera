"""T-016 tests: round trip per type; rejection of unknown type, free-text names and missing parameters."""

import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from tessera.data.constraints import (
    SUPPORTED_TYPES,
    dump_constraint,
    parse_constraint,
    parse_constraints,
    validate_references,
)
from tessera.data.term_io import load_json

TERM = load_json(
    Path(__file__).resolve().parents[2]
    / "data"
    / "synthetic"
    / "example_term"
    / "term.json"
)
MAJORS = {
    "ECMP",
    "EECE",
    "EMCH",
    "INDE",
    "CHME",
    "CSEN",
}  # codes seen in AUB restrictions

COMMON = {
    "term_id": "syn-2026-fall",
    "source": "unit test",
    "source_kind": "manual",
    "author": "tester",
    "created_at": "2026-11-14T10:00:00",
}

# one valid example per type, all referring to IDs in the synthetic term
EXAMPLES = {
    "no_clash_group": {
        "params": {"cohort_id": "C-E1", "course_ids": ["SYN 101", "SYN 102"]}
    },
    "clash_exception": {
        "params": {
            "scope": "course",
            "a": "SYN 201",
            "b": "SYN 102",
            "reason": "approved overlap",
        }
    },
    "instructor_days": {
        "params": {"instructor_id": "I-02", "allowed_patterns": ["TR"]}
    },
    "instructor_time_window": {
        "params": {"instructor_id": "I-03", "earliest": "14:00"}
    },
    "component_time_window": {
        "params": {
            "course_id": "SYN 101",
            "component": "recitation",
            "earliest": "17:00",
        }
    },
    "room_requirement": {
        "params": {
            "course_id": "SYN 102",
            "component": "lab",
            "room_type": "lab",
            "slack": 2,
        }
    },
    "parallel_rooms": {
        "params": {
            "course_id": "SYN 101",
            "component": "in_lecture_lab",
            "rooms": 2,
            "room_type": "lab",
        }
    },
    "major_restriction": {
        "params": {
            "section_ids": ["90001"],
            "allowed_majors": ["EMCH"],
            "day_pattern": "WM",
        }
    },
    "external_block": {
        "params": {"cohort_id": "C-E1", "external_meeting_id": "X-MATH"}
    },
    "preference": {
        "hard": False,
        "weight": 5,
        "params": {
            "target_type": "instructor_time_window",
            "target": {"instructor_id": "I-01", "earliest": "09:00"},
        },
    },
    "stability": {"hard": False, "weight": 10, "params": {}},
}


def make(t: str, **over) -> dict:
    d = {"id": f"c-{t}", "type": t, **COMMON, **copy.deepcopy(EXAMPLES[t])}
    d.update(over)
    return d


def test_examples_cover_all_eleven_types():
    assert sorted(EXAMPLES) == sorted(SUPPORTED_TYPES) and len(SUPPORTED_TYPES) == 11


# ---------------------------------------------------------------- round trip per type


@pytest.mark.parametrize("t", sorted(EXAMPLES))
def test_round_trip(t):
    c = parse_constraint(make(t))
    assert c.type == t
    again = parse_constraint(dump_constraint(c))
    assert again == c
    assert parse_constraint(c.model_dump_json()) == c


@pytest.mark.parametrize("t", sorted(EXAMPLES))
def test_references_resolve(t):
    assert validate_references(parse_constraint(make(t)), TERM, MAJORS) == []


def test_list_round_trip():
    cs = parse_constraints([make(t) for t in EXAMPLES])
    assert [c.type for c in cs] == list(EXAMPLES)


def test_days_normalized():
    assert parse_constraint(make("major_restriction")).params.day_pattern == "MW"


# ---------------------------------------------------------------- unknown type


@pytest.mark.parametrize("bad", ["no_overlap", "room_preference", "", "NO_CLASH_GROUP"])
def test_unknown_type_rejected(bad):
    d = make("no_clash_group")
    d["type"] = bad
    with pytest.raises(ValidationError, match="tag"):
        parse_constraint(d)


def test_missing_type_rejected():
    d = make("no_clash_group")
    del d["type"]
    with pytest.raises(ValidationError):
        parse_constraint(d)


def test_preference_cannot_wrap_preference_or_unknown():
    for target in ("preference", "stability", "unsupported", "made_up"):
        d = make("preference")
        d["params"]["target_type"] = target
        with pytest.raises(ValidationError):
            parse_constraint(d)


# ---------------------------------------------------------------- free-text names


@pytest.mark.parametrize(
    "t,field,name",
    [
        ("instructor_days", "instructor_id", "Dr. Kabalan"),
        ("instructor_time_window", "instructor_id", "the part-timer"),
        ("no_clash_group", "cohort_id", "second year CCE students"),
        ("component_time_window", "course_id", "Electric Circuits"),
        ("external_block", "external_meeting_id", "MECHE's TR course"),
    ],
)
def test_free_text_name_rejected(t, field, name):
    d = make(t)
    d["params"][field] = name
    errs = validate_references(parse_constraint(d), TERM, MAJORS)
    assert errs and "IDs, not names" in errs[0]


def test_free_text_course_in_group_rejected():
    d = make("no_clash_group")
    d["params"]["course_ids"] = ["SYN 101", "Signals and Systems"]
    assert any(
        "Signals and Systems" in e
        for e in validate_references(parse_constraint(d), TERM)
    )


def test_free_text_inside_preference_rejected():
    d = make("preference")
    d["params"]["target"]["instructor_id"] = "Prof. X"
    assert validate_references(parse_constraint(d), TERM)


def test_major_names_rejected():
    d = make("major_restriction")
    d["params"]["allowed_majors"] = ["Mechanical Engineering"]
    with pytest.raises(ValidationError, match="not major codes"):
        parse_constraint(d)


def test_unknown_major_code_rejected():
    d = make("major_restriction")
    d["params"]["allowed_majors"] = ["ABCD"]
    assert validate_references(parse_constraint(d), TERM, MAJORS) == [
        "unknown major code 'ABCD'"
    ]


def test_wrong_term_rejected():
    d = make("stability", term_id="2025-26-fall")
    assert "term" in validate_references(parse_constraint(d), TERM)[0]


# ---------------------------------------------------------------- missing parameters


@pytest.mark.parametrize(
    "t,field",
    [
        ("no_clash_group", "cohort_id"),
        ("no_clash_group", "course_ids"),
        ("clash_exception", "reason"),
        ("instructor_days", "allowed_patterns"),
        ("component_time_window", "component"),
        ("room_requirement", "room_type"),
        ("parallel_rooms", "rooms"),
        ("major_restriction", "allowed_majors"),
        ("external_block", "external_meeting_id"),
        ("preference", "target"),
    ],
)
def test_missing_param_rejected(t, field):
    d = make(t)
    del d["params"][field]
    with pytest.raises(ValidationError, match="Field required"):
        parse_constraint(d)


def test_window_needs_a_bound():
    d = make("instructor_time_window")
    d["params"] = {"instructor_id": "I-03"}
    with pytest.raises(ValidationError, match="earliest, latest or both"):
        parse_constraint(d)


@pytest.mark.parametrize(
    "field", ["id", "term_id", "source", "source_kind", "author", "created_at"]
)
def test_missing_common_field_rejected(field):
    d = make("no_clash_group")
    del d[field]
    with pytest.raises(ValidationError):
        parse_constraint(d)


def test_unknown_param_rejected():
    d = make("instructor_days")
    d["params"]["mornings_only"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        parse_constraint(d)


# ---------------------------------------------------------------- common-field rules


def test_hard_with_weight_rejected():
    with pytest.raises(ValidationError, match="hard constraint has no weight"):
        parse_constraint(make("no_clash_group", weight=3))


def test_soft_without_weight_rejected():
    with pytest.raises(ValidationError, match="soft constraint needs a weight"):
        parse_constraint(make("no_clash_group", hard=False))


@pytest.mark.parametrize("t", ["preference", "stability"])
def test_always_soft_types(t):
    with pytest.raises(ValidationError):
        parse_constraint(make(t, hard=True, weight=None))


def test_learned_needs_evidence():
    with pytest.raises(ValidationError, match="evidence"):
        parse_constraint(make("no_clash_group", source_kind="learned"))
    ok = parse_constraint(
        make(
            "no_clash_group", source_kind="learned", evidence="62% co-enrolled, 2023-25"
        )
    )
    assert ok.evidence


def test_active_needs_approval():
    with pytest.raises(ValidationError, match="approved_by and approved_at"):
        parse_constraint(make("no_clash_group", status="active"))
    ok = parse_constraint(
        make(
            "no_clash_group",
            status="active",
            approved_by="scheduler",
            approved_at="2026-11-14T11:00:00",
        )
    )
    assert ok.status.value == "active"


def test_approved_before_created_rejected():
    with pytest.raises(ValidationError, match="before created_at"):
        parse_constraint(
            make("no_clash_group", approved_by="x", approved_at="2026-11-13T00:00:00")
        )


def test_room_requirement_target_is_exclusive():
    d = make("room_requirement")
    d["params"]["section_id"] = "90002"
    with pytest.raises(ValidationError, match="not both"):
        parse_constraint(d)


# ---------------------------------------------------------------- unsupported path


def unsupported(**over):
    d = {
        "id": "c-u",
        "type": "unsupported",
        **COMMON,
        "source_kind": "note",
        "params": {
            "original_text": "Dr. X wants a room with a window",
            "reason": "no room-feature type",
        },
    }
    d.update(over)
    return d


def test_unsupported_round_trip():
    c = parse_constraint(unsupported())
    assert parse_constraint(dump_constraint(c)) == c
    assert c.type not in SUPPORTED_TYPES


def test_unsupported_can_be_rejected():
    assert parse_constraint(unsupported(status="rejected")).status.value == "rejected"


def test_unsupported_never_active():
    with pytest.raises(ValidationError, match="only be proposed or rejected"):
        parse_constraint(
            unsupported(
                status="active", approved_by="x", approved_at="2026-11-14T11:00:00"
            )
        )


def test_bad_time_in_window_rejected():
    d = make("component_time_window")
    d["params"]["earliest"] = "25:00"
    with pytest.raises(ValidationError, match="HH:MM"):
        parse_constraint(d)


def test_bad_day_in_optional_fields_rejected():
    d = make("major_restriction")
    d["params"]["day_pattern"] = "MX"
    with pytest.raises(ValidationError, match="day"):
        parse_constraint(d)
    d = make("instructor_time_window")
    d["params"]["days"] = "MMW"
    with pytest.raises(ValidationError, match="day"):
        parse_constraint(d)
