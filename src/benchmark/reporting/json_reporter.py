import json
from dataclasses import asdict
from pathlib import Path

from ..models import ExperimentResult


def write_json(results: list[ExperimentResult], output_path: Path) -> None:
    data = [asdict(r) for r in results]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
