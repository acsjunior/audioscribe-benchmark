from jiwer import cer

from .base import BaseMetric, normalize


class CERMetric(BaseMetric):
    name = "cer"

    def compute(self, hypothesis: str, reference: str) -> float:
        return cer(normalize(reference), normalize(hypothesis))
