"""Canonical term-data schema (T-015).

One ``TermData`` object holds everything the system needs about one term:
the slot grid, courses, sections and their meetings, instructors, rooms,
cohorts, no-clash groups, external fixed meetings and clash exceptions.

Design rules (project doc v1, Sections 7 and 8):
- Generic, data-driven types only. No field refers to a specific course.
- A **section** is one registration unit (a CRN). It lists the weekly
  **meetings** it needs; each meeting carries its component type
  (lecture / lab / recitation / in-lecture lab). Labs registered as their
  own course (e.g. a separate "L" course) are ordinary sections of that
  course, coupled to the lecture course through ``Course.coupled_courses``.
- Values the department has not confirmed (room capacities, slot grid,
  hardness of rules) stay optional or configurable, never hard-coded.
- Every file carries provenance and a ``synthetic`` flag (Section 8.3).
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DAY_ORDER = "MTWRFSU"  # Mon Tue Wed Thu(R) Fri Sat Sun(U)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


# ---------------------------------------------------------------- helpers


def parse_days(value: str) -> str:
    """Validate a day string such as 'MWF' or 'TR' and return it in canonical order."""
    if not isinstance(value, str) or not value:
        raise ValueError("days must be a non-empty string such as 'MWF' or 'TR'")
    value = value.strip().upper()
    bad = [c for c in value if c not in DAY_ORDER]
    if bad:
        raise ValueError(
            f"unknown day letter(s) {bad}; use {DAY_ORDER} (R = Thursday, U = Sunday)"
        )
    if len(set(value)) != len(value):
        raise ValueError(f"repeated day letter in {value!r}")
    return "".join(sorted(value, key=DAY_ORDER.index))


def to_minutes(hhmm: str) -> int:
    """'08:30' -> 510."""
    m = _TIME_RE.match(hhmm)
    if not m:
        raise ValueError(f"time {hhmm!r} must be HH:MM in 24-hour format")
    return int(m.group(1)) * 60 + int(m.group(2))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _TimeWindow(_Model):
    days: str
    start: str = Field(description="HH:MM, 24-hour")
    end: str = Field(description="HH:MM, 24-hour")

    @field_validator("days")
    @classmethod
    def _days(cls, v: str) -> str:
        return parse_days(v)

    @field_validator("start", "end")
    @classmethod
    def _time(cls, v: str) -> str:
        to_minutes(v)
        return v

    @model_validator(mode="after")
    def _order(self):
        if to_minutes(self.start) >= to_minutes(self.end):
            raise ValueError(f"start {self.start} must be before end {self.end}")
        return self

    @property
    def start_min(self) -> int:
        return to_minutes(self.start)

    @property
    def end_min(self) -> int:
        return to_minutes(self.end)


# ---------------------------------------------------------------- enums


class Season(str, Enum):
    fall = "fall"
    spring = "spring"
    summer = "summer"


class ComponentType(str, Enum):
    lecture = "lecture"
    lab = "lab"
    recitation = "recitation"
    in_lecture_lab = (
        "in_lecture_lab"  # lab held in the lecture's own slot (H2 exemption)
    )


class SlotKind(str, Enum):
    lecture = "lecture"
    lab = "lab"
    recitation = "recitation"
    any = "any"


class RoomType(str, Enum):
    classroom = "classroom"
    lab = "lab"
    e_classroom = "e_classroom"
    auditorium = "auditorium"
    other = "other"


class InstructorKind(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    unknown = "unknown"


class CohortKind(str, Enum):
    year_major = "year_major"  # e.g. E2 CCE
    concentration = "concentration"  # E3/E4 concentration
    outside_major = "outside_major"  # e.g. MECHE students taking EECE courses
    other = "other"


# ---------------------------------------------------------------- entities


class Provenance(_Model):
    """Where this term file came from (Section 8.2 provenance record)."""

    synthetic: bool = Field(
        description="True for generated data; must be labeled (Section 8.3)"
    )
    source: str = Field(
        min_length=1,
        description="e.g. 'AUB Banner class search' or 'synthetic generator v1'",
    )
    retrieved_on: date | None = None
    generator: str | None = None
    seed: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _synthetic_needs_generator(self):
        if self.synthetic and not self.generator:
            raise ValueError("synthetic data must name its generator (Section 8.3)")
        return self


class Term(_Model):
    id: str = Field(min_length=1, description="e.g. '2025-26-fall'")
    name: str = Field(min_length=1, description="e.g. 'Fall 2025-26'")
    season: Season
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$", description="e.g. '2025-26'")


class TimeSlot(_TimeWindow):
    """One entry of the term's slot grid (O-06: the real grid is configurable)."""

    id: str = Field(min_length=1)
    kind: SlotKind = SlotKind.any


