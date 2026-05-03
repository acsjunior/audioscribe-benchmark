import logging
import time
from pathlib import Path

from openai import AsyncOpenAI

from .base import BaseTranscriber

logger = logging.getLogger("benchmark")


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
        return response.text
