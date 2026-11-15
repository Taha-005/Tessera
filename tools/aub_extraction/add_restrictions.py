"""Add section restrictions (Classes / Fields of Study / ...) to the EECE schedule CSVs.

For every CRN in eece_<term>.csv, asks AUB's public class search for that section's
restrictions (the same request the "Restrictions" tab of the class-details popup makes)
and writes a copy of the CSV with extra columns.

Usage (run in the folder that holds the eece_*.csv files):
    pip install requests
    python add_restrictions.py --limit 5        # quick test on 5 sections of each term
    python add_restrictions.py                  # all terms

Output (originals are not touched):
    with_restrictions/eece_<term>.csv         + columns restrictions, classes_allowed, majors_allowed, departments_allowed
    with_restrictions/ALL_eece_2024-27.csv    all terms combined
    with_restrictions/restriction_codes.csv   code -> full name (e.g. ECMP -> Computer & Communications Eng.)
    with_restrictions/errors.csv              sections that failed (if any)

Data source and permitted use: see docs/provenance.md (P-02). Internal use only; do not commit outputs.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
from pathlib import Path

BASE = "https://sturegss.aub.edu.lb/StudentRegistrationSsb/ssb"

# term label in our CSVs -> Banner term code (observed: Fall 2025-26 = 202610,
# Spring 2026-27 = 202720, Summer 2024-25 = 202530; others follow the same pattern)
TERMS = {
    "fall_2024-25": "202510", "spring_2024-25": "202520", "summer_2024-25": "202530",
    "fall_2025-26": "202610", "spring_2025-26": "202620", "summer_2025-26": "202630",
    "fall_2026-27": "202710", "spring_2026-27": "202720",
}
EXTRA_COLS = ["restrictions", "classes_allowed", "majors_allowed", "departments_allowed"]
DELAY_S = 0.15  # be polite to the server


# ---------------------------------------------------------------- parsing

_HEAD = re.compile(r'<span class="status-bold">(.*?)</span>', re.S)
_ITEM = re.compile(r'<span class="detail-popup-indentation">(.*?)</span>', re.S)
_RULE = re.compile(r"^(Must be|Cannot be) enrolled in one of the following ([^:(]+)")
_CODE = re.compile(r"\(([^()]{1,20})\)")


def parse_restrictions(fragment: str) -> tuple[list[tuple[str, str, list[str]]], dict[tuple[str, str], str]]:
    """Return ([(sign, category, [codes])], {(category, code): name}).

    sign is '+' for "Must be enrolled", '-' for "Cannot be enrolled".
    Item lines are joined first because Banner splits names on commas
    (e.g. "Engineering 1" / "2 (E1)").
    """
    rules, names = [], {}
    heads = list(_HEAD.finditer(fragment))
    for i, h in enumerate(heads):
        m = _RULE.match(html.unescape(h.group(1)).strip())
        if not m:
            continue  # e.g. "Not all restrictions are applicable."
        sign = "+" if m.group(1) == "Must be" else "-"
        category = m.group(2).strip()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(fragment)
        items = [html.unescape(x).strip() for x in _ITEM.findall(fragment[h.end():end])]
        joined = ", ".join(items)
        codes, last = [], 0
        for c in _CODE.finditer(joined):
            name = joined[last:c.start()].strip(" ,")
            codes.append(c.group(1).strip())
            names[(category, c.group(1).strip())] = re.sub(r"\s+", " ", name)
            last = c.end()
        if not codes and joined:  # items without codes: keep the text
            codes = [re.sub(r"\s+", " ", x) for x in items]
        rules.append((sign, category, codes))
    return rules, names


def summarize(rules) -> dict[str, str]:
    compact = ";".join(f"{s}{cat}={','.join(codes)}" for s, cat, codes in rules) or "NONE"
    def pick(*keys: str) -> str:
        found = [c for s, cat, codes in rules if s == "+" and cat.startswith(keys) for c in codes]
        return ",".join(dict.fromkeys(found))  # de-duplicate, keep order

    # Banner labels majors either "Fields of Study" or "Majors"; both mean the student's major.
    return {"restrictions": compact, "classes_allowed": pick("Classes"),
            "majors_allowed": pick("Fields of Study", "Majors"), "departments_allowed": pick("Departments")}


# ---------------------------------------------------------------- network

def make_session(term_code: str):
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "SchedAgent-course-project (EECE 503P, AUB)"
    s.get(f"{BASE}/term/termSelection?mode=search", timeout=30)
    s.post(f"{BASE}/term/search?mode=search", data={"term": term_code}, timeout=30)
    return s


def fetch(session, term_code: str, crn: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            r = session.post(f"{BASE}/searchResults/getRestrictions",
                             data={"term": term_code, "courseReferenceNumber": crn}, timeout=30)
            if r.status_code == 200 and "restrictions" in r.text:
                return r.text
            err = f"HTTP {r.status_code}"
        except Exception as e:  # network error
            err = str(e)
        time.sleep(1.5 * attempt)
    raise RuntimeError(err)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=".", help="folder with eece_<term>.csv files")
    ap.add_argument("--limit", type=int, default=0, help="only N sections per term (testing)")
    args = ap.parse_args()

    src = Path(args.folder)
    out = src / "with_restrictions"
    out.mkdir(exist_ok=True)
    all_names: dict[tuple[str, str], str] = {}
    errors: list[list[str]] = []
    combined: list[dict] = []
    header = None

    for label, code in TERMS.items():
        path = src / f"eece_{label}.csv"
        if not path.exists():
            print(f"skip {path.name} (not found)")
            continue
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        header = list(rows[0].keys()) + EXTRA_COLS
        crns = list(dict.fromkeys(r["crn"] for r in rows))
        if args.limit:
            crns = crns[: args.limit]
        print(f"{label} ({code}): {len(crns)} sections ...", flush=True)

        session = make_session(code)
        found: dict[str, dict[str, str]] = {}
        for i, crn in enumerate(crns, 1):
            try:
                rules, names = parse_restrictions(fetch(session, code, crn))
                found[crn] = summarize(rules)
                all_names.update(names)
            except Exception as e:
                errors.append([label, crn, str(e)])
            if i % 25 == 0:
                print(f"  {i}/{len(crns)}", flush=True)
            time.sleep(DELAY_S)

        kept = [r for r in rows if r["crn"] in found] if args.limit else rows
        for r in kept:
            r.update(found.get(r["crn"], {"restrictions": "ERROR", "classes_allowed": "",
                                          "majors_allowed": "", "departments_allowed": ""}))
        with (out / path.name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(kept)
        combined += kept
        print(f"  done: {len(found)} ok, {sum(1 for e in errors if e[0] == label)} errors")

    if header:
        with (out / "ALL_eece_2024-27.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(combined)
    with (out / "restriction_codes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "code", "name"])
        w.writerows([cat, code, name] for (cat, code), name in sorted(all_names.items()))
    if errors:
        with (out / "errors.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["term", "crn", "error"])
            w.writerows(errors)
    print(f"\nFinished. Output in {out}/  ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
