"""Hipóteses confirmatórias: contrastes pré-registrados, testados em sequência fixa.

As hipóteses do estudo (PROTOCOLO, seção 2) comparam pares de métodos que podem estar
em execuções diferentes (ex.: conferência vs. transcrição direta do E6, que usa outro
transcritor). Cada contraste é declarado num YAML, antes de rodar o teste:

    alpha: 0.05
    metric: wer
    failures: exclude          # exclude | draft (análise de sensibilidade)
    contrasts:
      - name: H1
        reference: {results: results/teste_.../results.json, method: baseline}
        treatment: {results: results/teste_.../results.json, method: "verify:..."}
      - name: H2
        after: H1              # só é testada se H1 for rejeitada
        reference: {...}
        treatment: {...}

``method`` é o rótulo do método como aparece no relatório (``ExperimentResult.
experiment_label``), ou ``baseline``.

**Pareamento**: por música (média das rodadas de cada lado), sobre as músicas presentes
nos dois lados. **Ganho** positivo = o tratamento é melhor.

**Procedimento de sequência fixa (gatekeeping)**: os contrastes sem ``after`` formam a
primeira família; os que têm ``after: X`` formam uma família testada só se X for
rejeitado. Dentro de cada família, Holm a ``alpha``. Isso controla a taxa de erro do
conjunto e dá à pergunta principal o ``alpha`` inteiro.

**Falhas** (avaliação com erro, ex.: bloqueio): ``exclude`` as descarta; ``draft`` as
substitui pelo valor do baseline da mesma música e rodada no mesmo arquivo (o método
"devolveria o rascunho"), como análise de sensibilidade.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, Field, model_validator

from ..config.schema import AnalysisConfig
from ..models import ExperimentResult
from .errors import diagnose
from .json_reporter import read_json
from .stats import (
    TIE_TOLERANCE,
    _bootstrap_ci,
    _ci_sign,
    _corpus_gain,
    adjust_holm,
    distribution,
    higher_is_better,
    hodges_lehmann,
    sign_test_p,
    wilcoxon_p,
)

BASELINE = "baseline"


class Side(BaseModel):
    results: str
    method: str


class Contrast(BaseModel):
    name: str
    reference: Side
    treatment: Side
    after: str | None = None


class ContrastsConfig(BaseModel):
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    metric: str = "wer"
    failures: Literal["exclude", "draft"] = "exclude"
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    contrasts: list[Contrast]

    @model_validator(mode="after")
    def _check_gates(self) -> "ContrastsConfig":
        names = [c.name for c in self.contrasts]
        if len(set(names)) != len(names):
            raise ValueError("nomes de contrastes repetidos")
        roots = {c.name for c in self.contrasts if c.after is None}
        if not roots:
            raise ValueError("é preciso ao menos um contraste sem 'after'")
        for c in self.contrasts:
            if c.after is not None and c.after not in roots:
                raise ValueError(
                    f"{c.name}: 'after' deve apontar para um contraste da primeira família"
                )
        return self


def load_contrasts(path: Path) -> ContrastsConfig:
    with open(path, encoding="utf-8") as f:
        return ContrastsConfig(**yaml.safe_load(f))


def _label(result: ExperimentResult) -> str:
    return BASELINE if result.refinement_provider is None else result.experiment_label


def _song_values(
    results: list[ExperimentResult], method: str, metric: str, failures: str
) -> tuple[dict[str, float], dict[str, tuple[float, float]], int, int]:
    """Por música: valor médio da métrica e (erros, palavras) médios; falhas e avaliações."""
    baseline = {
        (r.song_id, r.run): r
        for r in results
        if r.refinement_provider is None and not r.error and r.metrics.get(metric) is not None
    }
    rows = [r for r in results if _label(r) == method]
    if not rows:
        labels = sorted({_label(r) for r in results})
        raise ValueError(f"método '{method}' não encontrado. Disponíveis: {labels}")

    values: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, list[tuple[float, float]]] = defaultdict(list)
    failed = 0
    for r in rows:
        source = r
        if r.error or r.metrics.get(metric) is None:
            failed += 1
            if failures != "draft" or (r.song_id, r.run) not in baseline:
                continue
            source = baseline[(r.song_id, r.run)]
        values[r.song_id].append(source.metrics[metric])
        d = diagnose(source.evaluated_transcription, source.ground_truth)
        if d is not None:
            errors[r.song_id].append(
                (d["substitutions"] + d["deletions"] + d["insertions"], d["n_ref"])
            )
    song_values = {s: float(np.mean(v)) for s, v in values.items()}
    song_errors = {s: tuple(np.mean(v, axis=0)) for s, v in errors.items()}
    return song_values, song_errors, failed, len(rows)


def _evaluate(contrast: Contrast, config: ContrastsConfig, cache: dict) -> dict:
    def load(path: str) -> list[ExperimentResult]:
        if path not in cache:
            cache[path] = read_json(Path(path))
        return cache[path]

    metric = config.metric
    ref_v, ref_e, _, _ = _song_values(
        load(contrast.reference.results), contrast.reference.method, metric, config.failures
    )
    trt_v, trt_e, failed, total = _song_values(
        load(contrast.treatment.results), contrast.treatment.method, metric, config.failures
    )
    songs = sorted(set(ref_v) & set(trt_v))
    if not songs:
        raise ValueError(f"{contrast.name}: nenhuma música em comum entre os dois lados")

    sign = 1.0 if higher_is_better(metric) else -1.0
    gains = np.array([sign * (trt_v[s] - ref_v[s]) for s in songs])
    acfg = config.analysis
    wins = int(np.sum(gains > TIE_TOLERANCE))
    losses = int(np.sum(gains < -TIE_TOLERANCE))
    hl_ci = _bootstrap_ci(gains, hodges_lehmann, acfg)

    corpus = None
    if metric == "wer":
        common = [s for s in songs if s in ref_e and s in trt_e]
        corpus = _corpus_gain(
            {s: (ref_e[s][0], trt_e[s][0], ref_e[s][1]) for s in common}, acfg
        )

    return {
        "name": contrast.name,
        "after": contrast.after,
        "reference": contrast.reference.model_dump(),
        "treatment": contrast.treatment.model_dump(),
        "num_songs": len(songs),
        "treatment_failures": failed,
        "treatment_failure_rate": failed / total if total else 0.0,
        "gain_hl": hodges_lehmann(gains),
        "gain_hl_ci": hl_ci,
        "ci_excludes_zero": _ci_sign(hl_ci) == 1,
        "gain_median": float(np.median(gains)),
        "gain_mean": float(np.mean(gains)),
        "gain_distribution": distribution(gains),
        "wins": wins,
        "ties": len(gains) - wins - losses,
        "losses": losses,
        "songs_with_severe_loss": int(np.sum(gains < -acfg.severe_failure_threshold)),
        "wilcoxon_p": wilcoxon_p(gains),
        "sign_test_p": sign_test_p(wins, losses),
        "corpus": corpus,
    }


def _holm_family(rows: list[dict], alpha: float) -> None:
    adjusted = adjust_holm([r["wilcoxon_p"] for r in rows])
    for r, p in zip(rows, adjusted, strict=True):
        r["wilcoxon_p_adjusted"] = p
        r["rejected"] = p is not None and p < alpha


def run_contrasts(config: ContrastsConfig) -> dict:
    cache: dict = {}
    roots = [_evaluate(c, config, cache) for c in config.contrasts if c.after is None]
    for r in roots:
        r["tested"] = True
    _holm_family(roots, config.alpha)
    rejected = {r["name"] for r in roots if r["rejected"]}

    by_parent: dict[str, list[Contrast]] = defaultdict(list)
    for c in config.contrasts:
        if c.after is not None:
            by_parent[c.after].append(c)

    children: list[dict] = []
    for parent, family in by_parent.items():
        rows = [_evaluate(c, config, cache) for c in family]
        if parent in rejected:
            for r in rows:
                r["tested"] = True
            _holm_family(rows, config.alpha)
        else:
            # Portão fechado: a família é relatada, mas não testada.
            for r in rows:
                r.update(tested=False, rejected=False, wilcoxon_p_adjusted=None)
        children.extend(rows)

    return {
        "alpha": config.alpha,
        "metric": config.metric,
        "failures": config.failures,
        "procedure": "sequência fixa; Holm dentro de cada família; Wilcoxon-Pratt bilateral",
        "contrasts": roots + children,
    }


def write_contrasts_json(result: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
