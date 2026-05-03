from jiwer import wer

from .base import BaseMetric


class WERMetric(BaseMetric):
    name = "wer"

    def compute(self, hypothesis: str, reference: str) -> float:
        return wer(reference, hypothesis)
