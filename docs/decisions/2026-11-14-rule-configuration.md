# Rule configuration: defaults in the repo, department values in DATA_DIR

**Date:** 2026-11-14 · **Decided by:** Mohamad El Ajouz · **Task:** TESS-31 (T-025)

## Questions

1. T-025 says department-derived values are read from the data location unless the department agreed to publish them. Where does each value live?
2. T-025's "done when" asks for a test that toggling a rule changes validator behavior, but the validator (T-034) does not exist yet.

## Options considered

| Question | Option | Verdict |
|---|---|---|
| 1 | **Split**: `backend/tessera/rules/default_rules.toml` (all rules, structure, generic defaults) in the repo; `DATA_DIR/rule_overrides.toml` (department values) in the team drive, merged at startup | **Chosen.** Follows D-13 and the ticket; the repo stays free of department information. |
| 1 | Everything in one repo file | Rejected. The repository is public. |
| 2 | **Stand-in H1 check** used only to prove the configuration drives behavior | **Chosen.** T-034 replaces it and reuses the toggle tests. |
| 2 | Leave the toggle test to T-034 | Rejected. T-025 could not meet its "done when". |

## Decision

TOML files (read with the standard library, no new dependency), validated with Pydantic. `create_app` loads them right after the settings, so an invalid rule file stops startup with every problem listed, as a missing setting does. The overrides file is looked up in the existing `DATA_DIR` setting, so no new setting is added.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** Rule hardness, weights and parameters live in `default_rules.toml` (repo, generic) and `DATA_DIR/rule_overrides.toml` (team drive, department-derived), merged and validated at startup. Every value carries a source and a status.
