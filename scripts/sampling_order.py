"""Gera a ordem de conferência das músicas (PROTOCOLO, seção 3.3).

Lê o catálogo de candidatas extraído da Discografia Brasileira (db-scraper), aplica a
população do estudo (gênero "Samba", 1928–1955), sorteia uma gravação por composição e
ordena as composições em ordem aleatória estratificada e balanceada por década. O split
(dev/teste) não é definido aqui: depende da conferência (ver ``assign_splits.py``).

Uso:
    uv run python scripts/sampling_order.py \\
        data/candidatas/discografia_samba_dp_2026-11-10.csv \\
        data/candidatas/ordem_amostragem.csv --seed 20261110 \\
        --review data/candidatas/revisao_populacao.csv
"""

import argparse
from pathlib import Path

from benchmark.sampling import (
    load_candidates,
    load_review,
    population,
    sampling_order,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("candidates_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--review", type=Path, help="decisões manuais (instrumental, composição)")
    args = parser.parse_args()

    df = load_candidates(args.candidates_csv)
    review = load_review(args.review) if args.review else None
    pop = population(df, review)
    order = sampling_order(df, seed=args.seed, review=review)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    order.to_csv(args.output_csv, index=False)

    print(f"Candidatas: {len(df)} · população (Samba, 1928–1955, cantadas): {len(pop)} gravações")
    print(f"Composições (uma gravação sorteada por composição): {len(order)}")
    share = order["decada"].value_counts(normalize=True).sort_index()
    print("Proporção por década: " + ", ".join(f"{d}s {p:.1%}" for d, p in share.items()))
    print(f"Salvo em: {args.output_csv}")


if __name__ == "__main__":
    main()
