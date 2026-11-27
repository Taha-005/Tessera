"""Term data: what the department wants to offer. No times are given; the solver picks them."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DAY_LETTERS = "MTWRF"


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class TimeOption:
    days: str
    start: int
    end: int

    def overlaps(self, other: TimeOption) -> bool:
        return bool(set(self.days) & set(other.days)) and self.start < other.end and other.start < self.end

    def label(self) -> str:
        return f"{self.days} {to_hhmm(self.start)}-{to_hhmm(self.end)}"


@dataclass
class Section:
    id: str
    course: str
    component: str
    instructor: str | None
    options: list[TimeOption] = field(default_factory=list)  # every time it could physically take


@dataclass
class Term:
    name: str
    instructors: list[str]
    courses: dict[str, dict]
    sections: list[Section]
    raw: dict

    def section(self, sid: str) -> Section:
        return next(s for s in self.sections if s.id == sid)

    def sections_of(self, course: str) -> list[Section]:
        return [s for s in self.sections if s.course == course]


def load_term(source: str | Path | dict) -> Term:
    raw = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    kinds = raw["slot_kinds"]
    sections: list[Section] = []
    for c in raw["courses"]:
        opts: list[TimeOption] = []
        for k in c["slot_kinds"]:
            sk = kinds[k]
            for pattern in sk["day_patterns"]:
                for s in sk["starts"]:
                    opts.append(TimeOption(pattern, to_min(s), to_min(s) + sk["minutes"]))
        for s in c["sections"]:
            sections.append(Section(s["id"], c["id"], c["component"], s.get("instructor"), list(opts)))
    return Term(raw.get("term", ""), raw.get("instructors", []),
                {c["id"]: c for c in raw["courses"]}, sections, raw)
