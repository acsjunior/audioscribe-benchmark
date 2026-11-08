import csv
import pytest

from benchmark.dataset import load_catalog


CSV_HEADER = "Música,Autoria,Interpretação,Acompanhamento,Disco,Ano,Gênero,Letra,Arquivo,URL,Fonte,Acesso"

def _make_row(
    musica="As Rosas Não Falam",
    autoria="Cartola",
    interpretacao="Cartola",
    acompanhamento="Regional",
    disco="Cartola",
    ano="1976",
    genero="Samba",
    letra="As rosas não falam\nApenas perfumam",
    arquivo="As Rosas Não Falam - Cartola.mp3",
    url="https://drive.google.com/file/d/ABC123/view?usp=sharing",
    fonte="",
    acesso="",
):
    return {
        "Música": musica, "Autoria": autoria, "Interpretação": interpretacao,
        "Acompanhamento": acompanhamento, "Disco": disco, "Ano": ano, "Gênero": genero,
        "Letra": letra, "Arquivo": arquivo, "URL": url, "Fonte": fonte, "Acesso": acesso,
    }


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_make_row().keys())
        writer.writeheader()
        writer.writerows(rows)


def test_load_catalog(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv(csv_path, [_make_row()])

    songs = load_catalog(csv_path)

    assert len(songs) == 1
    s = songs[0]
    assert s.titulo == "As Rosas Não Falam"
    assert s.autoria == "Cartola"
    assert s.interpretacao == "Cartola"
    assert s.disco == "Cartola"
    assert s.ano == "1976"
    assert s.genero == "Samba"
    assert s.ground_truth == "As rosas não falam\nApenas perfumam"
    assert s.audio_url == "https://drive.google.com/file/d/ABC123/view?usp=sharing"
    assert s.audio_filename == "As Rosas Não Falam - Cartola.mp3"


def test_load_catalog_song_id_slug(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv(csv_path, [_make_row(musica="As Rosas Não Falam", interpretacao="Cartola")])

    songs = load_catalog(csv_path)
    assert songs[0].song_id == "cartola-as-rosas-nao-falam"


def test_load_catalog_sorted_order(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv(csv_path, [
        _make_row(musica="Folhas Secas", interpretacao="Nelson Cavaquinho"),
        _make_row(musica="As Rosas Não Falam", interpretacao="Cartola"),
    ])

    songs = load_catalog(csv_path)
    assert songs[0].song_id == "cartola-as-rosas-nao-falam"
    assert songs[1].song_id == "nelson-cavaquinho-folhas-secas"


def test_load_catalog_raises_if_not_found():
    with pytest.raises(FileNotFoundError):
        load_catalog("caminho/inexistente/catalogo.csv")


def test_load_catalog_strips_whitespace(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    row = _make_row(musica="  As Rosas Não Falam  ", autoria="  Cartola  ")
    _write_csv(csv_path, [row])

    songs = load_catalog(csv_path)
    assert songs[0].titulo == "As Rosas Não Falam"
    assert songs[0].autoria == "Cartola"


# --- Split ---

def _write_csv_with_split(path, rows_and_splits):
    fieldnames = list(_make_row().keys()) + ["Split"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row, split in rows_and_splits:
            writer.writerow({**row, "Split": split})


def test_load_catalog_without_split_column_defaults_to_dev(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv(csv_path, [_make_row()])

    assert load_catalog(csv_path)[0].split == "dev"


def test_load_catalog_reads_split_column(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv_with_split(csv_path, [
        (_make_row(musica="A", interpretacao="X"), "dev"),
        (_make_row(musica="B", interpretacao="X"), " TEST "),
    ])

    songs = load_catalog(csv_path)
    assert [s.split for s in songs] == ["dev", "test"]


@pytest.mark.parametrize("value", ["", "teste", "train"])
def test_load_catalog_rejects_invalid_split(tmp_path, value):
    csv_path = tmp_path / "catalogo.csv"
    _write_csv_with_split(csv_path, [(_make_row(), value)])

    with pytest.raises(ValueError, match="Split"):
        load_catalog(csv_path)


def test_load_catalog_ignores_extra_columns(tmp_path):
    csv_path = tmp_path / "catalogo.csv"
    fieldnames = list(_make_row().keys()) + ["Ano Morte Autores"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({**_make_row(), "Ano Morte Autores": "1937"})

    assert len(load_catalog(csv_path)) == 1
