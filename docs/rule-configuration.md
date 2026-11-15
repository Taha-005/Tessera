# Rule Configuration (T-025)

**Code:** `backend/tessera/rules/` (`config.py`, `default_rules.toml`, `overrides.example.toml`, stand-in `standin_h1.py`), loaded in `tessera/main.py`; tests in `backend/tests/test_rules.py`.

**Status:** v1. All values are **PROPOSED** until the department confirms which rules are hard (O-14).
**Requirements:** T1, T8 (centralized configuration), G3.

Lists the hard rules **H1–H11** (project doc 7.3) and soft objectives **S1–S5** (7.4) with hard/soft, weight and parameters. **Every rule and every parameter value carries a `source` and a `status`** (PROPOSED / CONFIRMED / DECIDED).

## Two files, merged at startup

| File | Where | Holds |
|---|---|---|
| `backend/tessera/rules/default_rules.toml` | **Repo** | Every rule, its structure, generic defaults and placeholders |
| `DATA_DIR/rule_overrides.toml` | **Data location (team drive)**, never committed (D-13) | Values derived from the department (interview, meetings) |

At startup, `create_app` loads the defaults plus `rule_overrides.toml` from the `DATA_DIR` setting, if that file exists, and keeps the result in `app.state.rules`. An invalid rule file stops startup, like a missing setting.

```python
from tessera.rules import load_rules
rules = load_rules(overrides_path=path)   # or load_rules() for the defaults only
rules.is_hard("H1"); rules.weight("S2"); rules.param("H9", "part_time_instructor_earliest")
rules.provenance()                        # every value with its source and status
```

An override can change `enabled`, `hard`, `weight`, `status` and `params`. Changing `enabled`/`hard`/`weight` **requires a `source`**. A parameter override replaces the value, source and status together. The format is shown in `backend/tessera/rules/overrides.example.toml` (synthetic values).

## Startup validation

`load_rules()` raises `RuleConfigError` listing every problem:

- **Completeness:** all of H1–H11 and S1–S5 present; no unknown rule IDs.
- **Hard and soft:** a hard rule has no weight; a soft one needs a weight ≥ 1; S1–S5 can never be hard.
- **Parameters:** only parameters declared for that rule (`PARAM_SPEC`), each type-checked (enum, `HH:MM`, integer ranges, 0–1 share, string list).
- **Tags:** every value has a non-empty `source` and a valid `status`.
- **Files:** file not found, invalid TOML.

## Rules and parameters

| Rule | Default | Parameters (default → source) |
|---|---|---|
| H1 no-clash groups | hard | `definition = pairwise` (D-06, DECIDED; cohort blocks O-09) |
| H2 coupling | hard | `exempt_components = [in_lecture_lab]` (7.3) |
| H3 instructor double-booking | hard | |
| H4 instructor availability | hard | |
| H5 rooms | hard | `room_model = named_rooms` (Option A, 2026-11-14; O-07) |
| H6 room type and capacity | hard | `default_slack = 0` (placeholder, O-14) |
| H7 parallel rooms | hard | (pattern is data, O-03) |
| H8 external meetings | hard | |
| H9 time windows | hard | `part_time_instructor_earliest` **from overrides** |
| H10 major restrictions | hard | |
| H11 completeness | hard (DECIDED) | |
| S1 instructor preferences | weight 1 | |
| S2 room slack | weight 1 | `target_slack = 0` |
| S3 co-enrollment | weight 1 | `min_co_enrollment_share = 0.2` (placeholder, O-11) |
| S4 stability | weight 1 | `moved_meeting_penalty = 1` |
| S5 conventions | weight 1 | `graduate_earliest`, `graduate_min_course_number` **from overrides** |

All weights are placeholders until O-14.

**Department values in the drive file** (`DATA_DIR/rule_overrides.toml`):
- Part-timers teach after 14:00 (interview).
- Graduate courses usually after 14:00 (interview; "usually", so soft).
- Graduate course numbers ≥ 600. This one is **inferred** from course numbers in the AUB data and is flagged to confirm with the department.

**Not config:** course-specific rules from the interview (E1 recitations after 17:00, EECE 330 oversized rooms, EECE 210 parallel labs) are **constraints** using the T-016 types, entered and approved per term.

## Toggle test (stand-in)

`backend/tessera/rules/standin_h1.py` is a **stand-in** H1 check, written only to prove that the config drives behavior. Tests show that the same clashing schedule gives:
- **H1 hard:** one violation.
- **H1 disabled:** nothing.
- **H1 soft (weight 7):** one penalty of weight 7.

Clash exceptions are respected. The real validator (T-034) replaces the stand-in and reuses these tests.

## Tests: 28

Including startup through `create_app`: rules load with no overrides file, the overrides file in `DATA_DIR` is applied, and an invalid one stops startup.
