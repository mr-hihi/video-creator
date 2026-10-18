import json
from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandError, CommandRunner
from app.modules.jobs.video_to_markdown.transcript import Transcript, whisper_json_to_transcript

TRANSCRIPT_BASENAME = "transcript"


@dataclass(frozen=True)
class WhisperConfig:
    whisper_bin: str
    model_path: Path
    timeout_sec: float


class WhisperCppTranscriber:
    def __init__(self, config: WhisperConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def transcribe(self, audio_path: Path, language: str) -> Transcript:
        if not self._config.model_path.is_file():
            raise CommandError(
                f"Whisper model not found at {self._config.model_path}. "
                "Run `sh run.sh setup_whisper` or set WHISPER_MODEL_PATH."
            )
        output_base = audio_path.with_name(TRANSCRIPT_BASENAME)
        self._runner.run(
            Command(
                args=[
                    self._config.whisper_bin,
                    "-m",
                    str(self._config.model_path),
                    "-f",
                    str(audio_path),
                    "-l",
                    language,
                    "-oj",
                    "-of",
                    str(output_base),
                    "-np",
                ],
                timeout_sec=self._config.timeout_sec,
            )
        )
        # whisper.cpp can split a multibyte character across tokens, emitting invalid UTF-8.
        raw_json = output_base.with_suffix(".json").read_text(encoding="utf-8", errors="replace")
        return whisper_json_to_transcript(json.loads(raw_json), language)
