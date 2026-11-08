"""Diagnóstico de tipos de erro das transcrições.

O WER sozinho não diz *como* a transcrição errou. Aqui cada avaliação (música × rodada
× método) é decomposta, sobre as palavras normalizadas, em:

- substituições: palavra trocada por outra;
- omissões: palavra da letra que não aparece na transcrição;
- inserções: palavra na transcrição que não existe na letra.

As taxas são divididas pelo número de palavras da letra, de modo que
``substituições + omissões + inserções = WER``. A **razão de comprimento** (palavras da
transcrição / palavras da letra) indica trechos pulados (< 1) ou inventados/repetidos (> 1).

Alertas (por avaliação):

- ``wer_zero``: WER exatamente 0, improvável em gravações antigas (78 rpm); pode indicar
  letra copiada, memorização do modelo ou erro na referência;
- ``curta``: razão de comprimento abaixo de ``length_ratio_min`` (trechos omitidos);
- ``longa``: razão de comprimento acima de ``length_ratio_max`` (trechos inventados ou
  repetidos).
"""

from collections import defaultdict

import numpy as np
from jiwer import process_words

from ..config.schema import AnalysisConfig
from ..metrics.base import normalize
from ..models import ExperimentResult

MAX_FLAGGED = 10


def diagnose(hypothesis: str, reference: str) -> dict | None:
    """Decompõe o erro de uma transcrição. Retorna None se a letra não tiver palavras."""
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    n_ref = len(ref.split())
    n_hyp = len(hyp.split())
    if n_ref == 0:
        return None
    if n_hyp == 0:
        subs, dels, ins = 0, n_ref, 0
    else:
        out = process_words(ref, hyp)
        subs, dels, ins = out.substitutions, out.deletions, out.insertions
    return {
        "n_ref": n_ref,
        "n_hyp": n_hyp,
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "sub_rate": subs / n_ref,
        "del_rate": dels / n_ref,
        "ins_rate": ins / n_ref,
        "wer": (subs + dels + ins) / n_ref,
        "length_ratio": n_hyp / n_ref,
    }


def flags_for(diag: dict, config: AnalysisConfig) -> list[str]:
    flags = []
    if diag["wer"] == 0:
        flags.append("wer_zero")
    if diag["length_ratio"] < config.length_ratio_min:
        flags.append("curta")
    if diag["length_ratio"] > config.length_ratio_max:
        flags.append("longa")
    return flags


def _summary(rows: list[tuple[ExperimentResult, dict, list[str]]]) -> dict:
    # A unidade de análise é a música: média das rodadas, depois média das músicas.
    by_song: dict[str, list[dict]] = defaultdict(list)
    for result, diag, _ in rows:
        by_song[result.song_id].append(diag)

    def song_means(key: str) -> np.ndarray:
        return np.array([np.mean([d[key] for d in diags]) for diags in by_song.values()])

    flagged = [
        {
            "song_id": r.song_id,
            "run": r.run,
            "flags": flags,
            "wer": d["wer"],
            "length_ratio": d["length_ratio"],
            "sub_rate": d["sub_rate"],
            "del_rate": d["del_rate"],
            "ins_rate": d["ins_rate"],
        }
        for r, d, flags in rows
        if flags
    ]
    flagged.sort(key=lambda f: abs(f["length_ratio"] - 1.0), reverse=True)
    counts = {
        flag: sum(1 for _, _, flags in rows if flag in flags)
        for flag in ("wer_zero", "curta", "longa")
    }
    return {
        "num_songs": len(by_song),
        "num_evaluations": len(rows),
        "sub_rate": float(np.mean(song_means("sub_rate"))),
        "del_rate": float(np.mean(song_means("del_rate"))),
        "ins_rate": float(np.mean(song_means("ins_rate"))),
        "length_ratio_median": float(np.median(song_means("length_ratio"))),
        "alerts": counts,
        "flagged": flagged[:MAX_FLAGGED],
    }


def analyze_errors(results: list[ExperimentResult], config: AnalysisConfig) -> dict:
    """Diagnóstico de erros por método (o baseline aparece como método sem provedor)."""
    groups: dict[tuple[str, str, str], list[tuple[ExperimentResult, dict, list[str]]]] = (
        defaultdict(list)
    )
    for r in results:
        if r.error:
            continue
        diag = diagnose(r.evaluated_transcription, r.ground_truth)
        if diag is None:
            continue
        key = (r.refinement_provider or "", r.refinement_model or "", r.prompt_name or "")
        groups[key].append((r, diag, flags_for(diag, config)))

    methods = []
    for (provider, model, prompt), rows in groups.items():
        methods.append({"provider": provider, "model": model, "prompt": prompt, **_summary(rows)})
    # baseline primeiro, depois os métodos por nome
    methods.sort(key=lambda m: (m["provider"] != "", m["provider"], m["model"], m["prompt"]))
    return {
        "length_ratio_min": config.length_ratio_min,
        "length_ratio_max": config.length_ratio_max,
        "methods": methods,
    }
