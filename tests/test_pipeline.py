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
        dataset_path=str(tmp_path / "dataset"),
        results_path=str(tmp_path / "results"),
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
        dataset_path=str(tmp_path / "dataset"),
        results_path=str(tmp_path / "results"),
        refinement=[
            RefinementConfig(provider="openai", model="gpt-4o", prompt_file=str(prompt_file))
        ],
    )
    return cfg, tmp_path


@pytest.fixture
def fake_song(tmp_path) -> SongData:
    return SongData(
        song_id="cartola-as-rosas-nao-falam",
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        audio_path=tmp_path / "audio.mp3",
        ground_truth="As rosas não falam",
    )


@patch("benchmark.pipeline.load_dataset")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_baseline_only(mock_transcriber_cls, mock_load_dataset, config, fake_song):
    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber
    mock_load_dataset.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    assert (run_dir / "results.json").exists()
    assert (run_dir / "report.html").exists()


@patch("benchmark.pipeline.load_dataset")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_with_refinement(
    mock_get_refiner, mock_transcriber_cls, mock_load_dataset, config_with_refinement, fake_song
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
    mock_load_dataset.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    assert mock_refiner.refine.call_count == 1


@patch("benchmark.pipeline.load_dataset")
@patch("benchmark.pipeline.WhisperTranscriber")
async def test_pipeline_skips_song_on_transcription_failure(
    mock_transcriber_cls, mock_load_dataset, config, fake_song
):
    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(side_effect=RuntimeError("API error"))
    mock_transcriber_cls.return_value = mock_transcriber
    mock_load_dataset.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert not (run_dir / "results.csv").exists()


@patch("benchmark.pipeline.load_dataset")
@patch("benchmark.pipeline.WhisperTranscriber")
@patch("benchmark.pipeline.get_refiner")
async def test_pipeline_records_error_on_refinement_failure(
    mock_get_refiner, mock_transcriber_cls, mock_load_dataset, config_with_refinement, fake_song
):
    config, _ = config_with_refinement

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="as rosas nao falam")
    mock_transcriber_cls.return_value = mock_transcriber

    mock_refiner = MagicMock()
    mock_refiner.refine = AsyncMock(side_effect=RuntimeError("LLM error"))
    mock_get_refiner.return_value = mock_refiner
    mock_load_dataset.return_value = [fake_song]

    pipeline = Pipeline(config)
    run_dir = await pipeline.run()

    assert (run_dir / "results.csv").exists()
    rows = list(csv.DictReader((run_dir / "results.csv").read_text(encoding="utf-8").splitlines()))
    error_rows = [r for r in rows if r["error"]]
    assert len(error_rows) == 1
    assert "LLM error" in error_rows[0]["error"]
