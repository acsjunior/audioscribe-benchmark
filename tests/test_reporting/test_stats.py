import json

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from benchmark.cli import cli
from benchmark.config.schema import AnalysisConfig
from benchmark.models import ExperimentResult
from benchmark.reporting.html_reporter import write_html
from benchmark.reporting.json_reporter import read_json, write_json
from benchmark.reporting.stats import analyze, higher_is_better, write_stats_json

CONFIG = AnalysisConfig(bootstrap_samples=1000)


def make(song, run, value, provider=None, prompt="p", metric="wer", error=None):
    return ExperimentResult(
        song_id=song,
        titulo=song,
        autoria="a",
        interpretacao="i",
        disco="d",
        ano="1930",
        genero="Samba",
        whisper_transcription="texto",
        refinement_provider=provider,
        refinement_model="gpt-4o" if provider else None,
        prompt_name=prompt if provider else None,
        prompt_file=None,
        refined_transcription="refinado" if provider else None,
        ground_truth="gt",
        metrics={} if error else {metric: value},
        error=error,
        run=run,
    )


def dataset(baselines, methods, metric="wer", prompt="p"):
    """baselines/methods: {song: [valor por rodada]}."""
    rows = []
    for song, values in baselines.items():
        rows += [make(song, i + 1, v, metric=metric) for i, v in enumerate(values)]
    for song, values in methods.items():
        rows += [
            make(song, i + 1, v, provider="openai", prompt=prompt, metric=metric)
            for i, v in enumerate(values)
        ]
    return rows


def method(analysis, metric="wer", index=0):
    return analysis["metrics"][metric]["methods"][index]


def test_higher_is_better():
    assert higher_is_better("bertscore")
    assert not higher_is_better("wer")
    assert not higher_is_better("cer")


def test_gain_is_positive_when_lower_metric_improves():
    rows = dataset({"a": [0.5], "b": [0.4]}, {"a": [0.3], "b": [0.3]})
    m = method(analyze(rows, ["wer"], CONFIG))
    assert m["gain_mean"] == pytest.approx(0.15)  # (0.2 + 0.1) / 2


def test_gain_is_positive_when_higher_metric_improves():
    rows = dataset({"a": [0.5]}, {"a": [0.7]}, metric="bertscore")
    analysis = analyze(rows, ["bertscore"], CONFIG)
    assert analysis["metrics"]["bertscore"]["direction"] == "higher"
    assert method(analysis, "bertscore")["gain_mean"] == pytest.approx(0.2)


def test_pairs_each_refinement_with_baseline_of_same_run():
    rows = dataset({"a": [0.9, 0.1]}, {"a": [0.8, 0.0]})
    m = method(analyze(rows, ["wer"], CONFIG))
    # pareado por rodada: (0.9-0.8) e (0.1-0.0), ambos +0.1 — e não 0.5-0.4 de médias
    assert m["gain_mean"] == pytest.approx(0.1)
    assert m["num_evaluations"] == 2


def test_song_is_the_unit_of_analysis():
    rows = dataset({"a": [0.5, 0.5, 0.5], "b": [0.5]}, {"a": [0.4, 0.4, 0.4], "b": [0.6]})
    m = method(analyze(rows, ["wer"], CONFIG))
    assert m["num_songs"] == 2
    assert m["num_evaluations"] == 4
    assert m["gain_mean"] == pytest.approx(0.0)  # (+0.1 + -0.1) / 2, e não 3x a música a


def test_wins_ties_losses_are_counted_per_song():
    rows = dataset(
        {"a": [0.5], "b": [0.5], "c": [0.5], "d": [0.5]},
        {"a": [0.4], "b": [0.3], "c": [0.5], "d": [0.6]},
    )
    m = method(analyze(rows, ["wer"], CONFIG))
    assert (m["wins"], m["ties"], m["losses"]) == (2, 1, 1)


def test_median_gain_resists_one_catastrophic_song():
    baselines = {f"s{i}": [0.30] for i in range(9)} | {"bad": [0.30]}
    methods = {f"s{i}": [0.29] for i in range(9)} | {"bad": [1.10]}
    m = method(analyze(dataset(baselines, methods), ["wer"], CONFIG))
    assert m["gain_mean"] < 0  # a média acusa piora...
    assert m["gain_median"] == pytest.approx(0.01)  # ...a mediana mostra o caso típico
    assert m["wins"] == 9
    assert m["losses"] == 1


