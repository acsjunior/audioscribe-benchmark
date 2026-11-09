"""Análise estatística dos resultados de um experimento.

Cada método de refinamento é comparado com o baseline (a transcrição bruta) de forma
**pareada**: a revisão de uma transcrição é comparada com o baseline daquela mesma
música e rodada, isto é, sobre exatamente o mesmo texto de partida.

Definições (para uma métrica qualquer):

- ganho  = baseline - método, se menor é melhor (WER, CER);
           método - baseline, se maior é melhor (BERTScore).
  Ganho positivo sempre significa melhora.
- ganho por música = média do ganho nas rodadas da música. As músicas, e não as
  rodadas, são a unidade de análise: rodadas da mesma música não são independentes.
- intervalo de confiança = bootstrap percentil, reamostrando músicas.
- falha grave = avaliação (música × rodada) em que o método piora a métrica em mais
  que ``severe_failure_threshold`` em relação ao baseline.
- p-valor = teste de Wilcoxon (postos sinalizados) sobre os ganhos por música.
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

from ..config.schema import AnalysisConfig
from ..models import ExperimentResult
from .edits import analyze_edits
from .errors import analyze_errors

TIE_TOLERANCE = 1e-9
WORST_CASES = 3


def higher_is_better(metric: str) -> bool:
    return "score" in metric.lower()


def method_key(result: ExperimentResult) -> tuple[str, str, str]:
    return (
        result.refinement_provider or "",
        result.refinement_model or "",
        result.prompt_name or "",
    )


def _valid(result: ExperimentResult, metric: str) -> bool:
    return not result.error and result.metrics.get(metric) is not None


def _bootstrap_ci(
    values: np.ndarray, statistic, config: AnalysisConfig
) -> list[float] | None:
    """Intervalo percentil por bootstrap, reamostrando os elementos de ``values``."""
    if len(values) < 2:
        return None
    rng = np.random.default_rng(config.seed)
    idx = rng.integers(0, len(values), size=(config.bootstrap_samples, len(values)))
    estimates = statistic(values[idx], axis=1)
    alpha = (1.0 - config.confidence) / 2.0
    low, high = np.quantile(estimates, [alpha, 1.0 - alpha])
    return [float(low), float(high)]


def _ci_sign(ci: list[float] | None) -> int:
    """+1 se o intervalo está todo acima de zero, -1 se todo abaixo, 0 caso contrário."""
    if ci is None:
        return 0
    if ci[0] > 0:
        return 1
    if ci[1] < 0:
        return -1
    return 0


def _wilcoxon_p(gains: np.ndarray) -> float | None:
    nonzero = gains[np.abs(gains) > TIE_TOLERANCE]
    if len(nonzero) == 0:
        return None
    try:
        return float(scipy_stats.wilcoxon(nonzero).pvalue)
    except ValueError:
        return None


def _per_song(values: dict[tuple[str, int], float]) -> dict[str, list[float]]:
    by_song: dict[str, list[float]] = defaultdict(list)
    for (song_id, _run), value in values.items():
        by_song[song_id].append(value)
    return by_song


def distribution(values: np.ndarray) -> dict:
    """Média, desvio padrão, mínimo, quartis e máximo (sobre músicas)."""
    if len(values) == 0:
        return dict.fromkeys(("mean", "std", "min", "q1", "median", "q3", "max"))
    q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else None,
        "min": float(np.min(values)),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "max": float(np.max(values)),
    }


def _value_summary(values: dict[tuple[str, int], float]) -> dict:
    """Resumo de uma métrica sobre músicas: média, mediana, dispersão e ruído entre rodadas."""
    by_song = _per_song(values)
    song_means = np.array([np.mean(v) for v in by_song.values()])
    within = [np.std(v, ddof=1) for v in by_song.values() if len(v) >= 2]
    return {
        "num_songs": len(by_song),
        "num_evaluations": len(values),
        "mean": float(np.mean(song_means)) if len(song_means) else None,
        "median": float(np.median(song_means)) if len(song_means) else None,
        "std_between_songs": float(np.std(song_means, ddof=1)) if len(song_means) > 1 else None,
        "mean_std_between_runs": float(np.mean(within)) if within else None,
        "distribution": distribution(song_means),
    }


def _analyze_method(
    rows: list[ExperimentResult],
    metric: str,
    baseline: dict[tuple[str, int], float],
    higher: bool,
    config: AnalysisConfig,
) -> dict | None:
    values: dict[tuple[str, int], float] = {}
    gains: dict[tuple[str, int], float] = {}
    for r in rows:
        key = (r.song_id, r.run)
        if key not in baseline:
            continue
        value = r.metrics[metric]
        values[key] = value
        gains[key] = (value - baseline[key]) if higher else (baseline[key] - value)
    if not gains:
        return None

    song_gain = {s: float(np.mean(g)) for s, g in _per_song(gains).items()}
    song_gain_array = np.array(list(song_gain.values()))

    wins = int(np.sum(song_gain_array > TIE_TOLERANCE))
    losses = int(np.sum(song_gain_array < -TIE_TOLERANCE))
    severe = {k: g for k, g in gains.items() if g < -config.severe_failure_threshold}
    worst = sorted(gains.items(), key=lambda kv: kv[1])[:WORST_CASES]

    gain_mean_ci = _bootstrap_ci(song_gain_array, np.mean, config)
    gain_median_ci = _bootstrap_ci(song_gain_array, np.median, config)

    summary = _value_summary(values)
    summary.update({
        "gain_mean": float(np.mean(song_gain_array)),
        "gain_mean_ci": gain_mean_ci,
        "gain_mean_sig": _ci_sign(gain_mean_ci),
        "gain_median": float(np.median(song_gain_array)),
        "gain_median_ci": gain_median_ci,
        "gain_median_sig": _ci_sign(gain_median_ci),
        "gain_distribution": distribution(song_gain_array),
        "wins": wins,
        "ties": len(song_gain_array) - wins - losses,
        "losses": losses,
        "wilcoxon_p": _wilcoxon_p(song_gain_array),
        "severe_failures": len(severe),
        "severe_failure_rate": len(severe) / len(gains),
        "worst_cases": [
            {"song_id": song_id, "run": run, "gain": float(gain)}
            for (song_id, run), gain in worst
            if gain < -TIE_TOLERANCE
        ],
    })
    return summary


def _analyze_metric(
    results: list[ExperimentResult], metric: str, config: AnalysisConfig
) -> dict:
    higher = higher_is_better(metric)

    baseline = {
        (r.song_id, r.run): r.metrics[metric]
        for r in results
        if r.refinement_provider is None and _valid(r, metric)
    }

    by_method: dict[tuple[str, str, str], list[ExperimentResult]] = defaultdict(list)
    for r in results:
        if r.refinement_provider is not None and _valid(r, metric):
            by_method[method_key(r)].append(r)

    methods = []
    for (provider, model, prompt), rows in by_method.items():
        summary = _analyze_method(rows, metric, baseline, higher, config)
        if summary is None:
            continue
        methods.append({"provider": provider, "model": model, "prompt": prompt, **summary})

    methods.sort(key=lambda m: (m["gain_median"], m["gain_mean"]), reverse=True)

    return {
        "direction": "higher" if higher else "lower",
        "baseline": _value_summary(baseline),
        "methods": methods,
    }


def analyze(
    results: list[ExperimentResult], metric_names: list[str], config: AnalysisConfig
) -> dict:
    """Análise estatística pareada de cada método contra o baseline, por métrica."""
    return {
        "settings": {
            "bootstrap_samples": config.bootstrap_samples,
            "confidence": config.confidence,
            "severe_failure_threshold": config.severe_failure_threshold,
            "seed": config.seed,
            "length_ratio_min": config.length_ratio_min,
            "length_ratio_max": config.length_ratio_max,
            "max_change_fraction": config.max_change_fraction,
        },
        "num_songs": len({r.song_id for r in results}),
        "num_runs": max((r.run for r in results), default=0),
        "metrics": {m: _analyze_metric(results, m, config) for m in metric_names},
        "errors": analyze_errors(results, config),
        "verification": analyze_edits(results, config),
    }


def write_stats_json(analysis: dict, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
