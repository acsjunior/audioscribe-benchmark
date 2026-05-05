import re
from abc import ABC, abstractmethod


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)  # remove pontuação, mantém acentos
    text = re.sub(r"\s+", " ", text)       # colapsa espaços e quebras de linha
    return text.strip()


class BaseMetric(ABC):
    name: str

    @abstractmethod
    def compute(self, hypothesis: str, reference: str) -> float: ...
