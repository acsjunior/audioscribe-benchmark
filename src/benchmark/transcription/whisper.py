import logging
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

from .base import BaseTranscriber

logger = logging.getLogger("benchmark")

# Known Whisper hallucination patterns (regex, case-insensitive).
# Add new entries here as new hallucinations are identified.
HALLUCINATION_PATTERNS: list[str] = [
    # Padrões específicos primeiro para evitar remoção parcial por padrões mais curtos
    r"Legendas pela comunidade Amara\.org",
    r"Subtitles by the Amara\.org community",
    r"Legendas:\s+Amara\.org",
    r"Tradução e legendas\s*:",
    # Padrões genéricos depois
    r"Amara\.org",
    r"Legendas\s*:",
    r"Transcrição\s*:",
    r"Legendado por\s*:",
    r"Transcrição por\s*:",
]


def _remove_hallucinations(text: str) -> str:
    for pattern in HALLUCINATION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


class WhisperTranscriber(BaseTranscriber):
    def __init__(self, model: str = "whisper-1") -> None:
        self.model = model
        self.client = AsyncOpenAI()

    async def transcribe(self, audio_path: Path) -> str:
        logger.debug(f"Transcribing {audio_path.name} with {self.model}")
        start = time.monotonic()

        with open(audio_path, "rb") as f:
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                language="pt",
            )

        elapsed = (time.monotonic() - start) * 1000
        logger.debug(f"Transcription completed in {elapsed:.0f}ms")
        return _remove_hallucinations(response.text)
