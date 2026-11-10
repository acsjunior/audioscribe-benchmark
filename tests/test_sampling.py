import numpy as np
import pandas as pd
import pytest

from benchmark.sampling import (
    balanced_order,
    composition_key,
    load_review,
    population,
    probably_instrumental,
    sampling_order,
)


def _df(rows):
    df = pd.DataFrame(rows, columns=["data_id", "titulo", "autor", "interprete", "genero", "ano"])
    for col in ["acompanhamento", "disco", "fonte_url", "audio_url"]:
        df[col] = ""
    df["ano_disco"] = df["ano"].astype(str)
    df["ano"] = df["ano"].astype(float)
    return df


def test_composition_key_ignores_subtitle_accents_and_author_order():
    a = composition_key("Fala Meu Louro (Papagaio Louro)", "Sinhô")
    assert a == composition_key("FALA MEU LOURO", "Sinho")
    b = composition_key("Saramba", "Duque / J. Thomaz")
    assert composition_key("Sarambá", "J. Thomaz / Duque") == b
    assert composition_key("Golpe Errado", "Francisco Alves") != composition_key(
        "Golpe Errado", "Francisco Matoso"
    )


def test_probably_instrumental():
    assert probably_instrumental("Orquestra Pan American")
    assert probably_instrumental("")
    assert not probably_instrumental("Francisco Alves")
    assert not probably_instrumental("Aracy de Almeida / Trio Melodia")


def test_population_filters_genre_and_years():
    df = _df([
        ["1", "A", "x", "Cantor", "Samba", 1930],
        ["2", "B", "x", "Cantor", "Samba Canção", 1930],
        ["3", "C", "x", "Cantor", "Samba", 1927],
        ["4", "D", "x", "Cantor", "Samba", 1956],
        ["5", "E", "x", "Cantor", " Samba ", 1955],
    ])
    assert list(population(df)["data_id"]) == ["1", "5"]


def test_review_removes_instrumentals_and_forces_composition(tmp_path):
    df = _df([
        ["1", "Linda Flor", "Vogeler", "Cantor", "Samba", 1930],
        ["2", "Linda Flor - Ai Ioiô", "Vogeler", "Cantora", "Samba", 1950],
        ["3", "Danúbio", "Strauss", "Orquestra X", "Samba", 1947],
        ["4", "Outra", "Y", "Cantor", "Samba", 1931],
    ])
    path = tmp_path / "rev.csv"
    pd.DataFrame([
        {"data_id": "3", "acao": "instrumental", "valor": "", "confirmado": "sim"},
        {"data_id": "2", "acao": "composicao", "valor": "linda flor|vogeler", "confirmado": "sim"},
        {"data_id": "4", "acao": "instrumental", "valor": "", "confirmado": ""},  # não confirmada
    ]).to_csv(path, index=False)
    pop = population(df, load_review(path))
    assert set(pop["data_id"]) == {"1", "2", "4"}
    assert pop.set_index("data_id").loc["2", "composicao"] == "linda flor|vogeler"


def test_review_rejects_unknown_action(tmp_path):
    path = tmp_path / "rev.csv"
    pd.DataFrame([{"data_id": "1", "acao": "apagar", "valor": ""}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="desconhecida"):
        load_review(path)


def test_balanced_order_keeps_proportions_at_every_prefix():
    strata = pd.Series([1920] * 30 + [1930] * 60 + [1940] * 10)
    order = balanced_order(strata, np.random.default_rng(0))
    assert sorted(order) == list(range(100))
    labels = strata.iloc[order].to_numpy()
    for n in range(1, 101):
        for value, share in [(1920, 0.3), (1930, 0.6), (1940, 0.1)]:
            assert abs(np.sum(labels[:n] == value) - n * share) < 1.0 + 1e-9


def test_sampling_order_one_per_composition_dev_split_and_reproducible():
    rows = [[str(i), f"T{i}", "A", f"C{i}", "Samba", 1930 + i % 20] for i in range(40)]
    rows.append(["99", "T1 (Subtítulo)", "A", "Outro", "Samba", 1951])  # mesma composição de T1
    df = _df(rows)
    a = sampling_order(df, seed=7, dev_size=5)
    b = sampling_order(df, seed=7, dev_size=5)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 40  # T1 tem duas gravações, uma sorteada
    assert list(a["split"][:5]) == ["dev"] * 5
    assert set(a["split"][5:]) == {"test"}
    assert list(a["posicao"]) == list(range(1, 41))
    t1 = a[a["titulo"].str.startswith("T1") & (a["n_gravacoes_composicao"] == 2)]
    assert len(t1) == 1
    assert sampling_order(df, seed=8, dev_size=5)["data_id"].tolist() != a["data_id"].tolist()
