from jiwer import wer

from .base import BaseMetric, normalize


class WERMetric(BaseMetric):
    name = "wer"

    def compute(self, hypothesis: str, reference: str) -> float:
        return wer(normalize(reference), normalize(hypothesis))
