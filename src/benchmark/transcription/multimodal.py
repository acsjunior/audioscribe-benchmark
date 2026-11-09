"""Transcrição direta por LLMs multimodais (entrada de áudio) — grupo de controle do E7.

Um LLM com entrada de áudio ouve a gravação e escreve a letra, sem passar por um modelo
de transcrição dedicado. Serve para separar dois efeitos que o E7 (conferência com áudio)
mistura: "um modelo que ouve melhor" e "conferir um rascunho com o áudio". Se transcrever
direto já rende o mesmo que conferir, a conferência não acrescenta nada.

O prompt é uma instrução neutra, sem título, autoria ou intérprete: não há como o modelo
acertar por memorização do nome da música, que é o que o E7 vai testar à parte.

Provedores (``transcription.provider``):

- ``google``: Gemini via ``google-genai`` (áudio enviado inline);
- ``openai-audio``: modelos ``gpt-audio*`` via Chat Completions (``input_audio``).
"""

import asyncio
import base64
import logging
import os
import time
from pathlib import Path

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from ..refinement.base import BlockedResponseError, TruncatedResponseError
from ..refinement.google import BLOCKED_FINISH_REASONS
from .base import BaseTranscriber

logger = logging.getLogger("benchmark")

DEFAULT_MULTIMODAL_PROMPT = (
    "Ouça esta gravação de um samba brasileiro antigo (décadas de 1920 a 1950) e "
    "transcreva a letra cantada, em português. Escreva apenas o que é cantado, sem "
    "títulos, comentários, marcações de tempo ou explicações. Se um trecho for "
    "inaudível, transcreva só o que for possível ouvir, sem inventar."
)

AUDIO_MIME_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
OPENAI_AUDIO_FORMATS = {".mp3": "mp3", ".wav": "wav"}


def multimodal_prompt(prompt: str | None) -> str:
    """Instrução efetivamente enviada: a configurada ou a padrão."""
    return prompt if prompt is not None else DEFAULT_MULTIMODAL_PROMPT


def _clean(text: str | None) -> str:
    """Remove espaços no fim das linhas (os modelos costumam terminá-las com 2 espaços)."""
    return "\n".join(line.rstrip() for line in (text or "").strip().splitlines())


def _suffix(audio_path: Path, supported: dict[str, str]) -> str:
    suffix = audio_path.suffix.lower()
    if suffix not in supported:
        raise ValueError(
            f"Formato de áudio não suportado para transcrição multimodal: '{suffix}' "
            f"(aceitos: {sorted(supported)})"
        )
    return suffix


class GeminiTranscriber(BaseTranscriber):
    def __init__(self, model: str = "gemini-2.5-flash", prompt: str | None = None) -> None:
        self.model = model
        self.prompt = multimodal_prompt(prompt)
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))

    def _call_sync(self, audio_path: Path) -> str:
        mime = AUDIO_MIME_TYPES[_suffix(audio_path, AUDIO_MIME_TYPES)]
        audio = types.Part.from_bytes(data=audio_path.read_bytes(), mime_type=mime)
        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[types.Part(text=self.prompt), audio])],
            config=types.GenerateContentConfig(temperature=0.0),
        )

        finish = response.candidates[0].finish_reason if response.candidates else None
        name = finish.name if finish is not None else None
        if name in BLOCKED_FINISH_REASONS:
            raise BlockedResponseError(
                f"Google {self.model} bloqueou a resposta (finish_reason={name})"
            )
        if name == "MAX_TOKENS":
            raise TruncatedResponseError(
                f"Google {self.model} truncou a resposta (finish_reason=MAX_TOKENS)"
            )
        text = _clean(response.text)
        if not text:
            raise RuntimeError(f"Google {self.model} devolveu uma resposta vazia")
        return text

    async def transcribe(self, audio_path: Path) -> str:
        logger.debug(f"Transcribing {audio_path.name} with {self.model}")
        start = time.monotonic()
        text = await asyncio.to_thread(self._call_sync, audio_path)
        logger.debug(f"Transcription completed in {(time.monotonic() - start) * 1000:.0f}ms")
        return text


class OpenAIAudioTranscriber(BaseTranscriber):
    def __init__(self, model: str = "gpt-audio", prompt: str | None = None) -> None:
        self.model = model
        self.prompt = multimodal_prompt(prompt)
        self.client = AsyncOpenAI()

    async def transcribe(self, audio_path: Path) -> str:
        logger.debug(f"Transcribing {audio_path.name} with {self.model}")
        fmt = OPENAI_AUDIO_FORMATS[_suffix(audio_path, OPENAI_AUDIO_FORMATS)]
        data = base64.b64encode(audio_path.read_bytes()).decode("ascii")

        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=self.model,
            modalities=["text"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {"type": "input_audio", "input_audio": {"data": data, "format": fmt}},
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        elapsed = (time.monotonic() - start) * 1000

        choice = response.choices[0]
        if choice.finish_reason == "content_filter":
            raise BlockedResponseError(
                f"OpenAI {self.model} bloqueou a resposta (finish_reason=content_filter)"
            )
        if choice.finish_reason == "length":
            raise TruncatedResponseError(
                f"OpenAI {self.model} truncou a resposta (finish_reason=length)"
            )
        text = _clean(choice.message.content)
        if not text:
            raise RuntimeError(f"OpenAI {self.model} devolveu uma resposta vazia")
        logger.debug(f"Transcription completed in {elapsed:.0f}ms")
        return text


MULTIMODAL_TRANSCRIBERS: dict[str, type[BaseTranscriber]] = {
    "google": GeminiTranscriber,
    "openai-audio": OpenAIAudioTranscriber,
}


def get_multimodal_transcriber(
    provider: str, model: str, prompt: str | None = None
) -> BaseTranscriber:
    if provider not in MULTIMODAL_TRANSCRIBERS:
        raise ValueError(
            f"Provedor de transcrição multimodal desconhecido: '{provider}'. "
            f"Disponíveis: {list(MULTIMODAL_TRANSCRIBERS)}"
        )
    return MULTIMODAL_TRANSCRIBERS[provider](model=model, prompt=prompt)
