import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import yaml

NORMALIZATION_FILE = Path(__file__).with_name("normalization.yaml")


@lru_cache(maxsize=1)
def _normalization_rules() -> tuple[frozenset[str], list[tuple[list[str], list[str]]]]:
    with open(NORMALIZATION_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    interjections = frozenset(w.lower() for w in data.get("interjections", []))
    equivalences = [
        (src.lower().split(), dst.lower().split())
        for src, dst in (data.get("equivalences") or {}).items()
    ]
    equivalences.sort(key=lambda pair: len(pair[0]), reverse=True)  # mais longas primeiro
    return interjections, equivalences


def _apply_equivalences(words: list[str], rules: list[tuple[list[str], list[str]]]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(words):
        for src, dst in rules:
            if words[i : i + len(src)] == src:
                out.extend(dst)
                i += len(src)
                break
        else:
            out.append(words[i])
            i += 1
    return out


def basic_normalize(text: str) -> str:
    """Minúsculas, sem pontuação (apóstrofo junta: "p'ra" → "pra"), espaços colapsados."""
    text = text.lower()
    text = re.sub(r"['’`´]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)  # remove pontuação, mantém acentos
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize(text: str) -> str:
    """Normalização das métricas (PROTOCOLO 6.2), igual para referência e transcrição.

    Além de ``basic_normalize``: remove as interjeições e aplica as equivalências de
    grafia de ``normalization.yaml``.
    """
    interjections, equivalences = _normalization_rules()
    words = [w for w in basic_normalize(text).split() if w not in interjections]
    return " ".join(_apply_equivalences(words, equivalences))


class BaseMetric(ABC):
    name: str

    @abstractmethod
    def compute(self, hypothesis: str, reference: str) -> float: ...
