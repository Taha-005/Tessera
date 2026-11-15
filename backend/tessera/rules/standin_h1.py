"""STAND-IN check for H1 only, to test that toggling a rule changes validator behavior (T-025).

Not the validator. The real one is T-034 (independent validator, shared clash interface T-033),
which will replace this module and reuse the toggle tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from tessera.data.schema import TermData, to_minutes
from tessera.rules.config import RuleConfig


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "violation" (hard) or "penalty" (soft, weight > 0)
    detail: str
    weight: int = 0


def _overlap(a, b) -> bool:
    if not set(a.days) & set(b.days):
        return False
    return to_minutes(a.start) < to_minutes(b.end) and to_minutes(b.start) < to_minutes(
        a.end
    )


def check_h1(term: TermData, rules: RuleConfig) -> list[Finding]:
    """Pairwise no-clash check over placed meetings, honoring clash exceptions."""
    if not rules.is_enabled("H1"):
        return []
    hard = rules.is_hard("H1")
    excepted = {frozenset((x.course_a, x.course_b)) for x in term.clash_exceptions}
    placed: dict[str, list] = {}
    for s in term.sections:
        for m in s.meetings:
            if m.placement:
                placed.setdefault(s.course_id, []).append((s.id, m.id, m.placement))
    out: list[Finding] = []
    for g in term.no_clash_groups:
        cs = g.course_ids
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                if frozenset((cs[i], cs[j])) in excepted:
                    continue
                for _, ma, pa in placed.get(cs[i], []):
                    for _, mb, pb in placed.get(cs[j], []):
                        if _overlap(pa, pb):
                            detail = (
                                f"group {g.id}: {cs[i]} ({ma}) overlaps {cs[j]} ({mb})"
                            )
                            out.append(
                                Finding("H1", "violation", detail)
                                if hard
                                else Finding(
                                    "H1", "penalty", detail, rules.weight("H1")
                                )
                            )
    return out
