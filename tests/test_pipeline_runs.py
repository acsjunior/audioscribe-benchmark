"""Testes das rodadas múltiplas, do cache de transcrições e do filtro por split."""

import csv
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.config.schema import ExperimentConfig, RefinementConfig
from benchmark.models import SongData
from benchmark.pipeline import Pipeline
from benchmark.refinement.base import RefinementResult


def _config(tmp_path, **transcription) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="teste",
        metrics=["wer"],
        catalog_path=str(tmp_path / "catalogo.csv"),
        results_path=str(tmp_path / "results"),
        drive={"audio_dir": str(tmp_path / "inputs")},
        transcription=transcription,
    )


def _song(tmp_path, song_id="cartola-as-rosas", split="dev", filename="audio.mp3") -> SongData:
    audio = tmp_path / "inputs" / filename
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"audio-" + song_id.encode())
    return SongData(
        song_id=song_id,
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        genero="Samba",
        audio_url="https://drive.google.com/file/d/ABC/view",
        audio_filename=filename,
        ground_truth="As rosas não falam",
        split=split,
    )


def _transcriber(side_effect=None):
    t = MagicMock()
    t.transcribe = AsyncMock(
        side_effect=side_effect or (lambda path: "as rosas nao falam")
    )
    return t


def _rows(run_dir):
    text = (run_dir / "results.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_multiple_runs_produce_one_baseline_per_run(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = t = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]

    run_dir = await Pipeline(_config(tmp_path, runs=3)).run()

    assert t.transcribe.call_count == 3
    rows = _rows(run_dir)
    assert [r["run"] for r in rows] == ["1", "2", "3"]
    assert all(r["split"] == "dev" for r in rows)


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_second_execution_reuses_cached_transcriptions(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = t = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    await Pipeline(_config(tmp_path, runs=3)).run()

    mock_cls.return_value = t2 = _transcriber()
    run_dir = await Pipeline(_config(tmp_path, runs=3)).run()

    assert t.transcribe.call_count == 3
    assert t2.transcribe.call_count == 0
    assert len(_rows(run_dir)) == 3
    assert (tmp_path / "transcriptions").is_dir()


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_increasing_runs_only_transcribes_missing_ones(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    await Pipeline(_config(tmp_path, runs=2)).run()

    mock_cls.return_value = t2 = _transcriber()
    run_dir = await Pipeline(_config(tmp_path, runs=5)).run()

    assert t2.transcribe.call_count == 3
    assert len(_rows(run_dir)) == 5


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_cache_is_per_transcription_config(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    await Pipeline(_config(tmp_path, model="whisper-1")).run()

    mock_cls.return_value = t2 = _transcriber()
    await Pipeline(_config(tmp_path, model="gpt-4o-transcribe")).run()

    assert t2.transcribe.call_count == 1


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_cache_disabled_always_transcribes(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    await Pipeline(_config(tmp_path, cache=False)).run()

    mock_cls.return_value = t2 = _transcriber()
    await Pipeline(_config(tmp_path, cache=False)).run()

    assert t2.transcribe.call_count == 1
    assert not (tmp_path / "transcriptions").exists()


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_custom_cache_dir(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    await Pipeline(_config(tmp_path, cache_dir=str(tmp_path / "meu_cache"))).run()

    assert any((tmp_path / "meu_cache").rglob("run_01.json"))


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_failed_run_is_skipped_and_not_cached(mock_cls, mock_catalog, tmp_path):
    calls = {"n": 0}

    def flaky(path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("API error")
        return "as rosas nao falam"

    mock_cls.return_value = _transcriber(side_effect=flaky)
    mock_catalog.return_value = [_song(tmp_path)]
    cfg = _config(tmp_path, runs=3)
    cfg.retry.max_attempts = 1
    run_dir = await Pipeline(cfg).run()

    assert [r["run"] for r in _rows(run_dir)] == ["1", "3"]

    mock_cls.return_value = t2 = _transcriber()
    await Pipeline(cfg).run()
    assert t2.transcribe.call_count == 1  # só a rodada 2, que falhou


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_refinement_runs_on_each_transcription(
    mock_get_refiner, mock_cls, mock_catalog, tmp_path
):
    texts = iter(["rodada um", "rodada dois"])
    mock_cls.return_value = _transcriber(side_effect=lambda path: next(texts))
    mock_catalog.return_value = [_song(tmp_path)]

    refiner = MagicMock()
    refiner.refine = AsyncMock(return_value=RefinementResult(refined_text="As rosas não falam"))
    mock_get_refiner.return_value = refiner

    prompt_file = tmp_path / "p.yaml"
    prompt_file.write_text("name: p\nsystem: s\nuser: '{transcription}'\n", encoding="utf-8")
    cfg = _config(tmp_path, runs=2)
    cfg.refinement = [
        RefinementConfig(provider="openai", model="gpt-4o", prompt_file=str(prompt_file))
    ]

    run_dir = await Pipeline(cfg).run()

    refined_inputs = [c.args[0] for c in refiner.refine.call_args_list]
    assert refined_inputs == ["rodada um", "rodada dois"]
    rows = _rows(run_dir)
    assert [(r["run"], r["refinement_provider"]) for r in rows] == [
        ("1", "baseline"), ("1", "openai"), ("2", "baseline"), ("2", "openai"),
    ]


# --- split ---

@pytest.mark.parametrize(
    ("split", "expected"),
    [("dev", {"song-dev"}), ("test", {"song-test"}), ("all", {"song-dev", "song-test"})],
)
@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_split_filter(mock_cls, mock_catalog, tmp_path, split, expected):
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [
        _song(tmp_path, "song-dev", "dev", "dev.mp3"),
        _song(tmp_path, "song-test", "test", "test.mp3"),
    ]
    cfg = _config(tmp_path)
    cfg.split = split

    run_dir = await Pipeline(cfg).run()

    assert {r["song_id"] for r in _rows(run_dir)} == expected


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_default_split_is_dev(mock_cls, mock_catalog, tmp_path):
    mock_cls.return_value = t = _transcriber()
    mock_catalog.return_value = [_song(tmp_path, "song-test", "test", "test.mp3")]

    await Pipeline(_config(tmp_path)).run()

    assert t.transcribe.call_count == 0


# --- análise estatística ---

@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_writes_stats_json(mock_get_refiner, mock_cls, mock_catalog, tmp_path):
    import json

    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]
    refiner = MagicMock()
    refiner.refine = AsyncMock(return_value=RefinementResult(refined_text="As rosas não falam"))
    mock_get_refiner.return_value = refiner

    prompt_file = tmp_path / "p.yaml"
    prompt_file.write_text("name: p\nsystem: s\nuser: '{transcription}'\n", encoding="utf-8")
    cfg = _config(tmp_path, runs=2)
    cfg.refinement = [
        RefinementConfig(provider="openai", model="gpt-4o", prompt_file=str(prompt_file))
    ]
    cfg.analysis.bootstrap_samples = 200

    run_dir = await Pipeline(cfg).run()

    stats = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
    assert stats["num_runs"] == 2
    method = stats["metrics"]["wer"]["methods"][0]
    assert method["num_evaluations"] == 2
    assert "Análise Estatística" in (run_dir / "report.html").read_text(encoding="utf-8")


@patch("benchmark.pipeline.analyze", side_effect=RuntimeError("boom"))
@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_survives_analysis_failure(mock_cls, mock_catalog, mock_analyze, tmp_path):
    assert mock_analyze is not None
    mock_cls.return_value = _transcriber()
    mock_catalog.return_value = [_song(tmp_path)]

    run_dir = await Pipeline(_config(tmp_path)).run()

    assert (run_dir / "report.html").exists()
    assert not (run_dir / "stats.json").exists()
