import re

UNSAFE_FILENAME_CHARS = re.compile(r"[^\w\-. ]+")


def to_safe_file_stem(text: str, fallback_stem: str) -> str:
    stem = UNSAFE_FILENAME_CHARS.sub("_", text).strip(" ._")
    return stem or fallback_stem
