from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import (
    AiAsk,
    AiCallError,
    AiLimits,
    AiModelChoice,
    AiStepGroup,
)
from app.modules.film_clones.clone_activity import AiActivity, AiActivityTracker
from app.modules.film_clones.clone_ai_caller import WatchedCloneAiCaller
from app.modules.providers.provider_catalog import ProviderId

CLONE_ID = "clone-1"
CHOICE = AiModelChoice(ProviderId.OPENAI, "gpt-6-luna")
LIMITS = AiLimits(timeout_sec=3600, silence_limit_sec=900)
ASK = AiAsk(instructions="Assets", message="Notes", reply_schema={"type": "object"})


def build_rig(answer):
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = CHOICE
    tracker = AiActivityTracker(lambda: "now")
    seen: list = []

    def ask_for_json(choice, ask, limits):
        seen.append(tracker.get(CLONE_ID))
        limits.on_output()
        seen.append(tracker.get(CLONE_ID))
        return answer()

    ai_caller.ask_for_json.side_effect = ask_for_json
    caller = WatchedCloneAiCaller(ai_caller, LIMITS, tracker)
    return SimpleNamespace(caller=caller, ai_caller=ai_caller, tracker=tracker, seen=seen)


@pytest.fixture
def clone_call():
    rig = build_rig(lambda: {"assets": []})
    reply = rig.caller.ask(CLONE_ID, CHOICE, ASK)
    choice, ask, limits = rig.ai_caller.ask_for_json.call_args.args
    return SimpleNamespace(reply=reply, rig=rig, choice=choice, ask=ask, limits=limits)


@pytest.fixture
def failed_clone_call():
    def fail():
        raise AiCallError("openai stopped responding for 900s")

    rig = build_rig(fail)
    with pytest.raises(AiCallError) as caught:
        rig.caller.ask(CLONE_ID, CHOICE, ASK)
    return SimpleNamespace(error=caught.value, tracker=rig.tracker)


@pytest.fixture
def found_model():
    rig = build_rig(dict)
    return SimpleNamespace(model=rig.caller.find_model(), ai_caller=rig.ai_caller)


def test_a_clone_call_runs_with_the_watched_limits(clone_call):
    assert (clone_call.choice, clone_call.ask) == (CHOICE, ASK)
    assert (clone_call.limits.timeout_sec, clone_call.limits.silence_limit_sec) == (3600, 900)
    assert clone_call.reply == {"assets": []}


def test_a_clone_call_shows_its_model_until_it_ends(clone_call):
    assert clone_call.rig.seen == [
        AiActivity(choice=CHOICE, started_at="now", last_output_at=None),
        AiActivity(choice=CHOICE, started_at="now", last_output_at="now"),
    ]
    assert clone_call.rig.tracker.get(CLONE_ID) is None


def test_a_failed_clone_call_clears_the_activity(failed_clone_call):
    assert str(failed_clone_call.error) == "openai stopped responding for 900s"
    assert failed_clone_call.tracker.get(CLONE_ID) is None


def test_the_model_of_a_clone_call_is_the_film_clone_model(found_model):
    assert found_model.model == CHOICE
    found_model.ai_caller.find_model.assert_called_once_with(AiStepGroup.FILM_CLONE)
