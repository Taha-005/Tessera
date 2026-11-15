# Term Data Format (T-015)

**Code:** `backend/tessera/data/schema.py` (models), `backend/tessera/data/term_io.py` (JSON and CSV), tests in `backend/tests/test_term_schema.py`. Regenerate the example with `uv run python -m scripts.make_example_term` (from `backend/`).

**Status:** v1.0, built on project doc Section 7.1 (PROPOSED). Field lists may grow once department data arrives; additions bump `schema_version`.
**Requirements:** T7 (contracts and validation), T8 (no course-specific code), G7 (provenance).

One **term** of scheduling input = one `TermData` object. It can be stored in two equivalent formats:

| Format | Use | Notes |
|---|---|---|
| **JSON** (one file per term) | Canonical. What the importer stores and the system reads | Validated directly by the Pydantic models |
| **CSV folder** (one CSV per entity) | Staff-friendly input, editable in Excel | Converts losslessly to and from JSON (`load_csv_dir` / `save_csv_dir`) |

```python
from tessera.data.term_io import load_json, load_csv_dir, save_json, save_csv_dir
term = load_csv_dir("data/2026-fall/")   # raises TermDataError with a readable list of problems
save_json(term, "data/2026-fall.json")
```

---

## 1. Key modeling decisions

- **Section = one registration unit (CRN).** *(Decided 2026-11-14.)* A section lists the weekly **meetings** it needs. Each meeting has a component type, so one CRN can bundle a lecture and a lab, as AUB "Multiple Sessions" sections do.
- **Separately registered labs** (e.g. an "L" course) are ordinary sections of their own course. The link to the lecture course is `Course.coupled_courses`, which drives the coupling rule H2.
- **Meeting** is the unit the solver places. Before solving it has requirements (duration, allowed day patterns, room type, number of rooms). After solving, or for past schedules, it has a `placement`.
- **No course-specific fields.** Special cases are data: a lab held in the lecture slot is `component: in_lecture_lab`; "needs 2 lab rooms at once" is `rooms_needed: 2`.
- **Unknown values stay optional.** Room capacity (O-07), the slot grid (O-06), and a section's instructor or capacity can be missing. The schema accepts them; the importer reports missing instructor or capacity as blocking the solve (F17, T-019).
- **No personal data.** Instructors are referenced by pseudonymous IDs only (Section 8.2). Names never appear in term files.

## 2. Conventions

| Item | Format | Example |
|---|---|---|
| Days | Letters from `MTWRFSU`, any order in, canonical order stored. **R = Thursday**, **U = Sunday** | `MWF`, `TR` |
| Times | `HH:MM`, 24-hour | `08:00`, `17:45` |
| Dates | ISO `YYYY-MM-DD` | `2026-11-14` |
| Academic year | `YYYY-YY` | `2025-26` |
| IDs | Free text, unique within their entity | `EECE 230`, `11309`, `I-07` |
| Lists in CSV | `;`-separated in one cell | `MWF;TR` |
| Empty CSV cell | "Not set" | |

Unknown fields are **rejected**, so typos fail loudly instead of being silently ignored.

## 3. Entities

### provenance *(required)*
| Field | Type | Required | Notes |
|---|---|---|---|
| synthetic | bool | yes | Must be true for generated data (Section 8.3) |
| source | text | yes | e.g. "AUB Banner class search" |
| retrieved_on | date | | |
| generator | text | if synthetic | Script that produced the file |
| seed | int | | For reproducible generation |
| notes | text | | |

### term *(required)*
`id`, `name`, `season` (`fall`/`spring`/`summer`), `academic_year`.

### slot_grid
Standard slots of the term (O-06; may be empty until known).
`id`, `days`, `start`, `end`, `kind` (`lecture`/`lab`/`recitation`/`any`).

### courses *(at least one)*
| Field | Type | Notes |
|---|---|---|
| id | text | e.g. `EECE 230` |
| title | text | |
| credits | number | |
| coupled_courses | list of course ids | Meetings must not overlap for the same students (H2) |

### sections
| Field | Type | Notes |
|---|---|---|
| id | text | CRN or synthetic id |
| course_id | course id | |
| number | text | Section number within the course |
| capacity | int ≥ 0 | Enrollment cap. Missing → blocks solving (F17) |
| instructor_ids | list of instructor ids | Missing → blocks solving (F17) |
| meetings | list of meetings | |

