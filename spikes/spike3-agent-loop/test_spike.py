"""The same scenarios run on both versions; they must behave identically.

These are the T-068 "done when" cases (step limit, tool error, ask path) plus a normal run.
"""

import pytest
from tessera.data.schema import TermData

import langgraph_agent
import plain_loop
from common import Answer, Ask, LoopingModel, ScriptedModel, ToolCall, load_term

LOOPS = {"plain": plain_loop.run, "langgraph": langgraph_agent.run}
TERM = load_term()


def clashing_term() -> TermData:
    """The synthetic term with SYN 101's lecture placed on top of SYN 102's (MWF 09:00)."""
    raw = TERM.model_dump(mode="json")
    raw["sections"][0]["meetings"][0]["placement"] = {
        "days": "MWF",
        "start": "09:00",
        "end": "09:50",
        "room_ids": ["R-A101"],
    }
    return TermData.model_validate(raw)


def happy_script():
    return [
        ToolCall(name="query_data", args={"course_id": "SYN 102"}),
        ToolCall(
            name="check_clash", args={"course_a": "SYN 101", "course_b": "SYN 102"}
        ),
        Answer(text="Yes: SYN 101 and SYN 102 both meet MWF 09:00."),
    ]


@pytest.fixture(params=LOOPS)
def run(request):
    return LOOPS[request.param]


def test_normal_run_calls_tools_and_answers(run):
    model = ScriptedModel(happy_script())
    out = run("Do SYN 101 and SYN 102 clash?", model, clashing_term())
    assert out.status == "answered"
    assert [(s.kind, s.name) for s in out.trace] == [
        ("model", "query_data"),
        ("tool", "query_data"),
        ("model", "check_clash"),
        ("tool", "check_clash"),
        ("model", "answer"),
    ]
    assert out.trace[3].output["output"]["clash"] is True
    # the model saw each tool result before deciding its next step
    assert model.seen[2][-1]["result"]["output"]["clash"] is True


def test_no_clash_in_example_term(run):
    out = run("clash?", ScriptedModel(happy_script()), TERM)
    assert out.trace[3].output["output"] == {"clash": False, "details": []}


def test_step_limit_stops_the_loop(run):
    model = LoopingModel()
    out = run("loop forever", model, TERM, max_steps=4)
    assert out.status == "step_limit"
    assert model.calls == 4
    assert sum(s.kind == "model" for s in out.trace) == 4


def test_tool_error_goes_back_to_model_which_asks_user(run):
    model = ScriptedModel(
        [
            ToolCall(name="query_data", args={"course_id": "EECE 999"}),
            Ask(question="I can't find EECE 999 this term. Which course did you mean?"),
        ]
    )
    out = run("When is EECE 999?", model, TERM)
    assert out.status == "asked_user"
    assert out.trace[1].status == "error"
    assert model.seen[1][-1]["result"]["error"] == "UNKNOWN_ENTITY"


@pytest.mark.parametrize(
    "call,code",
    [
        (ToolCall(name="check_clash", args={"course_a": "SYN 101"}), "INVALID_ARGS"),
        (ToolCall(name="delete_schedule", args={}), "UNKNOWN_TOOL"),
    ],
)
def test_bad_tool_calls_do_not_crash(run, call, code):
    model = ScriptedModel([call, Answer(text="Sorry, I could not do that.")])
    out = run("x", model, TERM)
    assert out.status == "answered"
    assert out.trace[1].output["error"] == code


SCENARIOS = {
    "normal": (happy_script, clashing_term()),
    "error_then_ask": (
        lambda: [
            ToolCall(name="query_data", args={"course_id": "X"}),
            Ask(question="Which?"),
        ],
        TERM,
    ),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_both_versions_behave_identically(name):
    script, term = SCENARIOS[name]
    a = plain_loop.run("q", ScriptedModel(script()), term)
    b = langgraph_agent.run("q", ScriptedModel(script()), term)
    strip = lambda o: [
        (s.step, s.kind, s.name, s.input, s.output, s.status) for s in o.trace
    ]
    assert (a.status, a.text, a.history, strip(a)) == (
        b.status,
        b.text,
        b.history,
        strip(b),
    )
