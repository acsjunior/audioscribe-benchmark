from abc import ABC, abstractmethod


class BaseMetric(ABC):
    name: str

    @abstractmethod
    def compute(self, hypothesis: str, reference: str) -> float: ...
