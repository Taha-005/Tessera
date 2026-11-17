"""Rule configuration (T-025): hard rules H1-H11 and soft objectives S1-S5."""

from tessera.rules.config import (
    DEFAULT_PATH,
    HARD_IDS,
    OVERRIDES_FILENAME,
    PARAM_SPEC,
    SOFT_IDS,
    RuleConfig,
    RuleConfigError,
    load_rules,
    overrides_path_for,
)

__all__ = [
    "DEFAULT_PATH",
    "HARD_IDS",
    "OVERRIDES_FILENAME",
    "PARAM_SPEC",
    "SOFT_IDS",
    "RuleConfig",
    "RuleConfigError",
    "load_rules",
    "overrides_path_for",
]