class Course(_Model):
    id: str = Field(min_length=1, description="e.g. 'EECE 230'")
    title: str = ""
    credits: float | None = Field(default=None, ge=0)
    coupled_courses: list[str] = Field(
        default_factory=list,
        description="Courses whose meetings must not overlap this one's for the same students (H2), "
        "e.g. a separately registered lab course and its lecture course",
    )


class Placement(_Model):
    """Where a meeting actually is (past schedules, baselines, repair mode). Optional."""

    days: str
    start: str
    end: str
    room_ids: list[str] = Field(default_factory=list)

    @field_validator("days")
    @classmethod
    def _days(cls, v: str) -> str:
        return parse_days(v)

    @field_validator("start", "end")
    @classmethod
    def _time(cls, v: str) -> str:
        to_minutes(v)
        return v

    @model_validator(mode="after")
    def _order(self):
        if to_minutes(self.start) >= to_minutes(self.end):
            raise ValueError(f"start {self.start} must be before end {self.end}")
        return self


class Meeting(_Model):
    """A weekly meeting a section needs. This is what the solver places (Section 7.1)."""

    id: str = Field(min_length=1)
    component: ComponentType
    duration_min: int = Field(
        gt=0, le=24 * 60, description="Length of each occurrence in minutes"
    )
    allowed_day_patterns: list[str] = Field(
        default_factory=list,
        description="e.g. ['MWF', 'TR']; empty = any pattern in the grid",
    )
    room_type: RoomType | None = None
    rooms_needed: int = Field(default=1, ge=1, description=">1 for parallel rooms (H7)")
    placement: Placement | None = None

    @field_validator("allowed_day_patterns")
    @classmethod
    def _patterns(cls, v: list[str]) -> list[str]:
        out = [parse_days(p) for p in v]
        if len(set(out)) != len(out):
            raise ValueError("duplicate day pattern")
        return out


class Section(_Model):
    """One registration unit (CRN)."""

    id: str = Field(min_length=1, description="CRN or a synthetic id")
    course_id: str
    number: str = Field(min_length=1, description="Section number within the course")
    capacity: int | None = Field(
        default=None, ge=0, description="Enrollment cap; missing blocks solving (F17)"
    )
    instructor_ids: list[str] = Field(
        default_factory=list, description="Missing blocks solving (F17)"
    )
    meetings: list[Meeting] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_meeting_ids(self):
        ids = [m.id for m in self.meetings]
        if len(set(ids)) != len(ids):
            raise ValueError(f"section {self.id}: duplicate meeting id")
        return self


class AvailabilityWindow(_TimeWindow):
    """A window in which the instructor CAN teach (hard, H4)."""


class Instructor(_Model):
    id: str = Field(
        min_length=1, description="Pseudonymous id; never a name (Section 8.2)"
    )
    kind: InstructorKind = InstructorKind.unknown
    availability: list[AvailabilityWindow] = Field(
        default_factory=list, description="Empty = no restriction recorded"
    )


class Room(_Model):
    id: str = Field(min_length=1)
    building: str = ""
    name: str = ""
    room_type: RoomType
    capacity: int | None = Field(
        default=None, gt=0, description="O-07: not public; synthetic until obtained"
    )


class RoomPool(_Model):
    """Alternative to named rooms when only counts per type are known (O-07)."""

    room_type: RoomType
    count: int = Field(gt=0)
    capacity: int | None = Field(default=None, gt=0)


class Cohort(_Model):
    id: str = Field(min_length=1)
    kind: CohortKind
    label: str = Field(min_length=1, description="e.g. 'E2 CCE'")
    size: int | None = Field(default=None, ge=0)


