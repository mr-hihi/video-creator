import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

AI_IMAGE_MEDIA_TYPE = "image/jpeg"


@dataclass(frozen=True)
class AiImageEncoding:
    max_side_px: int
    jpeg_quality: int


def to_ai_jpeg_base64(path: Path, encoding: AiImageEncoding) -> str:
    with Image.open(path) as image:
        scaled_image = image.convert("RGB")
    scaled_image.thumbnail((encoding.max_side_px, encoding.max_side_px))
    buffer = io.BytesIO()
    scaled_image.save(buffer, format="JPEG", quality=encoding.jpeg_quality)
    return base64.b64encode(buffer.getvalue()).decode("ascii")
