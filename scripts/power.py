"""Simulação de poder: quantas músicas o conjunto de teste precisa (PROTOCOLO 3.3/7.3).

Poder = probabilidade de o teste detectar um efeito que existe. A simulação:

1. pega os ganhos por música (WER) de métodos já medidos, num ``results.json``;
2. separa os **empates exatos** (músicas em que o método não mudou nada) dos demais;
   a fração de empates observada é mantida — empates não carregam evidência e reduzem
   o poder, então deslocá-los junto com o resto superestimaria o poder;
3. **centra** os ganhos não nulos de cada método no próprio ganho típico
   (Hodges–Lehmann), ficando só com o *formato* (assimetria, falhas catastróficas,
   dispersão), e junta os métodos num único conjunto de "ruído";
4. para cada cenário δ, cada música simulada é empate com a probabilidade observada ou,
   senão, um valor do ruído somado a δ — δ é o **ganho típico entre as músicas que o
   método altera** (modelo de deslocamento de posição, o que fundamenta o Wilcoxon);
5. para cada número de músicas N, sorteia muitas amostras e conta em que fração delas o
   critério é atingido.

Critérios simulados (PROTOCOLO 7.3):

- ``H1``: Wilcoxon-Pratt bilateral com p < 0,05 (o IC de Hodges–Lehmann acima de zero
  acompanha de perto esse critério e não é simulado, por custo);
- ``H1+falhas``: o anterior e, além disso, no máximo ``--max-severe`` das músicas com
  piora maior que ``--severe`` (aproximação por música do critério de falhas graves);
- ``H2/H3``: p < 0,025 — o pior caso de Holm entre duas hipóteses depois de H1 (assume
  o mesmo δ para elas, o que é otimista se a diferença entre variantes for menor).

Limitações: o ruído vem de rodadas únicas da fase exploratória; com várias rodadas por
música o ruído cai e o poder real tende a ser maior (a simulação é conservadora nisso).
O formato da distribuição da conferência com áudio pode ser outro: rodar de novo com os
ganhos do E7 no dev antes de fechar o tamanho do teste.

Uso:
    uv run python scripts/power.py results/<execução>/results.json
    uv run python scripts/power.py results.json --methods "openai/gpt-4o [minimalist]" \\
        --effects 0.01 0.02 0.04 --sizes 30 40 60 80 --sims 4000 \\
        --exclude-songs alcides-gerardi-antonico
"""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

from benchmark.reporting.json_reporter import read_json
from benchmark.reporting.stats import TIE_TOLERANCE, hodges_lehmann


def song_gains(
    path: Path, methods: list[str] | None, exclude: set[str]
) -> dict[str, np.ndarray]:
    results = read_json(path)
    baseline = {
        (r.song_id, r.run): r.metrics["wer"]
        for r in results
        if r.refinement_provider is None and not r.error and r.metrics.get("wer") is not None
    }
    by_method: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.refinement_provider is None or r.error or r.metrics.get("wer") is None:
            continue
        label = r.experiment_label
        if methods and label not in methods:
            continue
        key = (r.song_id, r.run)
        if key in baseline and r.song_id not in exclude:
            by_method[label][r.song_id].append(baseline[key] - r.metrics["wer"])
    if not by_method:
        raise SystemExit("Nenhum método com ganho pareado encontrado.")
    return {m: np.array([np.mean(v) for v in songs.values()]) for m, songs in by_method.items()}


def wilcoxon_p(gains: np.ndarray) -> float:
    gains = np.where(np.abs(gains) > TIE_TOLERANCE, gains, 0.0)
    if not np.any(gains):
        return 1.0
    return float(scipy_stats.wilcoxon(gains, zero_method="pratt").pvalue)


def simulate(
    noise: np.ndarray, tie_rate: float, effect: float, n: int, sims: int, args, rng
) -> dict:
    hits = {"H1": 0, "H1+falhas": 0, "H2/H3": 0}
    for _ in range(sims):
        sample = rng.choice(noise, size=n, replace=True) + effect
        sample[rng.random(n) < tie_rate] = 0.0
        p = wilcoxon_p(sample)
        if p < 0.05:
            hits["H1"] += 1
            if np.mean(sample < -args.severe) <= args.max_severe:
                hits["H1+falhas"] += 1
        if p < 0.025:
            hits["H2/H3"] += 1
    return {k: v / sims for k, v in hits.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results_json", type=Path)
    parser.add_argument("--methods", nargs="*", help="rótulos dos métodos (padrão: todos)")
    parser.add_argument("--effects", nargs="+", type=float, default=[0.01, 0.02, 0.04])
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[20, 30, 40, 50, 60, 80, 100, 120])
    parser.add_argument("--sims", type=int, default=4000)
    parser.add_argument("--severe", type=float, default=0.2)
    parser.add_argument("--max-severe", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--exclude-songs", nargs="*", default=[],
                        help="músicas fora do formato (ex.: falhas já tratadas como erro)")
    args = parser.parse_args()

    gains = song_gains(args.results_json, args.methods, set(args.exclude_songs))
    all_gains = np.concatenate(list(gains.values()))
    tie_rate = float(np.mean(np.abs(all_gains) <= TIE_TOLERANCE))
    nonzero = [g[np.abs(g) > TIE_TOLERANCE] for g in gains.values()]
    noise = np.concatenate([g - hodges_lehmann(g) for g in nonzero if len(g)])
    if args.exclude_songs:
        print(f"Músicas excluídas do formato: {', '.join(args.exclude_songs)}")
    print("Métodos usados como formato da distribuição:")
    for m, g in gains.items():
        print(f"  {m}: {len(g)} músicas, HL {hodges_lehmann(g):+.4f}")
    q = np.percentile(noise, [0, 25, 50, 75, 100])
    print(f"Ruído centrado ({len(noise)} valores): dp {noise.std(ddof=1):.3f} · "
          f"mín {q[0]:+.3f} · Q1 {q[1]:+.3f} · mediana {q[2]:+.3f} · Q3 {q[3]:+.3f} · "
          f"máx {q[4]:+.3f}")
    print(f"Empates exatos mantidos: {tie_rate:.0%} das músicas")
    print(f"Falhas graves (< −{args.severe}) no ruído: {np.mean(noise < -args.severe):.1%} "
          f"dos valores não nulos\n")

    rng = np.random.default_rng(args.seed)
    for effect in args.effects:
        print(f"Efeito típico δ = {effect:+.3f}")
        print(f"  {'músicas':>7}  {'H1':>6}  {'H1+falhas':>9}  {'H2/H3':>6}")
        for n in args.sizes:
            r = simulate(noise, tie_rate, effect, n, args.sims, args, rng)
            print(f"  {n:>7}  {r['H1']:>6.0%}  {r['H1+falhas']:>9.0%}  {r['H2/H3']:>6.0%}")
        print()


if __name__ == "__main__":
    main()
