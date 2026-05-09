import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.config.schema import ExperimentConfig, RefinementConfig
from benchmark.models import SongData
from benchmark.pipeline import Pipeline
from benchmark.refinement.base import RefinementResult


@pytest.fixture
def config(tmp_path) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="teste",
        metrics=["wer"],
        catalog_path=str(tmp_path / "catalogo.csv"),
        results_path=str(tmp_path / "results"),
        drive={"audio_dir": str(tmp_path / "inputs")},
    )


@pytest.fixture
def config_with_refinement(tmp_path) -> tuple[ExperimentConfig, Path]:
    prompt_file = tmp_path / "minimalist.yaml"
    prompt_file.write_text(
        "name: minimalist\ndescription: test\nsystem: sys\nuser: '{transcription}'\n",
        encoding="utf-8",
    )
    cfg = ExperimentConfig(
        experiment_name="teste",
        metrics=["wer"],
        catalog_path=str(tmp_path / "catalogo.csv"),
        results_path=str(tmp_path / "results"),
        drive={"audio_dir": str(tmp_path / "inputs")},
        refinement=[
            RefinementConfig(provider="openai", model="gpt-4o", prompt_file=str(prompt_file))
        ],
    )
    return cfg, tmp_path


@pytest.fixture
def fake_song(tmp_path) -> SongData:
    audio_path = tmp_path / "inputs" / "audio.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"")
    return SongData(
        song_id="cartola-as-rosas-nao-falam",
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        genero="Samba",
        audio_url="https://drive.google.com/file/d/ABC/view",
        audio_filename="audio.mp3",
        ground_truth="As rosas não falam",
    )


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_baseline_only(mock_transcriber_cls, mock_load_catalog, config, fake_song):
    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber
    mock_load_catalog.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    assert (run_dir / "results.json").exists()
    assert (run_dir / "report.html").exists()


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_with_refinement(
    mock_get_refiner, mock_transcriber_cls, mock_load_catalog, config_with_refinement, fake_song
):
    config, _ = config_with_refinement

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber

    mock_refiner = MagicMock()
    mock_refiner.refine = AsyncMock(
        return_value=RefinementResult(
            refined_text="As rosas não falam", tokens_used=50, response_time_ms=300.0
        )
    )
    mock_get_refiner.return_value = mock_refiner
    mock_load_catalog.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    assert mock_refiner.refine.call_count == 1


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_passes_metadata_to_refiner(
    mock_get_refiner, mock_transcriber_cls, mock_load_catalog, config_with_refinement, fake_song
):
    config, _ = config_with_refinement

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber

    mock_refiner = MagicMock()
    mock_refiner.refine = AsyncMock(
        return_value=RefinementResult(refined_text="As rosas não falam", tokens_used=50)
    )
    mock_get_refiner.return_value = mock_refiner
    mock_load_catalog.return_value = [fake_song]

    pipeline = Pipeline(config)
    await pipeline.run()

    _, call_kwargs = mock_refiner.refine.call_args
    metadata = call_kwargs.get("metadata") or mock_refiner.refine.call_args.args[2]
    assert metadata["titulo"] == fake_song.titulo
    assert metadata["autoria"] == fake_song.autoria
    assert metadata["interpretacao"] == fake_song.interpretacao
    assert metadata["ano"] == fake_song.ano


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_skips_song_on_transcription_failure(
    mock_transcriber_cls, mock_load_catalog, config, fake_song
):
    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(side_effect=RuntimeError("API error"))
    mock_transcriber_cls.return_value = mock_transcriber
    mock_load_catalog.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert not (run_dir / "results.csv").exists()


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_records_error_on_refinement_failure(
    mock_get_refiner, mock_transcriber_cls, mock_load_catalog, config_with_refinement, fake_song
):
    config, _ = config_with_refinement

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber

    mock_refiner = MagicMock()
    mock_refiner.refine = AsyncMock(side_effect=RuntimeError("LLM error"))
    mock_get_refiner.return_value = mock_refiner
    mock_load_catalog.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    rows = list(csv.DictReader((run_dir / "results.csv").read_text(encoding="utf-8").splitlines()))
    error_rows = [r for r in rows if r["error"]]
    assert len(error_rows) == 1
    assert "LLM error" in error_rows[0]["error"]


@patch("benchmark.pipeline.download_audio")
@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_downloads_missing_audio(
    mock_transcriber_cls, mock_load_catalog, mock_download, config, tmp_path
):
    song = SongData(
        song_id="cartola-as-rosas-nao-falam",
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        genero="Samba",
        audio_url="https://drive.google.com/file/d/ABC/view",
        audio_filename="audio.mp3",
        ground_truth="As rosas não falam",
    )
    mock_load_catalog.return_value = [song]

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber

    fake_service = MagicMock()
    pipeline = Pipeline(config, drive_service=fake_service)

    def create_audio_file(service, url, dest_path):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"")

    mock_download.side_effect = create_audio_file
    await pipeline.run()

    mock_download.assert_called_once()


@patch("benchmark.pipeline.isolate_voice")
@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_calls_isolate_voice_when_enabled(
    mock_transcriber_cls, mock_load_catalog, mock_isolate_voice, config, fake_song, tmp_path
):
    isolated_path = tmp_path / "inputs" / "audio_vocals.wav"
    isolated_path.parent.mkdir(parents=True, exist_ok=True)
    isolated_path.write_bytes(b"")
    mock_isolate_voice.return_value = isolated_path

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber
    mock_load_catalog.return_value = [fake_song]

    cfg = ExperimentConfig(
        experiment_name="teste",
        metrics=["wer"],
        catalog_path=str(tmp_path / "catalogo.csv"),
        results_path=str(tmp_path / "results"),
        drive={"audio_dir": str(tmp_path / "inputs")},
        transcription={"voice_isolation": True},
    )
    pipeline = Pipeline(cfg)
    await pipeline.run()

    mock_isolate_voice.assert_called_once()
    transcribe_call_path = mock_transcriber.transcribe.call_args.args[0]
    assert transcribe_call_path == isolated_path


@patch("benchmark.pipeline.isolate_voice")
@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_skips_song_when_isolation_fails(
    mock_transcriber_cls, mock_load_catalog, mock_isolate_voice, config, fake_song
):
    mock_isolate_voice.side_effect = RuntimeError("demucs error")
    mock_transcriber_cls.return_value = MagicMock()
    mock_load_catalog.return_value = [fake_song]

    cfg = ExperimentConfig(
        experiment_name="teste",
        metrics=["wer"],
        catalog_path=str(config.catalog_path),
        results_path=config.results_path,
        drive={"audio_dir": config.drive.audio_dir},
        transcription={"voice_isolation": True},
    )
    pipeline = Pipeline(cfg)
    run_dir = await pipeline.run()

    assert not (run_dir / "results.csv").exists()


@patch("benchmark.pipeline.load_catalog")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_skips_song_when_no_audio_and_no_drive(
    mock_transcriber_cls, mock_load_catalog, config, tmp_path
):
    song = SongData(
        song_id="cartola-as-rosas-nao-falam",
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        genero="Samba",
        audio_url="https://drive.google.com/file/d/ABC/view",
        audio_filename="nao-existe.mp3",
        ground_truth="As rosas não falam",
    )
    mock_load_catalog.return_value = [song]
    mock_transcriber_cls.return_value = MagicMock()

    pipeline = Pipeline(config, drive_service=None)
    run_dir = await pipeline.run()

    assert not (run_dir / "results.csv").exists()
