"""Conferência com áudio (E7): o modelo ouve a gravação e propõe alterações no rascunho.

Fluxo: rascunho → segmentos numerados → modelo multimodal (áudio + segmentos
[+ metadados]) → lista de alterações (JSON) → aplicação por código.

Os prompts ficam em YAML (``prompts/verification/``) e usam marcadores substituídos
por ``str.replace`` (o texto do prompt pode conter JSON com chaves):

- ``{segments}``: o rascunho numerado (``[1] ...``);
- ``{metadata}``: título, autoria, intérprete e ano, ou vazio se ``metadata: false``;
- ``{audio_note}``: instrução sobre a fonte da evidência (áudio anexo ou só o texto),
  para que a variante sem áudio difira apenas nisso.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..transcription.multimodal import get_audio_llm
from .edits import EditOutcome, apply_edits, parse_edits
from .segments import render, segment

AUDIO_NOTE_WITH_AUDIO = (
    "Você recebe a gravação em áudio. Baseie cada alteração no que você ouvir na gravação."
)
AUDIO_NOTE_WITHOUT_AUDIO = (
    "Você não recebe o áudio; baseie-se apenas no texto do rascunho."
)


@dataclass
class VerificationPrompt:
    name: str
    description: str
    system: str
    user: str
    file: str


def load_verification_prompt(prompt_file: str) -> VerificationPrompt:
    path = Path(prompt_file)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VerificationPrompt(
        name=data["name"],
        description=data.get("description", ""),
        system=data["system"],
        user=data["user"],
        file=str(path),
    )


def format_metadata(metadata: dict | None) -> str:
    if not metadata:
        return ""
    labels = [("titulo", "Título"), ("autoria", "Autoria"),
              ("interpretacao", "Intérprete"), ("ano", "Ano")]
    lines = [f"{label}: {metadata[key]}" for key, label in labels if metadata.get(key)]
    return "Informações da gravação:\n" + "\n".join(lines) + "\n" if lines else ""


@dataclass
class VerificationOutput:
    text: str
    segments: list[str]
    outcomes: list[EditOutcome]
    raw_response: str
    response_time_ms: float
    extra: dict = field(default_factory=dict)

    @property
    def num_applied(self) -> int:
        return sum(o.applied for o in self.outcomes)


class Verifier:
    def __init__(self, provider: str, model: str, prompt: VerificationPrompt) -> None:
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.llm = get_audio_llm(provider, model)

    def build_user_message(
        self, segments: list[str], with_audio: bool, metadata: dict | None
    ) -> str:
        note = AUDIO_NOTE_WITH_AUDIO if with_audio else AUDIO_NOTE_WITHOUT_AUDIO
        return (
            self.prompt.user.replace("{segments}", render(segments))
            .replace("{metadata}", format_metadata(metadata))
            .replace("{audio_note}", note)
        )

    async def verify(
        self, draft: str, audio_path: Path | None, metadata: dict | None = None
    ) -> VerificationOutput:
        """Confere o rascunho. ``EditParseError`` se a resposta não for uma lista válida."""
        segments = segment(draft)
        user = self.build_user_message(segments, audio_path is not None, metadata)
        start = time.monotonic()
        raw = await self.llm.complete(user, audio_path, system=self.prompt.system)
        elapsed = (time.monotonic() - start) * 1000
        edits = parse_edits(raw)
        text, outcomes = apply_edits(segments, edits)
        return VerificationOutput(
            text=text,
            segments=segments,
            outcomes=outcomes,
            raw_response=raw,
            response_time_ms=elapsed,
        )
