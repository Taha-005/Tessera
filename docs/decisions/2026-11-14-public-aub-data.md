# Data source: AUB's public class search, internal use only

**Date:** 2026-11-14 · **Decided by:** Mohamad El Ajouz (team) · **Tasks:** TESS-20 (T-014, O-22), TESS-18 (T-012)

## Question

Can past EECE schedules come from AUB's public listings instead of the department (O-22), and on what terms?

## Evidence

- AUB Banner class search is public, needs no login, and keeps past terms (view-only). It gives per section: course, CRN, instructors, every meeting's days, times, building and room, seat cap, and (in the class details) registration restrictions by year level, major and department.
- AUB's site copyright allows non-commercial copying with attribution; republication needs written permission.
- Extracted 2026-11-14: 8 terms (Fall 2024-25 to Spring 2026-27), 1,300 EECE sections, each term's count equal to the site's total; restrictions for all 1,300 sections, 0 errors.

## Decision

Use the public listings for internal development and evaluation. Permissions are treated as obtained; nothing is published. Raw extracts stay in the team drive (D-13), instructor names are pseudonymized at import (Section 8.2). Room capacity and type are not public (see the room-capacity decision). The catalogue (majors, concentrations) is the source for O-01 and O-02.

## Proposed entry for the project document

- **Open items:** O-22 resolved as above.
- **Section 8.1 (data sources):** add "AUB public class search (P-02)" as the source of past schedules and section restrictions.
