"""Turns a JSON constraint back into a plain-English line, with plain code (no LLM).

The department approves THIS text, not the LLM's own wording, so what they read is
exactly what the solver will enforce.
"""


def _days(patterns):
    return " or ".join(patterns)


def describe(c: dict) -> str:
    p, t = c.get("params", {}), c.get("type")
    strength = "MUST" if c.get("hard", True) else f"PREFERS (weight {c.get('weight')})"
    if t == "instructor_days":
        return f"{p['instructor_id']} {strength} teach only on {_days(p['allowed_patterns'])} days"
    if t == "course_days":
        return f"{p['course_id']} {strength} meet only on {_days(p['allowed_patterns'])} days"
    if t in ("instructor_time_window", "component_time_window"):
        who = p.get("instructor_id") or (
            f"{p.get('course_id') + ' ' if p.get('course_id') else 'all '}{p['component']}s")
        parts = []
        if p.get("earliest"):
            parts.append(f"start at or after {p['earliest']}")
        if p.get("latest"):
            parts.append(f"end by {p['latest']}")
        on = f" on {p['days']}" if p.get("days") else ""
        verb = "MUST" if c.get("hard", True) else f"PREFER (weight {c.get('weight')}) to"
        return f"{who}: {verb} {' and '.join(parts)}{on}"
    if t == "no_clash_group":
        mode = ("whichever section a student is in, a clash-free full schedule exists"
                if p.get("mode", "every_section") == "every_section"
                else "at least one clash-free combination exists")
        who = f"{p['cohort_id']}: " if p.get("cohort_id") else ""
        return f"{who}{', '.join(p['course_ids'])} can be taken together ({mode})"
    if t == "clash_exception":
        return f"{p['a']} and {p['b']} MAY clash ({p['reason']})"
    if t == "unsupported":
        return f"NOT SUPPORTED, needs a person: {c.get('source')}"
    return f"{t}: {p}"
