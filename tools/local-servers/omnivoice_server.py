import os
import threading

import torch
from adapter_app import Audio, SpeechOrder, create_app, serve
from audio_files import WAV_MEDIA_TYPE, samples_to_wav
from omnivoice import OmniVoice

DEFAULT_PORT = 8010
OMNIVOICE_SAMPLE_RATE = 24000
MODEL_ID = os.environ.get("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")


def pick_device() -> str:
    if os.environ.get("OMNIVOICE_DEVICE"):
        return os.environ["OMNIVOICE_DEVICE"]
    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def build_speech_maker():
    device = pick_device()
    model = OmniVoice.from_pretrained(
        MODEL_ID,
        device_map=device,
        dtype=torch.float32 if device == "cpu" else torch.float16,
    )
    model_lock = threading.Lock()

    def make_speech(order: SpeechOrder) -> Audio:
        with model_lock:
            outputs = model.generate(
                text=order.text,
                ref_audio=str(order.sample_path),
                ref_text=order.sample_text or None,
            )
        return Audio(samples_to_wav(outputs[0], OMNIVOICE_SAMPLE_RATE), WAV_MEDIA_TYPE)

    return make_speech


if __name__ == "__main__":
    serve(create_app("OmniVoice adapter", make_speech=build_speech_maker()), DEFAULT_PORT)
