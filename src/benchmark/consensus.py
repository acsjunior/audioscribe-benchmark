"""Transcrição de consenso: a mais parecida com as demais entre as rodadas.

Dadas as ``n`` transcrições independentes de uma música, escolhe-se o **medoide**: a
transcrição com a menor soma de distâncias de edição (em palavras, texto normalizado)
para todas as outras. É uma escolha, não uma fusão — o texto final é sempre uma das
transcrições originais, então não inventa palavras. Não usa a letra de referência nem
chamadas de API.

Por que ajuda: os erros do modelo variam de uma rodada para outra (trechos pulados ou
inventados em uma rodada e não em outra); a transcrição "central" tende a evitar os
extremos. Com ``n < 3`` não há centro (com 2 a escolha seria arbitrária).
"""

from jiwer import process_words

from .metrics.base import normalize

MIN_RUNS = 3


def edit_distance(a: str, b: str) -> int:
    """Distância de edição em palavras entre dois textos, após normalização."""
    wa, wb = normalize(a), normalize(b)
    if not wa:
        return len(wb.split())
    if not wb:
        return len(wa.split())
    out = process_words(wa, wb)
    return out.substitutions + out.deletions + out.insertions


def medoid(texts: dict[int, str]) -> int:
    """Rodada cuja transcrição tem a menor soma de distâncias para as demais.

    Empates são resolvidos pela menor rodada, para o resultado ser determinístico.
    """
    if len(texts) < MIN_RUNS:
        raise ValueError(f"Consenso exige ao menos {MIN_RUNS} transcrições, recebeu {len(texts)}")
    runs = sorted(texts)
    totals = {
        r: sum(edit_distance(texts[r], texts[o]) for o in runs if o != r) for r in runs
    }
    return min(runs, key=lambda r: (totals[r], r))
