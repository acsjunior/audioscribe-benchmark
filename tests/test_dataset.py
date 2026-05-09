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
