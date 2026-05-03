import pytest

from benchmark.dataset import _parse_ground_truth, load_dataset


GROUND_TRUTH_WITH_HEADER = """\
titulo: As Rosas Não Falam
autoria: Cartola
interpretacao: Cartola
disco: Cartola
ano: 1976
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
    assert metadata["titulo"] == "As Rosas Não Falam"
    assert metadata["autoria"] == "Cartola"
    assert metadata["interpretacao"] == "Cartola"
    assert metadata["disco"] == "Cartola"
    assert metadata["ano"] == "1976"
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
    assert songs[0].autoria == "Cartola"
    assert songs[0].interpretacao == "Cartola"
    assert songs[0].ground_truth == "As rosas não falam\nApenas perfumam"


def test_load_dataset_accepts_any_mp3_filename(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "cartola_rosas.mp3").write_bytes(b"")
    (song_dir / "ground_truth.txt").write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")

    songs = load_dataset(str(tmp_path))
    assert len(songs) == 1
    assert songs[0].audio_path.name == "cartola_rosas.mp3"


def test_load_dataset_skips_no_mp3(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "ground_truth.txt").write_text(GROUND_TRUTH_WITH_HEADER, encoding="utf-8")

    songs = load_dataset(str(tmp_path))
    assert songs == []


def test_load_dataset_skips_multiple_mp3(tmp_path):
    song_dir = tmp_path / "cartola-as-rosas-nao-falam"
    song_dir.mkdir()
    (song_dir / "audio.mp3").write_bytes(b"")
    (song_dir / "audio2.mp3").write_bytes(b"")
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
