"""Constraint vocabulary (T-016): the closed set of constraint types of Section 11.1
with the common fields of Section 11.2, as a Pydantic discriminated union on ``type``.

Decisions (2026-11-14):
- ``preference`` is a wrapper type: it holds one other constraint (target type + params)
  and is always soft with a weight. That keeps the 11 types of Section 11.1.
- Majors in ``major_restriction`` are plain major codes (e.g. ECMP, EECE, EMCH, INDE),
  checked against the codes that appear in the AUB section restrictions.

Rules enforced here:
- Params reference entity IDs, never free-text names (checked against a term by
  ``validate_references``).
- Hard constraints have no weight; soft ones need a weight.
- ``stability`` and ``preference`` are always soft.
- ``active`` constraints must be approved (approved_by + approved_at).
- Anything outside the vocabulary goes through ``unsupported``: flagged to the
  user, never approximated, and it can never become active.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from tessera.data.schema import (
    ComponentType,
    RoomType,
    TermData,
    parse_days,
    to_minutes,
)

_MAJOR_CODE = re.compile(r"^[A-Z]{2,6}$")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _time(v: str | None) -> str | None:
    if v is not None:
        to_minutes(v)
    return v


# ---------------------------------------------------------------- common fields (11.2)


class SourceKind(str, Enum):
    note = "note"  # extracted from a natural-language note or request
    learned = "learned"  # proposed from data (e.g. co-enrollment), needs evidence
    manual = "manual"  # entered in the structured editor
    imported = "imported"  # came with imported department data


class Status(str, Enum):
    proposed = "proposed"
    active = "active"
    rejected = "rejected"
    retired = "retired"


class _Common(_M):
    id: str = Field(min_length=1)
    term_id: str = Field(min_length=1)
    hard: bool = True
    weight: int | None = Field(
        default=None, ge=1, description="Required when soft; forbidden when hard"
    )
    source: str = Field(min_length=1, description="e.g. 'email from lead scheduler'")
    source_kind: SourceKind
    evidence: str | None = Field(
        default=None, description="Required for learned constraints"
    )
    status: Status = Status.proposed
    author: str = Field(min_length=1)
    created_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _common_rules(self):
        if self.hard and self.weight is not None:
            raise ValueError("a hard constraint has no weight")
        if not self.hard and self.weight is None:
            raise ValueError("a soft constraint needs a weight")
        if self.source_kind == SourceKind.learned and not self.evidence:
            raise ValueError("a learned constraint needs evidence")
        if self.status == Status.active and not (self.approved_by and self.approved_at):
            raise ValueError(
                "an active constraint must have approved_by and approved_at"
            )
        if self.approved_at and self.approved_at < self.created_at:
            raise ValueError("approved_at is before created_at")
        return self


# ---------------------------------------------------------------- params per type (11.1)


class NoClashGroupParams(_M):
    cohort_id: str = Field(min_length=1)
    course_ids: list[str] = Field(min_length=2)

    @field_validator("course_ids")
    @classmethod
    def _uniq(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("duplicate course")
        return v


class ClashExceptionParams(_M):
    scope: Literal["course", "section"]
    a: str = Field(min_length=1)
    b: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _diff(self):
        if self.a == self.b:
            raise ValueError("a clash exception needs two different ids")
        return self


class InstructorDaysParams(_M):
    instructor_id: str = Field(min_length=1)
    allowed_patterns: list[str] = Field(min_length=1, description="e.g. ['TR']")

    @field_validator("allowed_patterns")
    @classmethod
    def _p(cls, v):
        return [parse_days(x) for x in v]


class _Window(_M):
    earliest: str | None = Field(
        default=None, description="HH:MM; meetings start at or after"
    )
    latest: str | None = Field(
        default=None, description="HH:MM; meetings end at or before"
    )

    _t = field_validator("earliest", "latest")(classmethod(lambda cls, v: _time(v)))

    @model_validator(mode="after")
    def _w(self):
        if self.earliest is None and self.latest is None:
            raise ValueError("give earliest, latest or both")
        if (
            self.earliest
            and self.latest
            and to_minutes(self.earliest) >= to_minutes(self.latest)
        ):
            raise ValueError("earliest must be before latest")
        return self


class InstructorTimeWindowParams(_Window):
    instructor_id: str = Field(min_length=1)
    days: str | None = Field(
        default=None, description="Restrict the window to these days; empty = all"
    )

    _d = field_validator("days")(classmethod(lambda cls, v: parse_days(v) if v else v))


class ComponentTimeWindowParams(_Window):
    course_id: str = Field(min_length=1)
    component: ComponentType


class RoomRequirementParams(_M):
    section_id: str | None = None
    course_id: str | None = None
    component: ComponentType | None = None
    room_type: RoomType
    min_capacity: int | None = Field(default=None, gt=0)
    slack: int | None = Field(
        default=None, ge=0, description="Extra seats above section size"
    )

    @model_validator(mode="after")
    def _target(self):
        if bool(self.section_id) == bool(self.course_id):
            raise ValueError(
                "target either a section_id or a course_id (with optional component), not both"
            )
        if self.section_id and self.component:
            raise ValueError("component is only used with course_id")
        return self


class ParallelRoomsParams(_M):
    course_id: str = Field(min_length=1)
    component: ComponentType
    rooms: int = Field(ge=2, description="Rooms held at the same time")
    room_type: RoomType


class MajorRestrictionParams(_M):
    section_ids: list[str] = Field(min_length=1)
    allowed_majors: list[str] = Field(
        min_length=1, description="Major codes, e.g. ['EMCH']"
    )
    day_pattern: str | None = Field(
        default=None, description="Pattern these sections must use, e.g. 'MW'"
    )

    @field_validator("allowed_majors")
    @classmethod
    def _codes(cls, v):
        bad = [x for x in v if not _MAJOR_CODE.match(x)]
        if bad:
            raise ValueError(
                f"not major codes: {bad} (use codes like ECMP, EECE, EMCH, INDE)"
            )
        return v

    _d = field_validator("day_pattern")(
        classmethod(lambda cls, v: parse_days(v) if v else v)
    )


class ExternalBlockParams(_M):
    cohort_id: str = Field(min_length=1)
    external_meeting_id: str = Field(min_length=1)


class StabilityParams(_M):
    base_version_id: str | None = Field(
        default=None, description="Schedule version to stay close to"
    )


class UnsupportedParams(_M):
    original_text: str = Field(min_length=1)
    reason: str = Field(min_length=1, description="Why it does not fit the vocabulary")


# Types a preference may wrap (everything except preference, stability and unsupported).
WRAPPABLE: dict[str, type[_M]] = {
    "no_clash_group": NoClashGroupParams,
    "clash_exception": ClashExceptionParams,
    "instructor_days": InstructorDaysParams,
    "instructor_time_window": InstructorTimeWindowParams,
    "component_time_window": ComponentTimeWindowParams,
    "room_requirement": RoomRequirementParams,
    "parallel_rooms": ParallelRoomsParams,
    "major_restriction": MajorRestrictionParams,
    "external_block": ExternalBlockParams,
}


class PreferenceParams(_M):
    target_type: Literal[tuple(WRAPPABLE)]  # type: ignore[valid-type]
    target: dict[str, Any]

    @model_validator(mode="after")
    def _validate_target(self):
        # validate the wrapped params; store them in normalized form
        model = WRAPPABLE[self.target_type].model_validate(self.target)
        object.__setattr__(
            self, "target", model.model_dump(mode="json", exclude_none=True)
        )
        return self

    def target_params(self) -> _M:
        return WRAPPABLE[self.target_type].model_validate(self.target)


# ---------------------------------------------------------------- constraint classes


class NoClashGroup(_Common):
    type: Literal["no_clash_group"]
    params: NoClashGroupParams


class ClashException(_Common):
    type: Literal["clash_exception"]
    params: ClashExceptionParams


class InstructorDays(_Common):
    type: Literal["instructor_days"]
    params: InstructorDaysParams


class InstructorTimeWindow(_Common):
    type: Literal["instructor_time_window"]
    params: InstructorTimeWindowParams


class ComponentTimeWindow(_Common):
    type: Literal["component_time_window"]
    params: ComponentTimeWindowParams


class RoomRequirement(_Common):
    type: Literal["room_requirement"]
    params: RoomRequirementParams


class ParallelRooms(_Common):
    type: Literal["parallel_rooms"]
    params: ParallelRoomsParams


class MajorRestriction(_Common):
    type: Literal["major_restriction"]
    params: MajorRestrictionParams


class ExternalBlock(_Common):
    type: Literal["external_block"]
    params: ExternalBlockParams


class _AlwaysSoft(_Common):
    hard: bool = False

    @model_validator(mode="after")
    def _soft(self):
        if self.hard:
            raise ValueError(f"{self.type} is always soft")
        return self


class Preference(_AlwaysSoft):
    type: Literal["preference"]
    params: PreferenceParams


class Stability(_AlwaysSoft):
    type: Literal["stability"]
    params: StabilityParams


class Unsupported(_Common):
    """The unsupported path: kept for the user to see; never reaches the solver."""

    type: Literal["unsupported"]
    params: UnsupportedParams

    @model_validator(mode="after")
    def _never_active(self):
        if self.status in (Status.active, Status.retired):
            raise ValueError(
                "an unsupported constraint can only be proposed or rejected"
            )
        return self


Constraint = Annotated[
    NoClashGroup | ClashException | InstructorDays | InstructorTimeWindow | ComponentTimeWindow | RoomRequirement | ParallelRooms | MajorRestriction | ExternalBlock | Preference | Stability | Unsupported,
    Field(discriminator="type"),
]
SUPPORTED_TYPES = list(WRAPPABLE) + [
    "preference",
    "stability",
]  # the 11 types of Section 11.1

_adapter = TypeAdapter(Constraint)
_list_adapter = TypeAdapter(list[Constraint])


def parse_constraint(data: dict | str | bytes):
    """Parse one constraint from a dict or JSON. Raises pydantic.ValidationError."""
    if isinstance(data, (str, bytes)):
        return _adapter.validate_json(data)
    return _adapter.validate_python(data)


def parse_constraints(data: list | str | bytes) -> list:
    if isinstance(data, (str, bytes)):
        return _list_adapter.validate_json(data)
    return _list_adapter.validate_python(data)


def dump_constraint(c) -> dict:
    return _adapter.dump_python(c, mode="json", exclude_none=True)


# ---------------------------------------------------------------- references (entity IDs only)


def validate_references(
    c, term: TermData, known_majors: set[str] | None = None
) -> list[str]:
    """Return problems with the IDs a constraint refers to; empty list = all resolve.

    This is where free-text names are rejected: 'Dr. Kabalan' is not an instructor ID.
    """
    errs: list[str] = []
    courses = {x.id for x in term.courses}
    sections = {x.id for x in term.sections}
    instructors = {x.id for x in term.instructors}
    cohorts = {x.id for x in term.cohorts}
    externals = {x.id for x in term.external_meetings}

    def need(kind: str, value: str, pool: set[str]):
        if value not in pool:
            errs.append(
                f"unknown {kind} {value!r} (constraints must reference {kind} IDs, not names)"
            )

    if c.term_id != term.term.id:
        errs.append(
            f"constraint is for term {c.term_id!r}, data is for {term.term.id!r}"
        )

    t, p = c.type, c.params
    if t == "preference":
        t, p = p.target_type, p.target_params()

    if t == "no_clash_group":
        need("cohort", p.cohort_id, cohorts)
        for x in p.course_ids:
            need("course", x, courses)
    elif t == "clash_exception":
        pool = courses if p.scope == "course" else sections
        need(p.scope, p.a, pool)
        need(p.scope, p.b, pool)
    elif t in ("instructor_days", "instructor_time_window"):
        need("instructor", p.instructor_id, instructors)
    elif t in ("component_time_window", "parallel_rooms"):
        need("course", p.course_id, courses)
    elif t == "room_requirement":
        if p.section_id:
            need("section", p.section_id, sections)
        else:
            need("course", p.course_id, courses)
    elif t == "major_restriction":
        for x in p.section_ids:
            need("section", x, sections)
        if known_majors is not None:
            for m in p.allowed_majors:
                if m not in known_majors:
                    errs.append(f"unknown major code {m!r}")
    elif t == "external_block":
        need("cohort", p.cohort_id, cohorts)
        need("external meeting", p.external_meeting_id, externals)
    return errs
