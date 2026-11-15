"""Convert the compact S/M extraction format into the same CSV layout as eece_fall_2025-26.csv."""
import csv
import html
import sys

BUILDINGS = {
    "BEB": "Bechtel Engineering Building",
    "RIOEC": "Ray Irani Oxy Eng'g Complex",
    "SRB": "CCC Science Research Blg.(SRB)",
    "DAH": "Dar AlHandasah Shair&P Arch B.",
    "MAMC": "Munib &Angela Masri Complex",
    "RGB": "Raymond Ghosn Building",
    "VDH": "Van Dyck Hall",
    "": "",
}
HEADER = ["term", "crn", "course", "section", "credits", "title", "schedule_type",
          "seat_cap", "seats_left", "instructors", "primary_instructor",
          "days", "start", "end", "building", "room"]


def clean(x):
    return html.unescape(x).replace("\t", "").strip()


def convert(src, dst, term_label):
    rows, section, has_meeting = [], None, False
    sections = 0

    def flush():
        if section is not None and not has_meeting:
            rows.append([term_label] + section + ["", "", "", "", ""])

    for line in open(src, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("|")
        if parts[0] == "S":
            flush()
            crn, num, seq, cr, title, st, cap, left, ins, prim = parts[1:11]
            section = [crn, "EECE " + num, seq, cr, clean(title), st, cap, left, clean(ins), clean(prim)]
            has_meeting = False
            sections += 1
        elif parts[0] == "M":
            days, start, end, bcode, room = parts[1:6]
            rows.append([term_label] + section + [days, start, end, BUILDINGS.get(bcode, bcode), room])
            has_meeting = True
        else:
            raise ValueError(f"bad line: {line!r}")
    flush()

    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"{dst}: {sections} sections, {len(rows)} rows")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
