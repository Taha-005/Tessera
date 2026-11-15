# Room capacities: build room rules now, synthetic capacities until known

**Date:** 2026-11-14 · **Decided by:** Mohamad El Ajouz · **Affects:** TESS-44 (T-038), TESS-45 (T-039), TESS-46 (T-040), TESS-59 (T-051), TESS-60 (T-052), TESS-61 (T-053)

## Question

Room capacity and room type are not in the public schedule data (room names only), and O-07 is open. Do the room rules wait, or get built now?

## Options considered

| Option | Verdict |
|---|---|
| **A. Build the room rules (H5, H6, H7, S2) now, with capacity and type as data inputs; test with synthetic capacities labeled synthetic** | **Chosen.** Keeps the interview's room rules (parallel labs, oversized rooms, e-classroom) and room-based infeasibility cases in scope; real values are entered as data later, with no code change. |
| B. Skip rooms; schedule times only | Rejected. Drops interview rules the evaluation and demo rely on. |

## Decision

Option A. The affected Jira tasks carry a comment with this decision; they are no longer blocked by O-07. Results on room rules state that capacities are synthetic until O-07 is answered by the department or facilities.

## Proposed entry for the project document

- **Section 25 (Decision Log), D-xx:** Room rules are built with capacity and type as inputs; synthetic capacities are used until O-07 is resolved, and the limitation is stated in results.
