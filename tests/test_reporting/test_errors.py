import pytest

from benchmark.config.schema import AnalysisConfig
from benchmark.models import ExperimentResult
from benchmark.reporting.errors import analyze_errors, diagnose, flags_for
from benchmark.reporting.stats import analyze


def make(song, text, truth="a b c d", run=1, provider=None, error=None):
    return ExperimentResult(
        song_id=song, titulo=song, autoria="", interpretacao="", disco="", ano="", genero="",
        whisper_transcription=text if provider is None else "a b c d",
        refinement_provider=provider,
        refinement_model="m" if provider else None,
        prompt_name="p" if provider else None,
        prompt_file=None,
        refined_transcription=text if provider else None,
        ground_truth=truth, run=run, error=error,
        metrics={"wer": 0.0},
    )


def test_diagnose_splits_error_types():
    d = diagnose("a x c d e", "a b c d")
    assert (d["substitutions"], d["deletions"], d["insertions"]) == (1, 0, 1)
    assert d["wer"] == pytest.approx(0.5)
    assert d["sub_rate"] + d["del_rate"] + d["ins_rate"] == pytest.approx(d["wer"])
    assert d["length_ratio"] == pytest.approx(5 / 4)


def test_diagnose_normalizes_punctuation_and_case():
    d = diagnose("A, B! c d.", "a b c d")
    assert d["wer"] == 0


def test_diagnose_empty_hypothesis_is_all_deletions():
    d = diagnose("", "a b c d")
    assert d["deletions"] == 4
    assert d["wer"] == 1.0
    assert d["length_ratio"] == 0


def test_diagnose_empty_reference_returns_none():
    assert diagnose("a b", "") is None


def test_flags():
    cfg = AnalysisConfig()
    assert flags_for(diagnose("a b c d", "a b c d"), cfg) == ["wer_zero"]
    assert flags_for(diagnose("a", "a b c d"), cfg) == ["curta"]
    assert flags_for(diagnose("a b c d e f", "a b c d"), cfg) == ["longa"]
    assert flags_for(diagnose("a b x d", "a b c d"), cfg) == []


def test_analyze_errors_by_method_and_alerts():
    results = [
        make("s1", "a b x d"),
        make("s2", "a b c d"),
        make("s1", "a", provider="x"),
        make("s2", "a b c d e f g", provider="x"),
    ]
    out = analyze_errors(results, AnalysisConfig())
    baseline, method = out["methods"]
    assert baseline["provider"] == ""
    assert baseline["alerts"]["wer_zero"] == 1
    assert method["alerts"]["curta"] == 1
    assert method["alerts"]["longa"] == 1
    assert method["flagged"][0]["song_id"] == "s1"  # razão 0,25 é o mais distante de 1


def test_analyze_errors_ignores_failed_results():
    out = analyze_errors([make("s1", "", provider="x", error="bloqueado")], AnalysisConfig())
    assert out["methods"] == []


def test_stats_json_includes_errors():
    out = analyze([make("s1", "a b c d")], ["wer"], AnalysisConfig())
    assert "errors" in out
    assert out["errors"]["methods"][0]["num_songs"] == 1
