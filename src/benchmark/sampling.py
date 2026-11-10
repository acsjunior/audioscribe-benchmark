"""Amostragem das músicas do estudo (PROTOCOLO, seção 3.3).

A partir do catálogo de candidatas extraído da Discografia Brasileira:

1. **população**: gênero exatamente "Samba", gravações de ``YEAR_MIN`` a ``YEAR_MAX``;
2. **uma gravação por composição**: gravações da mesma composição (mesmo título, sem
   subtítulos entre parênteses, e mesma autoria, em qualquer ordem, após normalização)
   são agrupadas e uma delas é sorteada;
3. **ordem aleatória estratificada por década, balanceada**: a cada posição entra a
   década mais atrasada em relação à sua proporção na população (empates sorteados), e
   dentro de cada década a ordem é aleatória. Em qualquer ponto em que a conferência
   pare, as décadas estão na proporção da população; intérpretes e autores ficam
   proporcionais pelo sorteio, sem limites;
4. **dev e teste**: na conferência, cada música é marcada ``incluida`` ou ``excluida``
   (``status``). As primeiras ``DEV_SIZE`` incluídas, na ordem, são o dev; as incluídas
   seguintes, o teste (``assign_splits``). Uma excluída é reposta pela próxima da lista,
   sem escolha manual.

Decisões manuais tomadas **antes** do sorteio, só com os metadados do catálogo, ficam num
arquivo de revisão (``data_id``, ``acao``, ``valor``, ``observacao``), versionado:

- ``acao = instrumental``: gravação sem canto (orquestra, solista instrumental); sai da
  população, que é de gravações cantadas;
- ``acao = composicao``: força a chave de composição (``valor``), para juntar gravações
  da mesma composição que a normalização automática não reconheceu, ou separá-las.

A heurística ``probably_instrumental`` só sugere candidatas a essa revisão. As demais
exclusões (letra, trechos duvidosos, autoria) são decididas na conferência, seguindo a
ordem, e registradas no próprio arquivo de saída.
"""

import re
import unicodedata

import numpy as np
import pandas as pd

YEAR_MIN = 1928
YEAR_MAX = 1955
GENRE = "Samba"
DEV_SIZE = 40
TEST_TARGET = 120  # meta, não limite: entram todas as incluídas conferidas
STATUSES = {"incluida", "excluida", ""}

