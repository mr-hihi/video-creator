import json
import os
import time
from typing import Any

import httpx
from adapter_app import Audio, MusicOrder, create_app, serve

DEFAULT_PORT = 8011
ACESTEP_API_URL = os.environ.get("ACESTEP_API_URL", "http://127.0.0.1:8001").rstrip("/")
INSTRUMENTAL_LYRICS = os.environ.get("ACESTEP_INSTRUMENTAL_LYRICS", "[Instrumental]")
SHORTEST_TRACK_S = 10
LONGEST_TRACK_S = 600
POLL_EVERY_SEC = 3.0
WAIT_LIMIT_SEC = float(os.environ.get("ACESTEP_WAIT_LIMIT_SEC", "1800"))
SUCCEEDED_STATUS = 1
FAILED_STATUS = 2
AUDIO_FORMAT = "wav"
WAV_MEDIA_TYPE = "audio/wav"

http_client = httpx.Client(base_url=ACESTEP_API_URL, timeout=60)


def check_health() -> None:
    try:
        http_client.get("/", timeout=5)
    except httpx.HTTPError as error:
        raise RuntimeError(f"acestep-api is not reachable at {ACESTEP_API_URL}: {error}") from error


def make_music(order: MusicOrder) -> Audio:
    duration_s = min(max(order.durationS or SHORTEST_TRACK_S, SHORTEST_TRACK_S), LONGEST_TRACK_S)
    task_id = submit_task(
        {
            "prompt": order.prompt,
            "lyrics": INSTRUMENTAL_LYRICS if order.instrumental else "",
            "audio_duration": duration_s,
            "audio_format": AUDIO_FORMAT,
        }
    )
    file_url = wait_for_file(task_id)
    response = http_client.get(file_url)
    response.raise_for_status()
    return Audio(response.content, WAV_MEDIA_TYPE)


def submit_task(body: dict[str, Any]) -> str:
    response = http_client.post("/release_task", json=body)
    response.raise_for_status()
    return str(response.json()["data"]["task_id"])


def wait_for_file(task_id: str) -> str:
    waited_sec = 0.0
    while waited_sec < WAIT_LIMIT_SEC:
        response = http_client.post("/query_result", json={"task_id_list": [task_id]})
        response.raise_for_status()
        item = find_task_item(response.json(), task_id)
        if item.get("status") == FAILED_STATUS:
            raise RuntimeError(f"ACE-Step failed: {item.get('result') or item}")
        if item.get("status") == SUCCEEDED_STATUS:
            return find_file_url(item.get("result"))
        time.sleep(POLL_EVERY_SEC)
        waited_sec += POLL_EVERY_SEC
    raise RuntimeError(f"ACE-Step gave no track after {int(WAIT_LIMIT_SEC)} s")


def find_task_item(answer: Any, task_id: str) -> dict[str, Any]:
    items = answer.get("data", answer) if isinstance(answer, dict) else answer
    if isinstance(items, dict):
        items = [items]
    for item in items or []:
        if str(item.get("task_id", task_id)) == task_id:
            return item
    return {}


def find_file_url(result: Any) -> str:
    parsed = json.loads(result) if isinstance(result, str) else result
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    file_url = parsed.get("file") if isinstance(parsed, dict) else None
    if not file_url:
        raise RuntimeError("ACE-Step answered without a file")
    return str(file_url)


if __name__ == "__main__":
    serve(
        create_app("ACE-Step adapter", make_music=make_music, check_health=check_health),
        DEFAULT_PORT,
    )
