"""Build the synthetic example term in both formats (JSON + CSV folder).

All entities are invented (course codes 'SYN ...', instructors 'I-..'). The file
is labeled synthetic in its provenance, as Section 8.3 requires.
Run from backend/:  uv run python -m scripts.make_example_term
"""

from datetime import date
from pathlib import Path

from tessera.data.schema import TermData
from tessera.data.term_io import save_csv_dir, save_json

OUT = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "example_term"

data = TermData.model_validate(
    {
        "provenance": {
            "synthetic": True,
            "source": "hand-written example for T-015",
            "generator": "backend/scripts/make_example_term.py",
            "seed": 0,
            "notes": "SYNTHETIC. Invented courses, instructors and rooms. Not AUB data.",
        },
        "term": {
            "id": "syn-2026-fall",
            "name": "Synthetic Fall 2026",
            "season": "fall",
            "academic_year": "2026-27",
        },
        "slot_grid": [
            {
                "id": "MWF-0800",
                "days": "MWF",
                "start": "08:00",
                "end": "08:50",
                "kind": "lecture",
            },
            {
                "id": "MWF-0900",
                "days": "MWF",
                "start": "09:00",
                "end": "09:50",
                "kind": "lecture",
            },
            {
                "id": "TR-0800",
                "days": "TR",
                "start": "08:00",
                "end": "09:15",
                "kind": "lecture",
            },
            {
                "id": "M-1400-LAB",
                "days": "M",
                "start": "14:00",
                "end": "16:45",
                "kind": "lab",
            },
            {
                "id": "W-1700-REC",
                "days": "W",
                "start": "17:00",
                "end": "18:45",
                "kind": "recitation",
            },
        ],
        "courses": [
            {"id": "SYN 101", "title": "Synthetic Circuits", "credits": 3},
            {"id": "SYN 102", "title": "Synthetic Programming", "credits": 3},
            {
                "id": "SYN 201",
                "title": "Synthetic Signals",
                "credits": 3,
                "coupled_courses": ["SYN 201L"],
            },
            {
                "id": "SYN 201L",
                "title": "Synthetic Signals Lab",
                "credits": 1,
                "coupled_courses": ["SYN 201"],
            },
        ],
        "sections": [
            {  # lecture + recitation + in-lecture lab needing 2 lab rooms at once (H7)
                "id": "90001",
                "course_id": "SYN 101",
                "number": "1",
                "capacity": 36,
                "instructor_ids": ["I-01"],
                "meetings": [
                    {
                        "id": "90001-L",
                        "component": "lecture",
                        "duration_min": 50,
                        "allowed_day_patterns": ["MWF"],
                        "room_type": "classroom",
                    },
                    {
                        "id": "90001-IL",
                        "component": "in_lecture_lab",
                        "duration_min": 50,
                        "room_type": "lab",
                        "rooms_needed": 2,
                    },
                    {
                        "id": "90001-R",
                        "component": "recitation",
                        "duration_min": 105,
                        "room_type": "classroom",
                    },
                ],
            },
            {  # one CRN bundling a lecture and a lab (like a 'Multiple Sessions' section)
                "id": "90002",
                "course_id": "SYN 102",
                "number": "1",
                "capacity": 18,
                "instructor_ids": ["I-02"],
                "meetings": [
                    {
                        "id": "90002-L",
                        "component": "lecture",
                        "duration_min": 50,
                        "allowed_day_patterns": ["MWF", "TR"],
                        "room_type": "classroom",
                        "placement": {
                            "days": "MWF",
                            "start": "09:00",
                            "end": "09:50",
                            "room_ids": ["R-A101"],
                        },
                    },
                    {
                        "id": "90002-B",
                        "component": "lab",
                        "duration_min": 105,
                        "room_type": "lab",
                        "placement": {
                            "days": "M",
                            "start": "14:00",
                            "end": "15:45",
                            "room_ids": ["R-LAB1"],
                        },
                    },
                ],
            },
            {  # missing instructor and capacity: allowed by the schema, blocks solving later (F17)
                "id": "90003",
                "course_id": "SYN 201",
                "number": "1",
                "meetings": [
                    {
                        "id": "90003-L",
                        "component": "lecture",
                        "duration_min": 75,
                        "allowed_day_patterns": ["TR"],
                        "room_type": "classroom",
                    }
                ],
            },
            {  # separately registered lab course, coupled to SYN 201 through the course
                "id": "90004",
                "course_id": "SYN 201L",
                "number": "1",
                "capacity": 16,
                "instructor_ids": ["I-03"],
                "meetings": [
                    {
                        "id": "90004-B",
                        "component": "lab",
                        "duration_min": 165,
                        "room_type": "lab",
                    }
                ],
            },
        ],
        "instructors": [
            {
                "id": "I-01",
                "kind": "full_time",
                "availability": [{"days": "MWF", "start": "08:00", "end": "17:00"}],
            },
            {"id": "I-02", "kind": "full_time"},
            {
                "id": "I-03",
                "kind": "part_time",
                "availability": [{"days": "MTWRF", "start": "14:00", "end": "19:00"}],
            },
        ],
        "rooms": [
            {
                "id": "R-A101",
                "building": "Synthetic Hall",
                "name": "101",
                "room_type": "classroom",
                "capacity": 40,
            },
            {
                "id": "R-LAB1",
                "building": "Synthetic Hall",
                "name": "Lab 1",
                "room_type": "lab",
                "capacity": 20,
            },
            {
                "id": "R-LAB2",
                "building": "Synthetic Hall",
                "name": "Lab 2",
                "room_type": "lab",
                "capacity": 20,
            },
        ],
        "room_pools": [{"room_type": "e_classroom", "count": 1, "capacity": 30}],
        "cohorts": [
            {"id": "C-E1", "kind": "year_major", "label": "Synthetic E1", "size": 150},
            {
                "id": "C-OUT",
                "kind": "outside_major",
                "label": "Synthetic outside major",
                "size": 40,
            },
        ],
        "no_clash_groups": [
            {
                "id": "G-E1",
                "cohort_id": "C-E1",
                "course_ids": ["SYN 101", "SYN 102"],
                "source": "synthetic example",
            },
        ],
        "external_meetings": [
            {
                "id": "X-MATH",
                "cohort_id": "C-E1",
                "label": "Synthetic math course",
                "days": "TR",
                "start": "11:00",
                "end": "12:15",
            },
        ],
        "clash_exceptions": [
            {
                "id": "E-1",
                "course_a": "SYN 201",
                "course_b": "SYN 102",
                "reason": "synthetic example",
                "approved_by": "synthetic chair",
                "approved_on": date(2026, 11, 14),
            },
        ],
    }
)

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    save_json(data, OUT / "term.json")
    save_csv_dir(data, OUT / "csv")
    print("wrote", OUT)