def test_severe_failures_counted_per_evaluation_with_threshold():
    rows = dataset({"a": [0.3, 0.3], "b": [0.3, 0.3]}, {"a": [0.9, 0.3], "b": [0.45, 0.3]})
    m = method(analyze(rows, ["wer"], CONFIG))
    assert m["severe_failures"] == 1  # a/rodada 1 (-0.6); b/rodada 1 (-0.15) não passa de 0.2
    assert m["severe_failure_rate"] == pytest.approx(1 / 4)

    strict = AnalysisConfig(bootstrap_samples=1000, severe_failure_threshold=0.1)
    assert method(analyze(rows, ["wer"], strict))["severe_failures"] == 2


def test_worst_cases_are_sorted_and_only_include_regressions():
    rows = dataset(
        {"a": [0.3], "b": [0.3], "c": [0.3]}, {"a": [0.5], "b": [0.9], "c": [0.1]}
    )
    worst = method(analyze(rows, ["wer"], CONFIG))["worst_cases"]
    assert [w["song_id"] for w in worst] == ["b", "a"]
    assert worst[0]["gain"] == pytest.approx(-0.6)


def test_errors_and_missing_metrics_are_ignored():
    rows = dataset({"a": [0.5], "b": [0.5]}, {"a": [0.4]})
    rows.append(make("b", 1, None, provider="openai", error="falhou"))
    m = method(analyze(rows, ["wer"], CONFIG))
    assert m["num_songs"] == 1


def test_method_row_without_baseline_is_dropped():
    rows = dataset({"a": [0.5]}, {"a": [0.4], "orfa": [0.1]})
    assert method(analyze(rows, ["wer"], CONFIG))["num_songs"] == 1


def test_only_baseline_gives_no_methods():
    analysis = analyze(dataset({"a": [0.5]}, {}), ["wer"], CONFIG)
    assert analysis["metrics"]["wer"]["methods"] == []
    assert analysis["metrics"]["wer"]["baseline"]["mean"] == pytest.approx(0.5)


def test_methods_are_sorted_by_median_gain():
    rows = dataset({"a": [0.5], "b": [0.5]}, {"a": [0.45], "b": [0.45]}, prompt="pior")
    rows += [
        make(s, 1, 0.2, provider="openai", prompt="melhor") for s in ("a", "b")
    ]
    prompts = [m["prompt"] for m in analyze(rows, ["wer"], CONFIG)["metrics"]["wer"]["methods"]]
    assert prompts == ["melhor", "pior"]


# --- baseline ---

def test_baseline_noise_between_runs():
    rows = dataset({"a": [0.1, 0.3], "b": [0.5, 0.5]}, {})
    base = analyze(rows, ["wer"], CONFIG)["metrics"]["wer"]["baseline"]
    # desvio (n-1) de [0.1, 0.3] = 0.1414; de [0.5, 0.5] = 0
    assert base["mean_std_between_runs"] == pytest.approx(0.1414213 / 2, rel=1e-4)
    assert base["mean"] == pytest.approx((0.2 + 0.5) / 2)


def test_baseline_noise_is_none_with_single_run():
    base = analyze(dataset({"a": [0.1], "b": [0.5]}, {}), ["wer"], CONFIG)["metrics"]["wer"][
        "baseline"
    ]
    assert base["mean_std_between_runs"] is None


# --- intervalos e testes ---

def test_bootstrap_is_deterministic_and_brackets_the_mean():
    baselines = {f"s{i}": [0.5] for i in range(20)}
    methods = {f"s{i}": [0.5 - 0.01 * i] for i in range(20)}
    a = method(analyze(dataset(baselines, methods), ["wer"], CONFIG))
    b = method(analyze(dataset(baselines, methods), ["wer"], CONFIG))
    assert a["gain_mean_ci"] == b["gain_mean_ci"]
    low, high = a["gain_mean_ci"]
    assert low < a["gain_mean"] < high


def test_ci_excludes_zero_flags_significant_gain():
    baselines = {f"s{i}": [0.5] for i in range(15)}
    methods = {f"s{i}": [0.4 - 0.001 * i] for i in range(15)}
    m = method(analyze(dataset(baselines, methods), ["wer"], CONFIG))
    assert m["gain_mean_sig"] == 1
    assert m["gain_median_sig"] == 1
    assert m["wilcoxon_p"] < 0.001


def test_ci_straddling_zero_is_not_flagged():
    baselines = {f"s{i}": [0.5] for i in range(10)}
    methods = {f"s{i}": [0.5 + (0.05 if i % 2 else -0.05)] for i in range(10)}
    m = method(analyze(dataset(baselines, methods), ["wer"], CONFIG))
    assert m["gain_mean_sig"] == 0


