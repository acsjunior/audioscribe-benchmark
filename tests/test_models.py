from pathlib import Path

from benchmark.models import ExperimentResult, SongData


def make_result(**kwargs) -> ExperimentResult:
    defaults = dict(
        song_id="cartola-as-rosas-nao-falam",
        artista="Cartola",
        titulo="As Rosas Não Falam",
        ano="1976",
        album="Cartola",
        whisper_transcription="as rosas nao falam",
        refinement_provider=None,
        refinement_model=None,
        prompt_name=None,
        prompt_file=None,
        refined_transcription=None,
        ground_truth="As rosas não falam",
    )
    return ExperimentResult(**{**defaults, **kwargs})


def test_song_data_fields():
    song = SongData(
        song_id="cartola-as-rosas-nao-falam",
        artista="Cartola",
        titulo="As Rosas Não Falam",
        ano="1976",
        album="Cartola",
        audio_path=Path("data/dataset/cartola-as-rosas-nao-falam/audio.mp3"),
        ground_truth="As rosas não falam",
    )
    assert song.song_id == "cartola-as-rosas-nao-falam"
    assert song.artista == "Cartola"


def test_evaluated_transcription_baseline():
    result = make_result()
    assert result.evaluated_transcription == "as rosas nao falam"


def test_evaluated_transcription_refined():
    result = make_result(refined_transcription="As rosas não falam")
    assert result.evaluated_transcription == "As rosas não falam"


def test_experiment_label_baseline():
    result = make_result()
    assert result.experiment_label == "baseline (whisper only)"


def test_experiment_label_with_refinement():
    result = make_result(
        refinement_provider="openai",
        refinement_model="gpt-4o",
        prompt_name="minimalist",
    )
    assert result.experiment_label == "openai/gpt-4o [minimalist]"


def test_metrics_default_empty():
    result = make_result()
    assert result.metrics == {}


def test_error_default_none():
    result = make_result()
    assert result.error is None
