# Provenance Register (T-012)

**Requirements:** G7 (data: public, authorized or synthetic; clear provenance; respect Terms of Service), D8 (evidence for every claim)
**Rule (Section 8.2, D-13):** this file holds **metadata only**. Raw department or AUB data is never committed to this repository. It lives in the team-only drive.

Each source has: who provided it, when, what it contains, what was changed, and what it may be used for.

---

## P-01 · Department interview

| Field | Value |
|---|---|
| Source | Interview with the EECE department staff who build the course schedule |
| Provided by | Department scheduling staff (lead scheduler and team; see Section 5.1) |
| Date | **OPEN (O-05)** |
| Collected by | Project team |
| Content | Scheduling process, rules and course-level examples (project doc Sections 4–5) |
| Transformations | Summarized into the project document; rules restated as general rule types (Section 11) |
| Consent | Staff consented to their information being used for this project (CONFIRMED: team) |
| Permitted use | This course project only (D-13). Not for publication outside the project |
| Storage | Interview notes in the team drive; summary in the project document |
| Personal data | None stored beyond staff roles |

## P-02 · AUB public class schedule (Banner class search)

| Field | Value |
|---|---|
| Source | AUB Banner class search: `https://sturegss.aub.edu.lb/StudentRegistrationSsb/ssb/term/termSelection?mode=search` (public, no login; past terms view-only) |
| Retrieved | 2026-11-14, by Mohamad El Ajouz (with AI-assisted browser extraction, see G9) |
| Scope | Subject **EECE only**; all sections of the term, including thesis, project and exam entries |
| Terms of use | AUB site copyright (`https://www.aub.edu.lb/Pages/CopyRight.aspx`): non-commercial copying allowed with AUB attribution; republication needs written permission. **Team position (2026-11-14):** permissions treated as obtained; nothing is published publicly (see T-014 / O-22 on TESS-20) |
| Permitted use | Internal development and evaluation (real instances, baselines, held-out testing, scale). Not published |
| Storage | Team drive only. Never committed (D-13) |
| Personal data | **Instructor names** (public on the site). Pseudonymized to IDs at import before any LLM call (8.2, T-021). Instructor emails shown on the site were **not collected**. No student data |

### Extracted files

| File | Term | Sections | Rows (meetings) | Distinct instructor lists |
|---|---|---|---|---|
| `eece_fall_2024-25.csv` | Fall 2024-25 | 215 | 262 | 102 |
| `eece_spring_2024-25.csv` | Spring 2024-25 | 222 | 266 | 104 |
| `eece_summer_2024-25.csv` | Summer 2024-25 | 39 | 40 | 13 |
| `eece_fall_2025-26.csv` | Fall 2025-26 | 187 | 244 | 83 |
| `eece_spring_2025-26.csv` | Spring 2025-26 | 181 | 232 | 80 |
| `eece_summer_2025-26.csv` | Summer 2025-26 | 40 | 41 | 11 |
| `eece_fall_2026-27.csv` | Fall 2026-27 | 214 | 293 | 93 |
| `eece_spring_2026-27.csv` | Spring 2026-27 | 202 | 281 | 75 |
| `ALL_eece_2024-27.csv` | All of the above | 1,300 | 1,659 | — |

**Completeness check:** for every term, the number of extracted sections equals the "N Classes" total the site reports for that search.

### Transformations applied

1. One row per **weekly meeting**; a section with several meetings has several rows (section fields repeated).
2. Days converted to letters: M, T, W, R (Thursday), F, S (Saturday).
3. Times converted to 24-hour `HHMM`.
4. HTML entities in titles decoded (e.g. `&amp;` → `&`); stray tab characters removed.
5. Building names kept as shown on the site; meetings with no building or room shown as empty.
6. **Dropped:** instructor emails; meeting type (always "Class" in the extracted data); meeting start and end dates.
7. Sections with no scheduled meeting (thesis, PhD, exams, most projects) kept as one row with empty day, time and room.
8. **Restrictions added (2026-11-14, step 2).** For every CRN, the section's registration restrictions were retrieved from the same public site (the "Restrictions" tab of the class-details popup) by `tools/aub_extraction/add_restrictions.py`, run by Mohamad El Ajouz. Result: 1,300 / 1,300 sections, 0 errors; 25 sections have no restrictions. Written to `with_restrictions/` (same rows, 4 extra columns). Code names are in `with_restrictions/restriction_codes.csv` (52 codes).

### Columns

`term, crn, course, section, credits, title, schedule_type, seat_cap, seats_left, instructors, primary_instructor, days, start, end, building, room`

`with_restrictions/` adds: `restrictions` (every rule, e.g. `+Classes=E1,E2;+Fields of Study=ECMP,EECE;-Programs=NWEN-EA-UG`; `+` = must be enrolled, `-` = cannot be enrolled; `NONE` = no restriction), `classes_allowed` (year levels), `majors_allowed` (union of the site's "Fields of Study" and "Majors" labels), `departments_allowed`.

### Known caveats

- `seats_left` is a **snapshot** at retrieval time. For Fall 2026-27 and Spring 2026-27 the schedule may still change.
- `seat_cap` is the section's enrollment cap, **not** the room capacity. Room capacity and type are not public (O-07; decision 2026-11-14, Option A: synthetic capacities until obtained).
- EECE 501/502 Final Year Project appear as many sections sharing one slot and room in some terms.
- Spring 2024-25, EECE 321L section 3: a meeting time with no room.
- Building "Annex Eng'g" appears only in Spring 2024-25.
- Year-level codes changed between systems: E1–E4 (Engineering 1–11) in older terms, FR/SO/JR/SR in Fall and Spring 2026-27. Mapping them onto common cohorts is an adapter decision (T-020).
- Restrictions say who **may register**, which is not exactly who **is expected** to take the course; e.g. a section open to E1–E4 is not evidence that E4 students take it.

### Reproduction

`tools/aub_extraction/add_restrictions.py` adds the restriction columns (run in the folder holding the CSVs; `--limit N` for a quick test). `tools/aub_extraction/compact_to_csv.py` converts the browser extraction (compact `S|…` / `M|…` lines) into the CSVs above. The extraction reads the search-results table of the public class search page, 50 results per page, for subject EECE and one term at a time.

## P-03 · AUB undergraduate and graduate catalogue

| Field | Value |
|---|---|
| Source | `https://www.aub.edu.lb/Registrar/catalogue2025-26` |
| Status | Identified (T-014); **not yet extracted** |
| Intended content | Majors, required courses per year, concentrations (O-01, O-02) |
| Terms of use | Same AUB site copyright as P-02 |

---

## Changelog

- **2026-11-14:** Created. P-01 (date open), P-02 (8 terms extracted), P-03 (identified).
- **2026-11-14:** P-02 step 2: section restrictions added for all 1,300 sections.