def test_single_song_has_no_ci():
    m = method(analyze(dataset({"a": [0.5]}, {"a": [0.4]}), ["wer"], CONFIG))
    assert m["gain_mean_ci"] is None
    assert m["gain_mean_sig"] == 0


def test_wilcoxon_is_none_when_everything_ties():
    rows = dataset({"a": [0.5], "b": [0.3]}, {"a": [0.5], "b": [0.3]})
    m = method(analyze(rows, ["wer"], CONFIG))
    assert m["wilcoxon_p"] is None
    assert m["ties"] == 2


def test_analysis_header():
    rows = dataset({"a": [0.5, 0.4], "b": [0.5, 0.4]}, {"a": [0.4, 0.3]})
    analysis = analyze(rows, ["wer"], CONFIG)
    assert analysis["num_songs"] == 2
    assert analysis["num_runs"] == 2
    assert analysis["settings"]["confidence"] == 0.95


# --- config ---

def test_analysis_config_defaults_and_validation():
    c = AnalysisConfig()
    assert (c.bootstrap_samples, c.confidence, c.severe_failure_threshold) == (10000, 0.95, 0.2)
    with pytest.raises(ValidationError):
        AnalysisConfig(confidence=1.0)
    with pytest.raises(ValidationError):
        AnalysisConfig(severe_failure_threshold=0)


# --- persistência, HTML e CLI ---

def test_write_stats_json_roundtrip(tmp_path):
    analysis = analyze(dataset({"a": [0.5]}, {"a": [0.4]}), ["wer"], CONFIG)
    out = tmp_path / "stats.json"
    write_stats_json(analysis, out)
    assert json.loads(out.read_text(encoding="utf-8")) == analysis


def test_read_json_roundtrip_and_legacy_files(tmp_path):
    rows = dataset({"a": [0.5]}, {"a": [0.4]})
    out = tmp_path / "results.json"
    write_json(rows, out)
    loaded = read_json(out)
    assert [(r.song_id, r.run, r.refinement_provider) for r in loaded] == [
        ("a", 1, None), ("a", 1, "openai"),
    ]

    # arquivos antigos não têm `run`/`split`, e o CSV usa "baseline" como provedor
    legacy = json.loads(out.read_text(encoding="utf-8"))
    for item in legacy:
        item.pop("run")
        item.pop("split")
    legacy[0]["refinement_provider"] = "baseline"
    out.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = read_json(out)
    assert loaded[0].refinement_provider is None
    assert loaded[0].run == 1
    assert loaded[0].split == "dev"


def test_html_includes_statistics_section_only_with_analysis(tmp_path):
    rows = dataset({"a": [0.5], "b": [0.5]}, {"a": [0.4], "b": [0.3]})
    analysis = analyze(rows, ["wer"], CONFIG)

    with_stats = tmp_path / "with.html"
    write_html(rows, with_stats, "exp", analysis=analysis)
    html = with_stats.read_text(encoding="utf-8")
    assert "Análise Estatística" in html
    assert "menor é melhor" in html
    assert "Wilcoxon" in html

    without = tmp_path / "without.html"
    write_html(rows, without, "exp")
    assert "Análise Estatística" not in without.read_text(encoding="utf-8")


def test_cli_analyze_writes_stats_and_report(tmp_path):
    results_dir = tmp_path / "exp_20260101_000000"
    results_dir.mkdir()
    rows = dataset({"a": [0.5], "b": [0.5]}, {"a": [0.4], "b": [0.3]})
    write_json(rows, results_dir / "results.json")

    result = CliRunner().invoke(cli, ["analyze", str(results_dir / "results.json")])

    assert result.exit_code == 0, result.output
    stats = json.loads((results_dir / "stats.json").read_text(encoding="utf-8"))
    assert stats["metrics"]["wer"]["methods"][0]["wins"] == 2
    assert "Análise Estatística" in (results_dir / "report.html").read_text(encoding="utf-8")


def test_cli_analyze_custom_output_and_threshold(tmp_path):
    src = tmp_path / "results.json"
    write_json(dataset({"a": [0.3]}, {"a": [0.45]}), src)
    out = tmp_path / "saida"

    result = CliRunner().invoke(
        cli, ["analyze", str(src), "-o", str(out), "--severe-threshold", "0.1"]
    )

    assert result.exit_code == 0, result.output
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats["settings"]["severe_failure_threshold"] == 0.1
    assert stats["metrics"]["wer"]["methods"][0]["severe_failures"] == 1
    assert not (tmp_path / "stats.json").exists()
