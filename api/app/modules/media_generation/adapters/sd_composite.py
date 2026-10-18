import io
from pathlib import Path

from PIL import Image, ImageOps

LOCATION_KIND = "location"
GREY_CANVAS_COLOR = (128, 128, 128)
REFERENCE_HEIGHT_SHARE = 0.6
COMPOSITE_FORMAT = "PNG"


def build_composite(
    size: tuple[int, int],
    base_path: Path | None,
    references: tuple[Path, ...],
    reference_kinds: tuple[str, ...],
) -> bytes:
    pasted_references = list(references)
    if base_path is None:
        base_path = _find_location_reference(references, reference_kinds)
        if base_path is not None:
            pasted_references.remove(base_path)
    canvas = (
        Image.new("RGB", size, GREY_CANVAS_COLOR)
        if base_path is None
        else _cover(_open_rgb(base_path), size)
    )
    _paste_side_by_side(canvas, [_open_rgb(path) for path in pasted_references])
    output = io.BytesIO()
    canvas.save(output, COMPOSITE_FORMAT)
    return output.getvalue()


def _find_location_reference(
    references: tuple[Path, ...], reference_kinds: tuple[str, ...]
) -> Path | None:
    for reference, kind in zip(references, reference_kinds, strict=False):
        if kind == LOCATION_KIND:
            return reference
    return None


def _open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS)


def _paste_side_by_side(canvas: Image.Image, images: list[Image.Image]) -> None:
    if not images:
        return
    target_height = round(canvas.height * REFERENCE_HEIGHT_SHARE)
    widths = [round(image.width * target_height / image.height) for image in images]
    shrink = min(1.0, canvas.width / sum(widths))
    height = max(1, round(target_height * shrink))
    left = (canvas.width - sum(max(1, round(width * shrink)) for width in widths)) // 2
    for image, width in zip(images, widths, strict=True):
        scaled_width = max(1, round(width * shrink))
        canvas.paste(
            image.resize((scaled_width, height), Image.Resampling.LANCZOS),
            (left, canvas.height - height),
        )
        left += scaled_width
