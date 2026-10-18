import os
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path

from adapter_app import Audio, MusicOrder, create_app, serve
from audio_files import WAV_MEDIA_TYPE, file_to_wav
from yue2 import YuE2Pipeline

DEFAULT_PORT = 8012
MODEL_ID = os.environ.get("YUE_MODEL", "m-a-p/YuE2-3B")
DEVICE = os.environ.get("YUE_DEVICE", "cuda")
INSTRUMENTAL_LYRICS = os.environ.get("YUE_INSTRUMENTAL_LYRICS", "")
AUDIO_FILE_PATTERN = "audio.*"


def build_music_maker(exit_stack: ExitStack):
    pipeline = exit_stack.enter_context(YuE2Pipeline.from_pretrained(MODEL_ID, device=DEVICE))
    pipeline_lock = threading.Lock()

    def make_music(order: MusicOrder) -> Audio:
        with pipeline_lock:
            song = pipeline(style=order.prompt, lyrics=INSTRUMENTAL_LYRICS)
        with tempfile.TemporaryDirectory() as work_dir:
            song.save_artifacts(work_dir)
            audio_path = next(Path(work_dir).glob(AUDIO_FILE_PATTERN), None)
            if audio_path is None:
                raise RuntimeError("YuE saved no audio file")
            return Audio(file_to_wav(audio_path), WAV_MEDIA_TYPE)

    return make_music


if __name__ == "__main__":
    with ExitStack() as stack:
        serve(create_app("YuE adapter", make_music=build_music_maker(stack)), DEFAULT_PORT)
