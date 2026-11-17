"""Read and write TermData as one JSON file or as a folder of CSV files (T-015).

JSON is the canonical format (one file per term). The CSV folder is the
staff-friendly input format; it converts losslessly to and from JSON.
List-valued CSV cells use ';' as the separator. Empty cells mean "not set".
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tessera.data.schema import TermData

LIST_SEP = ";"

# file name -> column order. Columns ending in [] hold ';'-separated lists.
CSV_FILES: dict[str, list[str]] = {
    "term.csv": [
        "id",
        "name",
        "season",
        "academic_year",
        "schema_version",
        "synthetic",
        "source",
        "retrieved_on",
        "generator",
        "seed",
        "notes",
    ],
    "slots.csv": ["id", "days", "start", "end", "kind"],
    "courses.csv": ["id", "title", "credits", "coupled_courses[]"],
    "sections.csv": ["id", "course_id", "number", "capacity", "instructor_ids[]"],
    "meetings.csv": [
        "id",
        "section_id",
        "component",
        "duration_min",
        "allowed_day_patterns[]",
        "room_type",
        "rooms_needed",
        "placed_days",
        "placed_start",
        "placed_end",
        "placed_room_ids[]",
    ],
    "instructors.csv": ["id", "kind"],
    "availability.csv": ["instructor_id", "days", "start", "end"],
    "rooms.csv": ["id", "building", "name", "room_type", "capacity"],
    "room_pools.csv": ["room_type", "count", "capacity"],
    "cohorts.csv": ["id", "kind", "label", "size"],
    "no_clash_groups.csv": ["id", "cohort_id", "course_ids[]", "source"],
    "external_meetings.csv": ["id", "cohort_id", "label", "days", "start", "end"],
    "clash_exceptions.csv": [
        "id",
        "course_a",
        "course_b",
        "reason",
        "approved_by",
        "approved_on",
    ],
}
REQUIRED_FILES = {"term.csv", "courses.csv"}


class TermDataError(ValueError):
    """Raised with a readable message when a term file is invalid (F11)."""


# ---------------------------------------------------------------- JSON


def load_json(path: str | Path) -> TermData:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TermDataError(f"{path.name}: not valid JSON ({e})") from e
    return _validate(raw, path.name)


def save_json(data: TermData, path: str | Path) -> None:
    Path(path).write_text(
        data.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------- CSV


def _cell(v: str) -> str | None:
    v = (v or "").strip()
    return v or None


def _lst(v: str) -> list[str]:
    v = (v or "").strip()
    return [x.strip() for x in v.split(LIST_SEP) if x.strip()] if v else []


def _read(folder: Path, name: str) -> list[dict[str, str]]:
    p = folder / name
    if not p.exists():
        if name in REQUIRED_FILES:
            raise TermDataError(f"missing required file {name}")
        return []
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        expected = CSV_FILES[name]
        got = reader.fieldnames or []
        missing = [c for c in expected if c not in got]
        extra = [c for c in got if c not in expected]
        if missing or extra:
            raise TermDataError(
                f"{name}: expected columns {expected}; missing {missing}, unexpected {extra}"
            )
        return list(reader)


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def load_csv_dir(folder: str | Path) -> TermData:
    folder = Path(folder)
    if not folder.is_dir():
        raise TermDataError(f"{folder} is not a folder")

    term_rows = _read(folder, "term.csv")
    if len(term_rows) != 1:
        raise TermDataError(
            f"term.csv must have exactly one row, found {len(term_rows)}"
        )
    t = term_rows[0]
    synthetic = (t.get("synthetic") or "").strip().lower()
    if synthetic not in {"true", "false"}:
        raise TermDataError("term.csv: synthetic must be 'true' or 'false'")

    instructors: dict[str, dict[str, Any]] = {
        r["id"]: _drop_none(
            {"id": r["id"], "kind": _cell(r["kind"]), "availability": []}
        )
        for r in _read(folder, "instructors.csv")
    }
    for r in _read(folder, "availability.csv"):
        ins = instructors.get(r["instructor_id"])
        if ins is None:
            raise TermDataError(
                f"availability.csv: instructor {r['instructor_id']!r} not in instructors.csv"
            )
        ins["availability"].append(
            {"days": r["days"], "start": r["start"], "end": r["end"]}
        )

    sections: dict[str, dict[str, Any]] = {}
    for r in _read(folder, "sections.csv"):
        sections[r["id"]] = _drop_none(
            {
                "id": r["id"],
                "course_id": r["course_id"],
                "number": r["number"],
                "capacity": _cell(r["capacity"]),
                "instructor_ids": _lst(r["instructor_ids[]"]),
                "meetings": [],
            }
        )
    for r in _read(folder, "meetings.csv"):
        sec = sections.get(r["section_id"])
        if sec is None:
            raise TermDataError(
                f"meetings.csv: section {r['section_id']!r} not in sections.csv"
            )
        placement = None
        if any(_cell(r[k]) for k in ("placed_days", "placed_start", "placed_end")):
            placement = {
                "days": r["placed_days"],
                "start": r["placed_start"],
                "end": r["placed_end"],
                "room_ids": _lst(r["placed_room_ids[]"]),
            }
        sec["meetings"].append(
            _drop_none(
                {
                    "id": r["id"],
                    "component": r["component"],
                    "duration_min": r["duration_min"],
                    "allowed_day_patterns": _lst(r["allowed_day_patterns[]"]),
                    "room_type": _cell(r["room_type"]),
                    "rooms_needed": _cell(r["rooms_needed"]),
                    "placement": placement,
                }
            )
        )

    raw = {
        "schema_version": _cell(t.get("schema_version", "")) or "1.0",
        "provenance": _drop_none(
            {
                "synthetic": synthetic == "true",
                "source": t["source"],
                "retrieved_on": _cell(t["retrieved_on"]),
                "generator": _cell(t["generator"]),
                "seed": _cell(t["seed"]),
                "notes": _cell(t["notes"]),
            }
        ),
        "term": {
            "id": t["id"],
            "name": t["name"],
            "season": t["season"],
            "academic_year": t["academic_year"],
        },
        "slot_grid": [
            _drop_none(
                {
                    "id": r["id"],
                    "days": r["days"],
                    "start": r["start"],
                    "end": r["end"],
                    "kind": _cell(r["kind"]),
                }
            )
            for r in _read(folder, "slots.csv")
        ],
        "courses": [
            _drop_none(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "credits": _cell(r["credits"]),
                    "coupled_courses": _lst(r["coupled_courses[]"]),
                }
            )
            for r in _read(folder, "courses.csv")
        ],
        "sections": list(sections.values()),
        "instructors": list(instructors.values()),
        "rooms": [
            _drop_none(
                {
                    "id": r["id"],
                    "building": r["building"],
                    "name": r["name"],
                    "room_type": r["room_type"],
                    "capacity": _cell(r["capacity"]),
                }
            )
            for r in _read(folder, "rooms.csv")
        ],
        "room_pools": [
            _drop_none(
                {
                    "room_type": r["room_type"],
                    "count": r["count"],
                    "capacity": _cell(r["capacity"]),
                }
            )
            for r in _read(folder, "room_pools.csv")
        ],
        "cohorts": [
            _drop_none(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "label": r["label"],
                    "size": _cell(r["size"]),
                }
            )
            for r in _read(folder, "cohorts.csv")
        ],
        "no_clash_groups": [
            {
                "id": r["id"],
                "cohort_id": r["cohort_id"],
                "course_ids": _lst(r["course_ids[]"]),
                "source": r["source"],
            }
            for r in _read(folder, "no_clash_groups.csv")
        ],
        "external_meetings": [
            {
                "id": r["id"],
                "cohort_id": r["cohort_id"],
                "label": r["label"],
                "days": r["days"],
                "start": r["start"],
                "end": r["end"],
            }
            for r in _read(folder, "external_meetings.csv")
        ],
        "clash_exceptions": [
            {
                "id": r["id"],
                "course_a": r["course_a"],
                "course_b": r["course_b"],
                "reason": r["reason"],
                "approved_by": r["approved_by"],
                "approved_on": r["approved_on"],
            }
            for r in _read(folder, "clash_exceptions.csv")
        ],
    }
    return _validate(raw, folder.name)


def save_csv_dir(data: TermData, folder: str | Path) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    j = lambda xs: LIST_SEP.join(xs)
    s = lambda v: "" if v is None else (v.value if hasattr(v, "value") else str(v))
    p, t = data.provenance, data.term

    rows: dict[str, list[list[str]]] = {
        "term.csv": [
            [
                t.id,
                t.name,
                t.season.value,
                t.academic_year,
                data.schema_version,
                "true" if p.synthetic else "false",
                p.source,
                s(p.retrieved_on),
                s(p.generator),
                s(p.seed),
                s(p.notes),
            ]
        ],
        "slots.csv": [
            [x.id, x.days, x.start, x.end, x.kind.value] for x in data.slot_grid
        ],
        "courses.csv": [
            [c.id, c.title, s(c.credits), j(c.coupled_courses)] for c in data.courses
        ],
        "sections.csv": [
            [x.id, x.course_id, x.number, s(x.capacity), j(x.instructor_ids)]
            for x in data.sections
        ],
        "meetings.csv": [
            [
                m.id,
                x.id,
                m.component.value,
                str(m.duration_min),
                j(m.allowed_day_patterns),
                s(m.room_type),
                str(m.rooms_needed),
                s(m.placement.days if m.placement else None),
                s(m.placement.start if m.placement else None),
                s(m.placement.end if m.placement else None),
                j(m.placement.room_ids) if m.placement else "",
            ]
            for x in data.sections
            for m in x.meetings
        ],
        "instructors.csv": [[i.id, i.kind.value] for i in data.instructors],
        "availability.csv": [
            [i.id, a.days, a.start, a.end]
            for i in data.instructors
            for a in i.availability
        ],
        "rooms.csv": [
            [r.id, r.building, r.name, r.room_type.value, s(r.capacity)]
            for r in data.rooms
        ],
        "room_pools.csv": [
            [r.room_type.value, str(r.count), s(r.capacity)] for r in data.room_pools
        ],
        "cohorts.csv": [[c.id, c.kind.value, c.label, s(c.size)] for c in data.cohorts],
        "no_clash_groups.csv": [
            [g.id, g.cohort_id, j(g.course_ids), g.source] for g in data.no_clash_groups
        ],
        "external_meetings.csv": [
            [e.id, e.cohort_id, e.label, e.days, e.start, e.end]
            for e in data.external_meetings
        ],
        "clash_exceptions.csv": [
            [
                x.id,
                x.course_a,
                x.course_b,
                x.reason,
                x.approved_by,
                x.approved_on.isoformat(),
            ]
            for x in data.clash_exceptions
        ],
    }
    for name, body in rows.items():
        with (folder / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_FILES[name])
            w.writerows(body)


# ---------------------------------------------------------------- shared


def _validate(raw: Any, label: str) -> TermData:
    try:
        return TermData.model_validate(raw)
    except ValidationError as e:
        lines = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "(root)"
            lines.append(f"  - {loc}: {err['msg']}")
        raise TermDataError(f"{label}: invalid term data\n" + "\n".join(lines)) from e
