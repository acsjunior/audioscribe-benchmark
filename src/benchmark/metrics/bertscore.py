from bert_score import score as bert_score_fn

from .base import BaseMetric


class BERTScoreMetric(BaseMetric):
    name = "bertscore"

    def compute(self, hypothesis: str, reference: str) -> float:
        _, _, f1 = bert_score_fn([hypothesis], [reference], lang="pt", verbose=False)
        return f1.item()