### meetings *(inside a section; `meetings.csv` in CSV form)*
| Field | Type | Notes |
|---|---|---|
| id | text | Unique across the term |
| component | `lecture` / `lab` / `recitation` / `in_lecture_lab` | `in_lecture_lab` = held in the lecture's own slot; exempt from H2 |
| duration_min | int > 0 | Length of each occurrence |
| allowed_day_patterns | list of day strings | Empty = any pattern in the grid |
| room_type | `classroom` / `lab` / `e_classroom` / `auditorium` / `other` | |
| rooms_needed | int ≥ 1 | > 1 = parallel rooms (H7) |
| placement | days, start, end, room_ids | Optional. Set for past schedules and solver output |

### instructors
`id` (pseudonymous), `kind` (`full_time`/`part_time`/`unknown`), `availability`: list of `{days, start, end}` windows in which the instructor **can** teach (hard, H4). Empty = no restriction recorded. In CSV form, availability rows go in `availability.csv`.

### rooms / room_pools
Named rooms: `id`, `building`, `name`, `room_type`, `capacity` (optional; O-07, synthetic until obtained).
Pools, when only counts are known: `room_type`, `count`, `capacity`. One pool per room type.

### cohorts
`id`, `kind` (`year_major`/`concentration`/`outside_major`/`other`), `label`, `size`.

### no_clash_groups
`id`, `cohort_id`, `course_ids` (at least 2, no duplicates), `source`. Pairwise clash-free definition (D-06).

### external_meetings
A non-EECE class the cohort attends (H8, Section 7.5): `id`, `cohort_id`, `label`, `days`, `start`, `end`.

### clash_exceptions
An approved overlap (Section 7.2): `id`, `course_a`, `course_b` (different), `reason`, `approved_by`, `approved_on`.

## 4. Validation

**Per field:** types, enums, day letters, `HH:MM` times, start before end, positive durations and counts, unknown fields rejected.

**Across the file (referential integrity):** unique IDs per entity (meeting IDs across the whole term); every reference resolves (section → course and instructors, placement → rooms, group/external meeting → cohort, group/exception/coupling → courses); a course cannot be coupled with itself; one pool per room type.

**CSV-specific:** required files present (`term.csv`, `courses.csv`); exact column headers; exactly one row in `term.csv`; `synthetic` is `true`/`false`; meeting and availability rows point to existing sections and instructors.

All errors are collected and reported together, with the path of each problem (F11).

## 5. CSV folder layout

| File | Columns (`[]` = `;`-separated list) | Required |
|---|---|---|
| term.csv | id, name, season, academic_year, schema_version, synthetic, source, retrieved_on, generator, seed, notes | yes (1 row) |
| courses.csv | id, title, credits, coupled_courses[] | yes |
| slots.csv | id, days, start, end, kind | |
| sections.csv | id, course_id, number, capacity, instructor_ids[] | |
| meetings.csv | id, section_id, component, duration_min, allowed_day_patterns[], room_type, rooms_needed, placed_days, placed_start, placed_end, placed_room_ids[] | |
| instructors.csv | id, kind | |
| availability.csv | instructor_id, days, start, end | |
| rooms.csv | id, building, name, room_type, capacity | |
| room_pools.csv | room_type, count, capacity | |
| cohorts.csv | id, kind, label, size | |
| no_clash_groups.csv | id, cohort_id, course_ids[], source | |
| external_meetings.csv | id, cohort_id, label, days, start, end | |
| clash_exceptions.csv | id, course_a, course_b, reason, approved_by, approved_on | |

Missing optional files mean "none".

## 6. Example

`data/synthetic/example_term/term.json` and `data/synthetic/example_term/csv/` hold the same small **synthetic** term (invented courses `SYN …`). It covers a bundled lecture+lab section, a lecture with an in-lecture lab needing 2 lab rooms, a coupled separate lab course, a section missing instructor and capacity, availability windows, named rooms and a room pool, a no-clash group, an external meeting and a clash exception.

**Fit check against real data:** the real Fall 2025-26 AUB extraction (187 sections) maps into this schema and validates. The proper mapping is the department-format adapter (T-020).

## 7. Open items this schema waits on

| Open item | Effect |
|---|---|
| O-06 slot grid | `slot_grid` may be empty; filled when known or derived from past schedules |
| O-07 rooms | `capacity` optional; named rooms or pools both supported |
| O-03 in-lecture lab pattern | `in_lecture_lab` + `rooms_needed` express it; which weeks it runs is not modeled yet |
| O-09 cohort blocks | Groups are pairwise for now (D-06) |
| O-21 EECE 230 structure | Covered by bundled meetings or separate sections, whichever the data shows |
