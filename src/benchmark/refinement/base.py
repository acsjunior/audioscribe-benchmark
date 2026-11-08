import collections
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..utils.retry import NonRetryableError


@dataclass
class PromptConfig:
    name: str
    description: str
    system: str
    user: str
    file: str
    examples: list[dict] | None = None

    def format_user(self, transcription: str, metadata: dict | None = None) -> str:
        kwargs: dict = {"transcription": transcription}
        if metadata:
            kwargs.update(metadata)
        return self.user.format_map(collections.defaultdict(str, kwargs))


@dataclass
class RefinementResult:
    refined_text: str
    tokens_used: int | None = None
    response_time_ms: float | None = None


def load_prompt(prompt_file: str) -> PromptConfig:
    path = Path(prompt_file)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PromptConfig(
        name=data["name"],
        description=data.get("description", ""),
        system=data["system"],
        user=data["user"],
        file=str(path),
        examples=data.get("examples"),
    )


class TruncatedResponseError(RuntimeError):
    """Levantado quando a resposta do LLM foi cortada por limite de tokens."""


class BlockedResponseError(RuntimeError, NonRetryableError):
    """Levantado quando o provedor bloqueou ou recusou a resposta (filtro de conteúdo/recitação).

    O texto devolvido nesses casos é parcial (cortado no meio da frase) e não pode ser
    avaliado como uma revisão. Com temperatura 0 o bloqueio se repete, então não há retry.
    """


class BaseRefiner(ABC):
    provider: str
    model: str

    @abstractmethod
    async def refine(
        self, transcription: str, prompt: PromptConfig, metadata: dict | None = None
    ) -> RefinementResult: ...
