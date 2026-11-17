# Constraint vocabulary: preference as a wrapper, majors as codes

**Date:** 2026-11-14 · **Decided by:** Mohamad El Ajouz · **Task:** TESS-22 (T-016)

## Questions

1. Section 11.1 lists `preference` as its own type ("any of the above as soft, with a weight"), while Section 11.2 gives every constraint a hard/soft flag and a weight. Is `preference` a separate type?
2. `major_restriction` names majors, but the term schema (T-015) has no major entity. How are majors referenced?

## Evidence

The AUB section restrictions (extracted 2026-11-14 for all 1,300 sections, provenance P-02) name majors by codes, e.g. `ECMP`, `EECE`, `EMCH`, `INDE`, under the labels "Fields of Study" and "Majors". 990 of the 1,051 scheduled sections carry a major restriction.

## Options considered

| Question | Option | Verdict |
|---|---|---|
| 1 | **Wrapper type** holding one other constraint (target type + params), always soft | **Chosen.** Keeps the 11 types of 11.1; a preference states its target explicitly. |
| 1 | Only the soft flag; drop `preference` (10 types) | Rejected. Simpler, but departs from the document's list. |
| 2 | **Major codes** (2–6 capital letters), checked against the codes seen in the restrictions | **Chosen.** Real, stable identifiers straight from the registrar's data. |
| 2 | Cohort IDs | Rejected. Restrictions are stated per major code, not per cohort. |

## Decision

`backend/tessera/data/constraints.py`, documented in `docs/constraint-vocabulary.md`. Unsupported requests use type `unsupported`, which can be proposed or rejected but never become active.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** `preference` is a wrapper type around one other constraint and is always soft. `major_restriction` references major codes as used by the AUB registrar (e.g. ECMP, EECE, EMCH, INDE).
- **Section 11.1:** note both points in the table.
