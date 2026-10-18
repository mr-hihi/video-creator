import io
from pathlib import Path

import numpy as np
import soundfile

WAV_MEDIA_TYPE = "audio/wav"


def samples_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, sample_rate, format="WAV")
    return buffer.getvalue()


def file_to_wav(path: Path) -> bytes:
    samples, sample_rate = soundfile.read(path)
    return samples_to_wav(samples, sample_rate)
