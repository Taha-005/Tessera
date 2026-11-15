"""T-025 tests: startup validation, overrides from DATA_DIR, source tags,
and toggling a rule changes validator behavior (through a stand-in H1 check)."""

import tomllib
from pathlib import Path

import pytest

from tessera.data.schema import TermData
from tessera.data.term_io import load_json
from tessera.main import create_app
from tessera.rules import (
    DEFAULT_PATH,
    HARD_IDS,
    OVERRIDES_FILENAME,
    SOFT_IDS,
    RuleConfig,
    RuleConfigError,
    load_rules,
)
from tessera.rules.standin_h1 import check_h1

EXAMPLE_OVERRIDES = DEFAULT_PATH.with_name("overrides.example.toml")
TERM = load_json(
    Path(__file__).resolve().parents[2]
    / "data"
    / "synthetic"
    / "example_term"
    / "term.json"
)


def write(tmp_path, text, name="o.toml"):
    p = tmp_path / name
    p.write_text(text)
    return p


def base_doc():
    return tomllib.loads(DEFAULT_PATH.read_text())


# ---------------------------------------------------------------- loads and is complete


def test_defaults_load_and_list_all_rules():
    cfg = load_rules()
    assert set(cfg.rules) == set(HARD_IDS + SOFT_IDS)
    assert all(cfg.is_hard(h) for h in HARD_IDS)
    assert all(not cfg.is_hard(s) and cfg.weight(s) >= 1 for s in SOFT_IDS)


@pytest.mark.parametrize("overrides", [None, EXAMPLE_OVERRIDES])
def test_every_value_carries_a_source_tag(overrides):
    for row in load_rules(overrides_path=overrides).provenance():
        assert row["source"].strip(), row
        assert row["status"] in {"PROPOSED", "CONFIRMED", "DECIDED"}


def test_example_overrides_applied():
    cfg = load_rules(overrides_path=EXAMPLE_OVERRIDES)
    assert cfg.param("H6", "default_slack") == 5
    assert cfg.weight("S1") == 3
    assert len(cfg.loaded_from) == 2


def test_without_overrides_department_values_absent():
    assert load_rules().param("H9", "part_time_instructor_earliest") is None


# ---------------------------------------------------------------- validated at startup


def test_startup_loads_rules_without_overrides(env):
    assert create_app().state.rules.is_hard("H1")


def test_startup_reads_overrides_from_data_dir(env, tmp_path):
    write(
        tmp_path,
        '[rules.H9]\nparams.part_time_instructor_earliest = { value = "14:00", source = "test" }',
        OVERRIDES_FILENAME,
    )
    rules = create_app().state.rules
    assert rules.param("H9", "part_time_instructor_earliest") == "14:00"


def test_startup_fails_on_invalid_overrides(env, tmp_path):
    write(tmp_path, '[rules.H12]\nhard = true\nsource = "x"', OVERRIDES_FILENAME)
    with pytest.raises(RuleConfigError, match="unknown rule"):
        create_app()


@pytest.mark.parametrize(
    "text,match",
    [
        ('[rules.H12]\nhard = true\nsource = "x"', "unknown rule"),
        ("[rules.H1]\nenabled = false", "without a source"),
        (
            '[rules.H9]\nparams.part_time_instructor_earliest = { value = "2pm", source = "x" }',
            "HH:MM",
        ),
        (
            '[rules.H6]\nparams.default_slack = { value = -1, source = "x" }',
            "integer >= 0",
        ),
        (
            '[rules.H1]\nparams.definition = { value = "blocks", source = "x" }',
            "must be one of",
        ),
        (
            '[rules.H3]\nparams.max_per_day = { value = 3, source = "x" }',
            "unknown parameter",
        ),
        ("[rules.H6]\nparams.default_slack = { value = 3 }", "source"),
        ('[rules.H1]\nhard = false\nsource = "x"', "soft rule needs a weight"),
        ('[rules.H1]\nweight = 3\nsource = "x"', "hard rule has no weight"),
        (
            '[rules.S1]\nhard = true\nweight = 1\nsource = "x"',
            "hard rule has no weight",
        ),
        ('[rules.S2]\nstatus = "MAYBE"\nsource = "x"', "status"),
        ("this is not toml", "not valid TOML"),
    ],
)
def test_invalid_config_rejected(tmp_path, text, match):
    with pytest.raises(RuleConfigError, match=match):
        load_rules(overrides_path=write(tmp_path, text))


def test_soft_objective_cannot_be_made_hard():
    doc = base_doc()
    doc["rules"]["S1"]["hard"] = True
    doc["rules"]["S1"].pop("weight")
    with pytest.raises(ValueError, match="cannot be hard"):
        RuleConfig.model_validate(doc)


def test_missing_rule_rejected():
    doc = base_doc()
    del doc["rules"]["H7"]
    with pytest.raises(ValueError, match="missing rules"):
        RuleConfig.model_validate(doc)


def test_missing_file_reported(tmp_path):
    with pytest.raises(RuleConfigError, match="not found"):
        load_rules(overrides_path=tmp_path / "nope.toml")


# ---------------------------------------------------------------- toggling changes validator behavior


def clashing_term() -> TermData:
    """Synthetic term where SYN 101 and SYN 102 (same no-clash group) overlap."""
    raw = TERM.model_dump(mode="json")
    raw["sections"][0]["meetings"][0]["placement"] = {
        "days": "MWF",
        "start": "09:00",
        "end": "09:50",
        "room_ids": ["R-A101"],
    }
    return TermData.model_validate(raw)


def test_h1_hard_reports_violation():
    f = check_h1(clashing_term(), load_rules())
    assert len(f) == 1 and f[0].severity == "violation"


def test_toggle_h1_off_removes_violation(tmp_path):
    cfg = load_rules(
        overrides_path=write(tmp_path, '[rules.H1]\nenabled = false\nsource = "test"')
    )
    assert check_h1(clashing_term(), cfg) == []


def test_toggle_h1_soft_reports_weighted_penalty(tmp_path):
    cfg = load_rules(
        overrides_path=write(
            tmp_path, '[rules.H1]\nhard = false\nweight = 7\nsource = "test"'
        )
    )
    f = check_h1(clashing_term(), cfg)
    assert len(f) == 1 and f[0].severity == "penalty" and f[0].weight == 7


def test_no_clash_no_finding():
    assert check_h1(TERM, load_rules()) == []


def test_clash_exception_respected():
    raw = clashing_term().model_dump(mode="json")
    raw["clash_exceptions"].append(
        {
            "id": "E-2",
            "course_a": "SYN 101",
            "course_b": "SYN 102",
            "reason": "test",
            "approved_by": "x",
            "approved_on": "2026-11-14",
        }
    )
    assert check_h1(TermData.model_validate(raw), load_rules()) == []