class NoClashGroup(_Model):
    """Courses whose meetings must not overlap for a cohort (H1, pairwise definition, D-06)."""

    id: str = Field(min_length=1)
    cohort_id: str
    course_ids: list[str] = Field(min_length=2)
    source: str = Field(min_length=1, description="Provenance of the rule")

    @field_validator("course_ids")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate course in no-clash group")
        return v


class ExternalFixedMeeting(_TimeWindow):
    """A non-EECE class the cohort must attend; blocked time for that cohort (H8, Section 7.5)."""

    id: str = Field(min_length=1)
    cohort_id: str
    label: str = Field(min_length=1)


class ClashException(_Model):
    """An approved permission for two courses to overlap (Section 7.2)."""

    id: str = Field(min_length=1)
    course_a: str
    course_b: str
    reason: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_on: date

    @model_validator(mode="after")
    def _different(self):
        if self.course_a == self.course_b:
            raise ValueError("a clash exception needs two different courses")
        return self


# ---------------------------------------------------------------- root


class TermData(_Model):
    schema_version: str = "1.0"
    provenance: Provenance
    term: Term
    slot_grid: list[TimeSlot] = Field(
        default_factory=list, description="O-06; may be empty until known"
    )
    courses: list[Course] = Field(min_length=1)
    sections: list[Section] = Field(default_factory=list)
    instructors: list[Instructor] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    room_pools: list[RoomPool] = Field(default_factory=list)
    cohorts: list[Cohort] = Field(default_factory=list)
    no_clash_groups: list[NoClashGroup] = Field(default_factory=list)
    external_meetings: list[ExternalFixedMeeting] = Field(default_factory=list)
    clash_exceptions: list[ClashException] = Field(default_factory=list)

    @model_validator(mode="after")
    def _referential_integrity(self):
        errors: list[str] = []

        def unique(name: str, ids: list[str]) -> set[str]:
            seen, dup = set(), set()
            for i in ids:
                (dup if i in seen else seen).add(i)
            if dup:
                errors.append(f"duplicate {name} id(s): {sorted(dup)}")
            return seen

        course_ids = unique("course", [c.id for c in self.courses])
        unique("section", [s.id for s in self.sections])
        unique("slot", [t.id for t in self.slot_grid])
        instructor_ids = unique("instructor", [i.id for i in self.instructors])
        room_ids = unique("room", [r.id for r in self.rooms])
        cohort_ids = unique("cohort", [c.id for c in self.cohorts])
        unique("no-clash group", [g.id for g in self.no_clash_groups])
        unique("external meeting", [e.id for e in self.external_meetings])
        unique("clash exception", [e.id for e in self.clash_exceptions])
        unique("meeting", [m.id for s in self.sections for m in s.meetings])

        pool_types = [p.room_type for p in self.room_pools]
        if len(set(pool_types)) != len(pool_types):
            errors.append("room_pools: one pool per room type")

        for c in self.courses:
            for cc in c.coupled_courses:
                if cc not in course_ids:
                    errors.append(f"course {c.id}: coupled course {cc!r} not found")
                if cc == c.id:
                    errors.append(f"course {c.id}: cannot be coupled with itself")

        for s in self.sections:
            if s.course_id not in course_ids:
                errors.append(f"section {s.id}: course {s.course_id!r} not found")
            for i in s.instructor_ids:
                if i not in instructor_ids:
                    errors.append(f"section {s.id}: instructor {i!r} not found")
            for m in s.meetings:
                if m.placement:
                    for r in m.placement.room_ids:
                        if r not in room_ids:
                            errors.append(f"meeting {m.id}: room {r!r} not found")

        for g in self.no_clash_groups:
            if g.cohort_id not in cohort_ids:
                errors.append(
                    f"no-clash group {g.id}: cohort {g.cohort_id!r} not found"
                )
            for c in g.course_ids:
                if c not in course_ids:
                    errors.append(f"no-clash group {g.id}: course {c!r} not found")

        for e in self.external_meetings:
            if e.cohort_id not in cohort_ids:
                errors.append(
                    f"external meeting {e.id}: cohort {e.cohort_id!r} not found"
                )

        for x in self.clash_exceptions:
            for c in (x.course_a, x.course_b):
                if c not in course_ids:
                    errors.append(f"clash exception {x.id}: course {c!r} not found")

        if errors:
            raise ValueError("; ".join(errors))
        return self
