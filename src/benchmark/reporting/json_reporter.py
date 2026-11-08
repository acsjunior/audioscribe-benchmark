import json
from dataclasses import asdict, fields
from pathlib import Path

from ..models import ExperimentResult


def write_json(results: list[ExperimentResult], output_path: Path) -> None:
    data = [asdict(r) for r in results]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(input_path: Path) -> list[ExperimentResult]:
    """Lê um results.json. Campos ausentes (resultados antigos) assumem o valor padrão."""
    known = {f.name for f in fields(ExperimentResult)}
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for item in data:
        item = {k: v for k, v in item.items() if k in known}
        if item.get("refinement_provider") == "baseline":
            item["refinement_provider"] = None
        results.append(ExperimentResult(**item))
    return results
