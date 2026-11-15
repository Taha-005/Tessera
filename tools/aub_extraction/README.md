# AUB public schedule extraction

Tools that built the AUB class-search dataset recorded as **P-02** in [`docs/provenance.md`](../../docs/provenance.md).
They run on a developer's machine, outside the app. **Their outputs contain instructor names: they go to the team drive, never into this repository** (D-13).

| File | What it does |
|---|---|
| `compact_to_csv.py` | Converts the browser extraction of the public class search (compact `S\|…` / `M\|…` lines, one term at a time) into `eece_<term>.csv`: one row per weekly meeting |
| `add_restrictions.py` | For every CRN in the `eece_<term>.csv` files, fetches the section's registration restrictions (the class-details "Restrictions" tab) and writes copies with `restrictions`, `classes_allowed`, `majors_allowed`, `departments_allowed` columns, plus `restriction_codes.csv` |
| `test_parse.py` | Tests the restrictions parser on a real response (`python -m pytest test_parse.py`) |

```
pip install requests
python add_restrictions.py --limit 5   # quick check: 5 sections per term
python add_restrictions.py             # all terms, about 5-10 minutes
```

Terms of use: AUB site copyright allows non-commercial copying with attribution; republication needs written permission. Team position (2026-11-14): internal use only, nothing published (see TESS-20).
