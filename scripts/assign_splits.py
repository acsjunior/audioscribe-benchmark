"""Atribui dev/teste na ordem de amostragem a partir da conferência (PROTOCOLO, seção 3.3).

Lê a lista de conferência (``status`` = incluida | excluida, vazio = ainda não conferida)
e preenche ``split``: as primeiras ``--dev-size`` incluídas, na ordem, são o dev; as
incluídas seguintes, o teste. Uma excluída é reposta automaticamente pela próxima da
lista. A atribuição para na primeira música ainda não conferida.

Uso:
    uv run python scripts/assign_splits.py data/candidatas/ordem_amostragem.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from benchmark.sampling import DEV_SIZE, TEST_TARGET, assign_splits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("order_csv", type=Path)
    parser.add_argument("--dev-size", type=int, default=DEV_SIZE)
    parser.add_argument("-o", "--output", type=Path, help="padrão: sobrescreve a entrada")
    args = parser.parse_args()

    order = pd.read_csv(args.order_csv, dtype=str).fillna("")
    order["posicao"] = order["posicao"].astype(int)
    out = assign_splits(order, dev_size=args.dev_size)
    out.to_csv(args.output or args.order_csv, index=False)

    status = out["status"]
    conferred = int((status != "").astype(int).cumprod().sum())
    n_dev = int((out["split"] == "dev").sum())
    n_test = int((out["split"] == "test").sum())
    print(f"Conferidas em sequência: {conferred} de {len(out)} posições")
    n_in, n_out = int((status == "incluida").sum()), int((status == "excluida").sum())
    print(f"Incluídas: {n_in} · excluídas: {n_out}")
    print(f"Dev: {n_dev}/{args.dev_size} · teste: {n_test} (meta {TEST_TARGET})")


if __name__ == "__main__":
    main()
