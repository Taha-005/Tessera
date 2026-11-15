"""Rule configuration (T-025): hard rules H1-H11 and soft objectives S1-S5.

Two files, merged at startup:
- ``default_rules.toml`` (in the repo): every rule, its structure, generic defaults.
- an **overrides** file in the data location (``DATA_DIR/rule_overrides.toml``, team drive,
  never committed): values derived from the department (interview, meetings), per the
  ticket and D-13. ``create_app`` loads it at startup when it exists.

Every rule and every parameter value carries a ``source`` and a ``status``
(PROPOSED / CONFIRMED / DECIDED). Values stay PROPOSED until O-14 is answered.
The merged result is validated; any problem stops startup with a clear message.
"""

from __future__ import annotations

import re
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

HARD_IDS = [f"H{i}" for i in range(1, 12)]
SOFT_IDS = [f"S{i}" for i in range(1, 6)]
DEFAULT_PATH = Path(__file__).with_name("default_rules.toml")
OVERRIDES_FILENAME = "rule_overrides.toml"  # looked up in settings.data_dir

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Allowed parameters per rule and their types. Unknown parameters are rejected.
PARAM_SPEC: dict[str, dict[str, str]] = {
    "H1": {"definition": "enum:pairwise|cohort_block"},
    "H2": {"exempt_components": "list[str]"},
    "H3": {},
    "H4": {},
    "H5": {"room_model": "enum:named_rooms|pools"},
    "H6": {"default_slack": "int>=0"},
    "H7": {},
    "H8": {},
    "H9": {"part_time_instructor_earliest": "time"},
    "H10": {},
    "H11": {},
    "S1": {},
    "S2": {"target_slack": "int>=0"},
    "S3": {"min_co_enrollment_share": "float0-1"},
    "S4": {"moved_meeting_penalty": "int>=1"},
    "S5": {"graduate_min_course_number": "int>=1", "graduate_earliest": "time"},
}


