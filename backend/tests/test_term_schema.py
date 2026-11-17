"""T-015 tests: valid and invalid term data, JSON and CSV round trips."""

import copy
import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tessera.data.schema import TermData, parse_days, to_minutes
from tessera.data.term_io import (
    TermDataError,
    load_csv_dir,
    load_json,
    save_csv_dir,
    save_json,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "example_term"


@pytest.fixture
def raw() -> dict:
    return json.loads((EXAMPLES / "term.json").read_text())


def invalid(raw: dict, match: str):
    with pytest.raises(ValidationError, match=match):
        TermData.model_validate(raw)


# ---------------------------------------------------------------- valid


def test_example_json_is_valid_and_synthetic():
    d = load_json(EXAMPLES / "term.json")
    assert d.provenance.synthetic is True
    assert len(d.sections) == 4


def test_example_csv_matches_json():
    assert load_csv_dir(EXAMPLES / "csv") == load_json(EXAMPLES / "term.json")


def test_json_round_trip(tmp_path):
    d = load_json(EXAMPLES / "term.json")
    save_json(d, tmp_path / "t.json")
    assert load_json(tmp_path / "t.json") == d


def test_csv_round_trip(tmp_path):
    d = load_json(EXAMPLES / "term.json")
    save_csv_dir(d, tmp_path / "csv")
    assert load_csv_dir(tmp_path / "csv") == d


def test_minimal_term_is_valid():
    TermData.model_validate(
        {
            "provenance": {"synthetic": False, "source": "unit test"},
            "term": {
                "id": "t",
                "name": "T",
                "season": "spring",
                "academic_year": "2025-26",
            },
            "courses": [{"id": "X 1"}],
        }
    )


def test_section_without_instructor_or_capacity_is_allowed(raw):
    d = TermData.model_validate(raw)
    s = next(s for s in d.sections if s.id == "90003")
    assert s.capacity is None and s.instructor_ids == []


def test_days_are_canonicalised():
    assert parse_days("fwm") == "MWF"
    assert parse_days("RT") == "TR"


def test_to_minutes():
    assert to_minutes("08:30") == 510
    assert to_minutes("23:59") == 1439


def test_parallel_rooms_and_in_lecture_lab(raw):
    d = TermData.model_validate(raw)
    m = d.sections[0].meetings[1]
    assert m.component.value == "in_lecture_lab" and m.rooms_needed == 2


# ---------------------------------------------------------------- invalid values


@pytest.mark.parametrize("days", ["MXF", "MMW", ""])
def test_bad_days(raw, days):
    raw["slot_grid"][0]["days"] = days
    invalid(raw, "day")


@pytest.mark.parametrize("t", ["8:00", "24:00", "08:60", "0800"])
def test_bad_time(raw, t):
    raw["slot_grid"][0]["start"] = t
    invalid(raw, "HH:MM")


def test_start_after_end(raw):
    raw["external_meetings"][0]["start"], raw["external_meetings"][0]["end"] = (
        "13:00",
        "12:00",
    )
    invalid(raw, "before end")


def test_unknown_component(raw):
    raw["sections"][0]["meetings"][0]["component"] = "seminar"
    invalid(raw, "component")


def test_zero_duration(raw):
    raw["sections"][0]["meetings"][0]["duration_min"] = 0
    invalid(raw, "duration_min")


def test_rooms_needed_zero(raw):
    raw["sections"][0]["meetings"][1]["rooms_needed"] = 0
    invalid(raw, "rooms_needed")


def test_negative_capacity(raw):
    raw["sections"][0]["capacity"] = -1
    invalid(raw, "capacity")


def test_unknown_field_rejected(raw):
    raw["courses"][0]["professor_prefers_mornings"] = True
    invalid(raw, "Extra inputs")


def test_synthetic_needs_generator(raw):
    del raw["provenance"]["generator"]
    invalid(raw, "generator")


def test_no_clash_group_needs_two_courses(raw):
    raw["no_clash_groups"][0]["course_ids"] = ["SYN 101"]
    invalid(raw, "course_ids")


def test_clash_exception_same_course(raw):
    raw["clash_exceptions"][0]["course_b"] = raw["clash_exceptions"][0]["course_a"]
    invalid(raw, "two different courses")


def test_bad_academic_year(raw):
    raw["term"]["academic_year"] = "2026"
    invalid(raw, "academic_year")


# ---------------------------------------------------------------- invalid references


def test_section_unknown_course(raw):
    raw["sections"][0]["course_id"] = "NOPE 1"
    invalid(raw, "course 'NOPE 1' not found")


def test_section_unknown_instructor(raw):
    raw["sections"][0]["instructor_ids"] = ["I-99"]
    invalid(raw, "instructor 'I-99' not found")


def test_placement_unknown_room(raw):
    raw["sections"][1]["meetings"][0]["placement"]["room_ids"] = ["R-404"]
    invalid(raw, "room 'R-404' not found")


def test_group_unknown_cohort(raw):
    raw["no_clash_groups"][0]["cohort_id"] = "C-NOPE"
    invalid(raw, "cohort 'C-NOPE' not found")


def test_coupled_unknown_course(raw):
    raw["courses"][2]["coupled_courses"] = ["SYN 999"]
    invalid(raw, "coupled course 'SYN 999' not found")


def test_duplicate_course_ids(raw):
    raw["courses"].append(copy.deepcopy(raw["courses"][0]))
    invalid(raw, "duplicate course")


def test_duplicate_meeting_ids_across_sections(raw):
    raw["sections"][1]["meetings"][0]["id"] = raw["sections"][0]["meetings"][0]["id"]
    invalid(raw, "duplicate meeting")


# ---------------------------------------------------------------- file-level errors (F11)


def test_malformed_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(TermDataError, match="not valid JSON"):
        load_json(p)


def test_invalid_json_gives_readable_error(tmp_path, raw):
    raw["sections"][0]["course_id"] = "NOPE 1"
    p = tmp_path / "t.json"
    p.write_text(json.dumps(raw))
    with pytest.raises(TermDataError, match="invalid term data"):
        load_json(p)


def test_csv_missing_required_file(tmp_path):
    save_csv_dir(load_json(EXAMPLES / "term.json"), tmp_path)
    (tmp_path / "courses.csv").unlink()
    with pytest.raises(TermDataError, match="missing required file courses.csv"):
        load_csv_dir(tmp_path)


def test_csv_wrong_columns(tmp_path):
    save_csv_dir(load_json(EXAMPLES / "term.json"), tmp_path)
    (tmp_path / "rooms.csv").write_text("id,room_type,cap\nR,lab,10\n")
    with pytest.raises(TermDataError, match="rooms.csv: expected columns"):
        load_csv_dir(tmp_path)


def test_csv_meeting_for_unknown_section(tmp_path):
    save_csv_dir(load_json(EXAMPLES / "term.json"), tmp_path)
    with (tmp_path / "meetings.csv").open("a", newline="") as f:
        csv.writer(f).writerow(
            ["M-X", "00000", "lecture", "50", "", "", "1", "", "", "", ""]
        )
    with pytest.raises(TermDataError, match="section '00000' not in sections.csv"):
        load_csv_dir(tmp_path)


def test_csv_bad_synthetic_flag(tmp_path):
    save_csv_dir(load_json(EXAMPLES / "term.json"), tmp_path)
    p = tmp_path / "term.csv"
    p.write_text(p.read_text().replace(",true,", ",yes,"))
    with pytest.raises(TermDataError, match="synthetic must be"):
        load_csv_dir(tmp_path)
