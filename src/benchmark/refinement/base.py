from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PromptConfig:
    name: str
    description: str
    system: str
    user: str
    file: str
    examples: list[dict] | None = None

    def format_user(self, transcription: str) -> str:
        return self.user.format(transcription=transcription)


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


class BaseRefiner(ABC):
    provider: str
    model: str

    @abstractmethod
    async def refine(self, transcription: str, prompt: PromptConfig) -> RefinementResult: ...
