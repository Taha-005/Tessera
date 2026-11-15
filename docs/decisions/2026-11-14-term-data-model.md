# Term data: section = CRN, JSON canonical plus CSV input

**Date:** 2026-11-14 · **Decided by:** Mohamad El Ajouz · **Task:** TESS-21 (T-015)

## Question

How should a term's input data be modeled and stored? Section 7.1 of the project document proposes "Component = lecture/lab/recitation; Section = an instance of a component". The real AUB class search data (provenance P-02) does not fit that exactly.

## Evidence

In the AUB data for Fall 2025-26 (187 EECE sections), one registration unit (CRN) often bundles several meetings: e.g. an EECE 230 section is an MWF lecture plus a 2-hour lab in another room ("Multiple Sessions"). Other courses register labs as a separate course (e.g. a course with an "L" suffix).

## Options considered

| Option | Verdict |
|---|---|
| **Section = CRN, with a list of meetings tagged by component** | **Chosen.** Matches how AUB registers sections; separate lab courses link to their lecture course through `Course.coupled_courses` (H2). The real Fall 2025-26 term maps in and validates. |
| One section per component (strict 7.1) | Rejected. Bundled CRNs would have to be split and re-linked, losing the registration unit staff work with. |

| Format | Verdict |
|---|---|
| **Both: one JSON per term (canonical) and a CSV folder (staff input)** | **Chosen.** JSON validates directly with Pydantic; CSV is editable in Excel; they convert losslessly. |
| JSON only | Simpler, but staff would not edit it. |
| CSV only | No natural place for nested meetings and provenance. |

## Decision

`backend/tessera/data/schema.py` and `term_io.py`, documented in `docs/term-data-format.md`. Unknown values (room capacity O-07, slot grid O-06, a section's instructor or capacity) stay optional; the importer reports missing instructor or capacity as blocking (F17).

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** A section is a registration unit (CRN) listing its weekly meetings, each with a component type; separately registered labs link to their lecture course. Term data is stored as one JSON file per term, with an equivalent CSV folder for staff input.
- **Section 7.1:** update "Section" to the CRN definition above.
