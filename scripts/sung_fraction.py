"""Fração cantada de cada gravação (critério de inclusão, PROTOCOLO seção 3.2).

Estima a parte da duração em que há voz, a partir da faixa de voz isolada pelo demucs
(``*_vocals.wav``, gerada se não existir):

1. energia (RMS) em janelas de 50 ms, em dB;
2. janela com voz = energia acima de ``p95 - LIMIAR`` dB (relativo à própria faixa,
   porque o volume varia entre gravações);
3. suavização: filtro de mediana de 0,5 s; pausas menores que 1 s entre trechos com voz
   contam como canto (respiração, fim de verso); ilhas menores que 0,5 s são descartadas.

É uma estimativa: o demucs deixa vazar instrumentos para a faixa de voz em gravações
antigas, e coro e falas também contam como voz. O resultado é estável entre limiares de
15 e 25 dB (o script mostra os três), e a decisão de exclusão de casos-limite é
confirmada ouvindo a gravação.

Uso:
    uv run python scripts/sung_fraction.py data/inputs/*.mp3
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import binary_closing, binary_opening, median_filter

from benchmark.voice_isolation import isolate_voice

FRAME_S = 0.05
THRESHOLDS_DB = (15, 20, 25)
MAIN_THRESHOLD_DB = 20


def sung_fraction(vocals_path: Path, drop_db: float) -> tuple[float, float]:
    """(fração da duração com voz, duração em segundos)."""
    x, sr = sf.read(vocals_path, always_2d=True)
    x = x.mean(axis=1)
    n = int(sr * FRAME_S)
    m = len(x) // n
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1)) + 1e-10
    db = 20 * np.log10(rms)
    active = db > np.percentile(db, 95) - drop_db
    active = median_filter(active.astype(int), size=int(0.5 / FRAME_S)).astype(bool)
    active = binary_closing(active, structure=np.ones(int(1.0 / FRAME_S)))
    active = binary_opening(active, structure=np.ones(int(0.5 / FRAME_S)))
    return float(active.mean()), m * FRAME_S


def describe(values: np.ndarray) -> str:
    q1, q2, q3 = np.percentile(values, [25, 50, 75])
    return (
        f"média {values.mean():.1f} · dp {values.std(ddof=1):.1f} · mín {values.min():.1f} · "
        f"Q1 {q1:.1f} · mediana {q2:.1f} · Q3 {q3:.1f} · máx {values.max():.1f}"
    )


def main(paths: list[str]) -> None:
    rows = []
    for p in sorted(paths):
        path = Path(p)
        if path.stem.endswith("_vocals") or path.suffix.lower() != ".mp3":
            continue
        vocals = isolate_voice(path)
        fractions = {d: sung_fraction(vocals, d)[0] * 100 for d in THRESHOLDS_DB}
        rows.append((path.stem, fractions, sung_fraction(vocals, MAIN_THRESHOLD_DB)[1]))

    if not rows:
        sys.exit("Nenhum .mp3 informado.")
    print("fração cantada (%), limiar 20 dB [15–25 dB], duração, gravação")
    for name, f, dur in sorted(rows, key=lambda r: r[1][MAIN_THRESHOLD_DB]):
        lo, hi = f[THRESHOLDS_DB[0]], f[THRESHOLDS_DB[-1]]
        print(f"{f[MAIN_THRESHOLD_DB]:5.1f}  [{lo:4.1f}–{hi:4.1f}]  {dur:4.0f}s  {name}")
    if len(rows) > 1:
        for d in THRESHOLDS_DB:
            print(f"\nlimiar {d} dB: " + describe(np.array([r[1][d] for r in rows])), end="")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
