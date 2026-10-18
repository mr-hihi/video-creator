import threading
from collections.abc import Callable
from pathlib import Path


class VoiceCopyCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._voice_ids_by_sample: dict[str, str] = {}

    def find_or_make(self, sample_paths: tuple[Path, ...], make_copy: Callable[[], str]) -> str:
        sample_key = "|".join(map(_to_sample_key, sample_paths))
        with self._lock:
            voice_id = self._voice_ids_by_sample.get(sample_key)
            if voice_id is None:
                voice_id = make_copy()
                self._voice_ids_by_sample[sample_key] = voice_id
            return voice_id


def _to_sample_key(path: Path) -> str:
    stat = path.stat()
    return f"{path}:{stat.st_size}:{stat.st_mtime_ns}"
