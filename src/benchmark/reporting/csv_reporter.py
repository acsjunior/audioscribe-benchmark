import csv
from pathlib import Path

from ..models import ExperimentResult


def write_csv(results: list[ExperimentResult], output_path: Path) -> None:
    if not results:
        return

    metric_keys = list(results[0].metrics.keys())
    fieldnames = [
        "song_id", "artista", "titulo", "ano", "album",
        "refinement_provider", "refinement_model", "prompt_name", "prompt_file",
        "tokens_used", "response_time_ms", "error",
    ] + metric_keys

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "song_id": r.song_id,
                "artista": r.artista,
                "titulo": r.titulo,
                "ano": r.ano,
                "album": r.album,
                "refinement_provider": r.refinement_provider or "baseline",
                "refinement_model": r.refinement_model or "",
                "prompt_name": r.prompt_name or "",
                "prompt_file": r.prompt_file or "",
                "tokens_used": r.tokens_used if r.tokens_used is not None else "",
                "response_time_ms": f"{r.response_time_ms:.0f}" if r.response_time_ms else "",
                "error": r.error or "",
            }
            row.update({k: v if v is not None else "" for k, v in r.metrics.items()})
            writer.writerow(row)
