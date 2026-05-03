from jiwer import cer

from .base import BaseMetric


class CERMetric(BaseMetric):
    name = "cer"

    def compute(self, hypothesis: str, reference: str) -> float:
        return cer(reference, hypothesis)
