from dataclasses import replace
from typing import Any

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiAsk, AiLimits, AiModelChoice, AiStepGroup
from app.modules.film_clones.clone_activity import AiActivityTracker


class WatchedCloneAiCaller:
    def __init__(self, ai_caller: AiCaller, limits: AiLimits, activity: AiActivityTracker):
        self._ai_caller = ai_caller
        self._limits = limits
        self._activity = activity

    def find_model(self) -> AiModelChoice:
        return self._ai_caller.find_model(AiStepGroup.FILM_CLONE)

    def ask(self, clone_id: str, choice: AiModelChoice, ask: AiAsk) -> dict[str, Any]:
        self._activity.start(clone_id, choice)
        watched_limits = replace(
            self._limits, on_output=lambda: self._activity.record_output(clone_id)
        )
        try:
            return self._ai_caller.ask_for_json(choice, ask, watched_limits)
        finally:
            self._activity.finish(clone_id)
