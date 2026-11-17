# Constraint Vocabulary (T-016)

**Code:** `backend/tessera/data/constraints.py`, tests in `backend/tests/test_constraints.py`.

**Status:** v1, built on project doc Section 11 (PROPOSED). **Builds on:** T-015 (`tessera.data.schema`).
**Requirements:** T2 (validated tool interfaces), T7 (contracts), T4 (validation).

Every constraint is one of a **closed set of types**. It is a Pydantic discriminated union on `type`: one JSON object, and the `type` field decides which `params` are valid. Anything that does not fit goes through the **unsupported path** and is never approximated.

```python
from tessera.data.constraints import parse_constraint, dump_constraint, validate_references
c = parse_constraint(json_text)                      # raises ValidationError on bad shape
problems = validate_references(c, term, known_majors) # [] = every ID resolves
```

## 1. Common fields (Section 11.2)

| Field | Rule |
|---|---|
| `id`, `type`, `params` | `type` picks the params model; unknown types are rejected |
| `term_id` | Must match the term the constraint is checked against |
| `hard`, `weight` | Hard (default) has **no** weight; soft **needs** a weight ≥ 1 |
| `source`, `source_kind` | `note` / `learned` / `manual` / `imported` |
| `evidence` | **Required** when `source_kind = learned` (e.g. co-enrollment counts) |
| `status` | `proposed` (default) / `active` / `rejected` / `retired` |
| `author`, `created_at` | Required |
| `approved_by`, `approved_at` | **Required for `active`**; approval cannot be dated before creation |
| `version` | ≥ 1 |

Unknown fields are rejected at every level.

## 2. The 11 types (Section 11.1)

| Type | Params | Rule |
|---|---|---|
| `no_clash_group` | `cohort_id`, `course_ids` (≥ 2, unique) | H1 |
| `clash_exception` | `scope` (`course`/`section`), `a`, `b` (different), `reason` | 7.2 |
| `instructor_days` | `instructor_id`, `allowed_patterns` (e.g. `["TR"]`) | H4 |
| `instructor_time_window` | `instructor_id`, `earliest` and/or `latest`, optional `days` | H4 |
| `component_time_window` | `course_id`, `component`, `earliest` and/or `latest` | H9 |
| `room_requirement` | **either** `section_id` **or** `course_id` (+ optional `component`); `room_type`; optional `min_capacity`, `slack` | H6 |
| `parallel_rooms` | `course_id`, `component`, `rooms` (≥ 2), `room_type` | H7 |
| `major_restriction` | `section_ids`, `allowed_majors` (codes), optional `day_pattern` | H10 |
| `external_block` | `cohort_id`, `external_meeting_id` | H8 |
| `preference` | `target_type` (one of the 9 above), `target` (that type's params). **Always soft** | S1–S5 |
| `stability` | optional `base_version_id`. **Always soft** | S4 |

**Decisions (2026-11-14):**
- `preference` is a **wrapper**. It holds one other constraint, which keeps the 11 types of Section 11.1. It cannot wrap `preference`, `stability` or `unsupported`.
- **Majors are codes** (2–6 capital letters, e.g. `ECMP`, `EECE`, `EMCH`, `INDE`). They are checked against the codes seen in the AUB section restrictions (`restriction_codes.csv` in the team drive; Fields of Study / Majors, provenance P-02). Full names such as "Mechanical Engineering" are rejected.

Days use the T-015 convention (`MTWRFSU`, R = Thursday) and are normalized (`WM` → `MW`). Times are `HH:MM`, 24-hour.

## 3. The unsupported path

`type: "unsupported"` with `params: {original_text, reason}`. It is kept so the user sees what could not be expressed (F2), and offered the structured editor. It can only be `proposed` or `rejected`, **never `active`**, so it can never reach the solver.

## 4. Entity IDs only (no free-text names)

Params hold IDs. `validate_references(c, term, known_majors)` checks every ID against the term data (courses, sections, instructors, cohorts, external meetings, and the wrapped target of a preference). Anything that doesn't resolve is reported as `unknown <kind> '<value>' (constraints must reference <kind> IDs, not names)`. This is how a name like "Dr. Kabalan" or "Electric Circuits" gets rejected, which is the input to the ambiguity checks (F3, T-066).

## 5. Tests (72)

- A round trip for each of the 11 types (dict and JSON), plus a list round trip.
- Every example's references resolve against the synthetic term.
- **Unknown type** is rejected, including a missing type and a preference wrapping an invalid target.
- **Free-text names** are rejected for instructors, cohorts, courses, external meetings, inside a preference, and as major names. Unknown major codes and a wrong term are rejected too.
- **Missing parameters** are rejected for each type and for each required common field; so are a window with no bound and an unknown extra parameter.
- **Common-field rules:** hard with weight, soft without weight, always-soft types, learned without evidence, active without approval, approval before creation.
- **Unsupported path:** round trip, can be rejected, can never be active.