# Intérprete que parece só instrumental (banda, orquestra, grupo...). Apenas sinaliza.
_INSTRUMENTAL = re.compile(
    r"^(banda|orquestra|grupo|jazz|bloco|conjunto|coro|choro|regional|violão|clarinete|"
    r"piano|trombone|turma|bando|gente do|zaccarias|carioca e|muraro|milionários|totó|"
    r"passos e|radamés|simão|vero|os )|orquestra|jazz band|ritmo$|regional$",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def composition_key(title: str, authors: str) -> str:
    """Título sem subtítulos entre parênteses + autores em ordem alfabética."""
    base = _plain(re.sub(r"\(.*?\)", "", title))
    names = sorted(_plain(a) for a in authors.split(" / ") if a.strip())
    return f"{base}|{' / '.join(names)}"


def probably_instrumental(performers: str) -> bool:
    parts = [p.strip() for p in performers.split(" / ") if p.strip()]
    return not parts or all(_INSTRUMENTAL.search(p) for p in parts)


def load_candidates(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    df["ano"] = pd.to_numeric(df["ano_disco"].str.slice(0, 4), errors="coerce")
    return df


def load_review(path) -> pd.DataFrame:
    review = pd.read_csv(path, dtype=str).fillna("")
    if "confirmado" in review.columns:  # só valem as decisões confirmadas
        review = review[review["confirmado"].str.strip().str.lower().isin({"sim", "s", "x"})]
    unknown = set(review["acao"]) - {"instrumental", "composicao", ""}
    if unknown:
        raise ValueError(f"Ação desconhecida no arquivo de revisão: {sorted(unknown)}")
    return review


def population(df: pd.DataFrame, review: pd.DataFrame | None = None) -> pd.DataFrame:
    mask = (
        (df["genero"].str.strip() == GENRE)
        & (df["ano"] >= YEAR_MIN)
        & (df["ano"] <= YEAR_MAX)
    )
    pop = df[mask].copy()
    pop["decada"] = (pop["ano"] // 10 * 10).astype(int)
    pop["composicao"] = [
        composition_key(t, a) for t, a in zip(pop["titulo"], pop["autor"], strict=True)
    ]
    pop["provavel_instrumental"] = pop["interprete"].map(probably_instrumental)
    if review is not None:
        instrumental = set(review.loc[review["acao"] == "instrumental", "data_id"])
        pop = pop[~pop["data_id"].isin(instrumental)]
        forced = review[review["acao"] == "composicao"].set_index("data_id")["valor"]
        pop["composicao"] = [
            forced.get(i, key) for i, key in zip(pop["data_id"], pop["composicao"], strict=True)
        ]
    return pop.reset_index(drop=True)


def one_per_composition(pop: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Sorteia uma gravação por composição e registra as demais."""
    rows = []
    for key in sorted(pop["composicao"].unique()):
        group = pop[pop["composicao"] == key].sort_values("data_id")
        chosen = group.iloc[int(rng.integers(len(group)))].copy()
        others = group[group["data_id"] != chosen["data_id"]]
        chosen["n_gravacoes_composicao"] = len(group)
        chosen["outras_gravacoes"] = "; ".join(
            f"{r.interprete} {int(r.ano)} [{r.data_id}]" for r in others.itertuples()
        )
        rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True)


def balanced_order(strata: pd.Series, rng: np.random.Generator) -> list[int]:
    """Índices em ordem aleatória, balanceada para manter a proporção de cada estrato.

    A cada posição i escolhe o estrato com maior déficit ``i * p_s - escolhidos_s``
    (empates sorteados); dentro de cada estrato, a ordem é uma permutação aleatória.
    """
    groups = {s: list(rng.permutation(idx)) for s, idx in strata.groupby(strata).groups.items()}
    total = len(strata)
    share = {s: len(v) / total for s, v in groups.items()}
    taken = dict.fromkeys(groups, 0)
    order: list[int] = []
    for i in range(1, total + 1):
        available = [s for s in groups if groups[s]]
        deficit = {s: i * share[s] - taken[s] for s in available}
        best = max(deficit.values())
        candidates = sorted(s for s in available if deficit[s] >= best - 1e-12)
        s = candidates[int(rng.integers(len(candidates)))]
        order.append(int(groups[s].pop(0)))
        taken[s] += 1
    return order


def sampling_order(
    df: pd.DataFrame, seed: int, review: pd.DataFrame | None = None
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pool = one_per_composition(population(df, review), rng)
    pool = pool.iloc[balanced_order(pool["decada"], rng)].reset_index(drop=True)
    pool.insert(0, "posicao", range(1, len(pool) + 1))
    pool.insert(1, "split", "")  # preenchido por assign_splits a partir de status
    pool["status"] = ""  # incluida | excluida (preenchido na conferência)
    pool["motivo_exclusao"] = ""
    columns = [
        "posicao", "split", "decada", "ano", "data_id", "titulo", "autor", "interprete",
        "acompanhamento", "disco", "genero", "provavel_instrumental",
        "n_gravacoes_composicao", "outras_gravacoes", "fonte_url", "audio_url",
        "status", "motivo_exclusao",
    ]
    pool["ano"] = pool["ano"].astype(int)
    return pool[columns]


def assign_splits(order: pd.DataFrame, dev_size: int = DEV_SIZE) -> pd.DataFrame:
    """Preenche ``split`` a partir de ``status``, seguindo a ordem da lista.

    As primeiras ``dev_size`` músicas incluídas são ``dev`` e as incluídas seguintes são
    ``test``; excluídas ficam sem split. A atribuição para na primeira música ainda não
    conferida (``status`` vazio): o split de uma música só é definido quando todas as
    anteriores já foram conferidas, para que nenhuma decisão posterior o altere.
    """
    out = order.sort_values("posicao").reset_index(drop=True).copy()
    status = out["status"].fillna("").str.strip().str.lower()
    unknown = set(status) - STATUSES
    if unknown:
        raise ValueError(f"Status desconhecido: {sorted(unknown)} (use incluida ou excluida)")
    splits, included = [], 0
    pending = False
    for value in status:
        pending = pending or value == ""
        if pending or value == "excluida":
            splits.append("")
            continue
        splits.append("dev" if included < dev_size else "test")
        included += 1
    out["status"] = status
    out["split"] = splits
    return out
