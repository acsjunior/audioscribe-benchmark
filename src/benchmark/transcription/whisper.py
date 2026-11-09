import logging
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

from ..audio_utils import anonymous_audio
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

# Prompt padrão para gpt-4o-transcribe quando nenhum prompt é fornecido explicitamente.
DEFAULT_PROMPT_GPT4O_TRANSCRIBE = (
    "A transcrição a seguir é de um samba brasileiro antigo das décadas de 1920 a 1950. "
    "Vocabulário arcaico, português coloquial carioca da época. "
    "Artistas como Cartola, Nelson Cavaquinho, Sinhô, João da Baiana, Francisco Alves."
)

# Modelos que suportam o parâmetro prompt na API de transcrição.
SUPPORTED_MODELS = {"whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"}


def effective_prompt(model: str, prompt: str | None) -> str | None:
    """Prompt efetivamente enviado à API: o configurado ou o padrão do modelo."""
    if prompt is not None:
        return prompt
    if model == "gpt-4o-transcribe":
        return DEFAULT_PROMPT_GPT4O_TRANSCRIBE
    return None


def _remove_hallucinations(text: str) -> str:
    for pattern in HALLUCINATION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


class WhisperTranscriber(BaseTranscriber):
    def __init__(self, model: str = "whisper-1", prompt: str | None = None) -> None:
        self.model = model
        self.prompt = prompt
        self.client = AsyncOpenAI()

    def _effective_prompt(self) -> str | None:
        return effective_prompt(self.model, self.prompt)

    async def transcribe(self, audio_path: Path) -> str:
        logger.debug(f"Transcribing {audio_path.name} with {self.model}")
        start = time.monotonic()

        kwargs: dict = {"model": self.model, "language": "pt"}
        effective_prompt = self._effective_prompt()
        if effective_prompt is not None:
            kwargs["prompt"] = effective_prompt

        # Nome neutro e sem tags: o nome do arquivo identificaria a música.
        response = await self.client.audio.transcriptions.create(
            file=anonymous_audio(audio_path), **kwargs
        )

        elapsed = (time.monotonic() - start) * 1000
        logger.debug(f"Transcription completed in {elapsed:.0f}ms")
        return _remove_hallucinations(response.text)
