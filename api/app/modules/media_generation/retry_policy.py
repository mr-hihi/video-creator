from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.media_generation.media_task import ProviderErrorKind

MAX_CAPTCHA_ATTEMPTS = 10
BACKOFF_BASE_SEC = 10
BACKOFF_CAP_SEC = 300
UNUSUAL_ACTIVITY_PAUSE_SEC = 120


class RetryAction(StrEnum):
    REQUEUE = "requeue"
    FAIL = "fail"


@dataclass(frozen=True)
class RetryDecision:
    action: RetryAction
    attempts: int
    next_attempt_at: datetime | None = None
    pauses_google_flow: bool = False


def decide_retry(
    error_kind: ProviderErrorKind, attempts: int, max_attempts: int, now: datetime
) -> RetryDecision:
    if error_kind in (ProviderErrorKind.INPUT_EXPIRED, ProviderErrorKind.NOT_CONNECTED):
        return RetryDecision(RetryAction.REQUEUE, attempts, now)
    if error_kind is ProviderErrorKind.UNUSUAL_ACTIVITY:
        return RetryDecision(RetryAction.FAIL, attempts + 1, pauses_google_flow=True)
    if error_kind in (ProviderErrorKind.FATAL, ProviderErrorKind.NO_ANSWER):
        return RetryDecision(RetryAction.FAIL, attempts + 1)
    counted_attempts = attempts + 1
    attempt_limit = (
        MAX_CAPTCHA_ATTEMPTS if error_kind is ProviderErrorKind.CAPTCHA else max_attempts
    )
    if counted_attempts >= attempt_limit:
        return RetryDecision(RetryAction.FAIL, counted_attempts)
    return RetryDecision(
        RetryAction.REQUEUE, counted_attempts, now + to_backoff_delay(counted_attempts)
    )


def to_backoff_delay(counted_attempts: int) -> timedelta:
    return timedelta(seconds=min(2**counted_attempts * BACKOFF_BASE_SEC, BACKOFF_CAP_SEC))