class Status(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    DECIDED = "DECIDED"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Param(_M):
    value: Any
    source: str = Field(min_length=1)
    status: Status = Status.PROPOSED


class Rule(_M):
    name: str = Field(min_length=1)
    enabled: bool = True
    hard: bool
    weight: int | None = Field(default=None, ge=1)
    source: str = Field(min_length=1)
    status: Status = Status.PROPOSED
    params: dict[str, Param] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _weight(self):
        if self.hard and self.weight is not None:
            raise ValueError("a hard rule has no weight")
        if not self.hard and self.weight is None:
            raise ValueError("a soft rule needs a weight")
        return self


class RuleConfig(_M):
    schema_version: str = "1.0"
    rules: dict[str, Rule]
    loaded_from: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete(self):
        errs = []
        ids = set(self.rules)
        missing = [r for r in HARD_IDS + SOFT_IDS if r not in ids]
        unknown = sorted(ids - set(HARD_IDS + SOFT_IDS))
        if missing:
            errs.append(f"missing rules {missing}")
        if unknown:
            errs.append(f"unknown rules {unknown}")
        for rid in SOFT_IDS:
            if rid in self.rules and self.rules[rid].hard:
                errs.append(f"{rid} is a soft objective; it cannot be hard")
        for rid, rule in self.rules.items():
            spec = PARAM_SPEC.get(rid, {})
            for pname, p in rule.params.items():
                if pname not in spec:
                    errs.append(
                        f"{rid}: unknown parameter {pname!r} (allowed: {sorted(spec)})"
                    )
                    continue
                problem = _check_type(spec[pname], p.value)
                if problem:
                    errs.append(f"{rid}.{pname}: {problem}")
        if errs:
            raise ValueError("; ".join(errs))
        return self

    # ------------------------------------------------------------ queries
    def is_enabled(self, rule_id: str) -> bool:
        return self.rules[rule_id].enabled

    def is_hard(self, rule_id: str) -> bool:
        r = self.rules[rule_id]
        return r.enabled and r.hard

    def weight(self, rule_id: str) -> int:
        r = self.rules[rule_id]
        return 0 if not r.enabled or r.hard else int(r.weight)

    def param(self, rule_id: str, name: str, default: Any = None) -> Any:
        p = self.rules[rule_id].params.get(name)
        return default if p is None else p.value

    def provenance(self) -> list[dict[str, str]]:
        """Flat list of every rule and parameter with its value, source and status."""
        out = []
        for rid in HARD_IDS + SOFT_IDS:
            r = self.rules[rid]
            out.append(
                {
                    "item": rid,
                    "value": f"enabled={r.enabled}, hard={r.hard}, weight={r.weight}",
                    "source": r.source,
                    "status": r.status.value,
                }
            )
            for pname, p in r.params.items():
                out.append(
                    {
                        "item": f"{rid}.{pname}",
                        "value": repr(p.value),
                        "source": p.source,
                        "status": p.status.value,
                    }
                )
        return out


def _check_type(kind: str, v: Any) -> str | None:
    if kind.startswith("enum:"):
        allowed = kind[5:].split("|")
        return None if v in allowed else f"must be one of {allowed}"
    if kind == "list[str]":
        return (
            None
            if isinstance(v, list) and all(isinstance(x, str) for x in v)
            else "must be a list of strings"
        )
    if kind == "time":
        return (
            None if isinstance(v, str) and _HHMM.match(v) else "must be HH:MM (24-hour)"
        )
    if kind in ("int>=0", "int>=1"):
        lo = int(kind[-1])
        return (
            None
            if isinstance(v, int) and not isinstance(v, bool) and v >= lo
            else f"must be an integer >= {lo}"
        )
    if kind == "float0-1":
        return (
            None
            if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
            else "must be 0..1"
        )
    return f"unknown spec {kind}"


class RuleConfigError(ValueError):
    """Raised at startup when the rule configuration is invalid."""


# ---------------------------------------------------------------- loading


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuleConfigError(f"rule file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise RuleConfigError(f"{path.name}: not valid TOML ({e})") from e


def _merge(base: dict, over: dict, label: str) -> None:
    """Apply an overrides document onto the base document, in place."""
    for rid, ov in (over.get("rules") or {}).items():
        if rid not in base["rules"]:
            raise RuleConfigError(f"{label}: override for unknown rule {rid!r}")
        tgt = base["rules"][rid]
        for k, v in ov.items():
            if k == "params":
                tgt.setdefault("params", {})
                for pname, pv in v.items():
                    tgt["params"][pname] = (
                        pv  # a param override replaces value, source and status
                    )
            else:
                tgt[k] = v
        if any(k in ov for k in ("enabled", "hard", "weight")) and "source" not in ov:
            raise RuleConfigError(
                f"{label}: override of {rid} changes its settings without a source"
            )


def overrides_path_for(data_dir: Path) -> Path | None:
    """The department overrides file in the data location, or None if there is none."""
    p = Path(data_dir) / OVERRIDES_FILENAME
    return p if p.exists() else None


def load_rules(
    default_path: str | Path = DEFAULT_PATH, overrides_path: str | Path | None = None
) -> RuleConfig:
    """Load the defaults, apply the overrides file if given, validate.

    Called at startup by ``create_app``; raises RuleConfigError with every problem listed.
    """
    default_path = Path(default_path)
    doc = _read_toml(default_path)
    loaded = [str(default_path)]
    if overrides_path:
        op = Path(overrides_path)
        _merge(doc, _read_toml(op), op.name)
        loaded.append(str(op))
    doc["loaded_from"] = loaded
    try:
        return RuleConfig.model_validate(doc)
    except ValidationError as e:
        lines = [
            f"  - {'.'.join(str(x) for x in err['loc']) or '(root)'}: {err['msg']}"
            for err in e.errors()
        ]
        raise RuleConfigError("invalid rule configuration\n" + "\n".join(lines)) from e
