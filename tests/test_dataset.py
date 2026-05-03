import pytest

from benchmark.dataset import _parse_ground_truth, load_dataset


GROUND_TRUTH_WITH_HEADER = """\
artista: Cartola
titulo: As Rosas Não Falam
ano: 1976
album: Cartola
---
As rosas não falam
Apenas perfumam
"""

GROUND_TRUTH_WITHOUT_HEADER = """\
As rosas não falam
Apenas perfumam
"""


def test_parse_ground_truth_with_header(tmp_path):
    gt = tmp_path / "ground_truth.txt"
    gt.write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")
    metadata, lyrics = _parse_ground_truth(gt)
    assert metadata["artista"] == "Cartola"
    assert metadata["titulo"] == "As Rosas Não Falam"
    assert metadata["ano"] == "1976"
    assert metadata["album"] == "Cartola"
    assert lyrics == "As rosas não falam\nApenas perfumam"


def test_parse_ground_truth_without_header(tmp_path):
    gt = tmp_path / "ground_truth.txt"
    gt.write_text(GROUND_TRUTH_WITHOUT_HEADER, encoding="utf-8")
    metadata, lyrics = _parse_ground_truth(gt)
    assert metadata == {}
    assert "As rosas não falam" in lyrics


def test_load_dataset(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "audio.mp3").write_bytes(b"")
    (song_dir / "ground_truth.txt").write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")

    songs = load_dataset(str(tmp_path))
    assert len(songs) == 1
    assert songs[0].song_id == "cartola-as-rosas-nao-falam"
    assert songs[0].artista == "Cartola"
    assert songs[0].ground_truth == "As rosas não falam\nApenas perfumam"


def test_load_dataset_skips_missing_audio(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "ground_truth.txt").write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")

    songs = load_dataset(str(tmp_path))
    assert songs == []


def test_load_dataset_skips_missing_ground_truth(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "audio.mp3").write_bytes(b"")

    songs = load_dataset(str(tmp_path))
    assert songs == []


def test_load_dataset_raises_if_path_not_found():
    with pytest.raises(FileNotFoundError):
        load_dataset("caminho/inexistente")


def test_load_dataset_sorted_order(tmp_path):
    for name in ["nelson-cavaquinho-folhas-secas", "cartola-as-rosas-nao-falam"]:
        d = tmp_path / name
        d.mkdir()
        (d / "audio.mp3").write_bytes(b"")
        (d / "ground_truth.txt").write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")

    songs = load_dataset(str(tmp_path))
    assert songs[0].song_id == "cartola-as-rosas-nao-falam"
    assert songs[1].song_id == "nelson-cavaquinho-folhas-secas"
