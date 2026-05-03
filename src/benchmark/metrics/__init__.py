from .base import BaseMetric
from .bertscore import BERTScoreMetric
from .cer import CERMetric
from .wer import WERMetric

METRIC_REGISTRY: dict[str, type[BaseMetric]] = {
    "wer": WERMetric,
    "cer": CERMetric,
    "bertscore": BERTScoreMetric,
}


def get_metrics(names: list[str]) -> list[BaseMetric]:
    metrics = []
    for name in names:
        if name not in METRIC_REGISTRY:
            raise ValueError(f"Unknown metric: '{name}'. Available: {list(METRIC_REGISTRY)}")
        metrics.append(METRIC_REGISTRY[name]())
    return metrics
