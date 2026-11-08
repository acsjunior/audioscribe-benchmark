import csv
import json

from benchmark.models import ExperimentResult
from benchmark.reporting.csv_reporter import write_csv
from benchmark.reporting.html_reporter import _build_comparison, _build_ranking, write_html
from benchmark.reporting.json_reporter import write_json


def make_result(provider=None, prompt="minimalist", wer=0.3, cer=0.2) -> ExperimentResult:
    return ExperimentResult(
        song_id="cartola-as-rosas-nao-falam",
        titulo="As Rosas Não Falam",
        autoria="Cartola",
        interpretacao="Cartola",
        disco="Cartola",
        ano="1976",
        genero="Samba",
        whisper_transcription="as rosas nao falam",
        refinement_provider=provider,
        refinement_model="gpt-4o" if provider else None,
        prompt_name=prompt if provider else None,
        prompt_file=f"prompts/{prompt}.yaml" if provider else None,
        refined_transcription="As rosas não falam" if provider else None,
        ground_truth="As rosas não falam",
        metrics={"wer": wer, "cer": cer},
        tokens_used=80 if provider else None,
        response_time_ms=500.0 if provider else None,
    )


# --- CSV ---

def test_write_csv(tmp_path):
    results = [make_result(), make_result(provider="openai")]
    out = tmp_path / "results.csv"
    write_csv(results, out)

    assert out.exists()
    rows = list(csv.DictReader(out.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 2
    assert "wer" in rows[0]
    assert rows[0]["refinement_provider"] == "baseline"
    assert rows[1]["refinement_provider"] == "openai"


def test_write_csv_empty(tmp_path):
    out = tmp_path / "results.csv"
    write_csv([], out)
    assert not out.exists()


# --- JSON ---

def test_write_json(tmp_path):
    results = [make_result(provider="openai")]
    out = tmp_path / "results.json"
    write_json(results, out)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["song_id"] == "cartola-as-rosas-nao-falam"
    assert data[0]["metrics"]["wer"] == 0.3


# --- HTML ---

def test_write_html(tmp_path):
    results = [make_result(), make_result(provider="openai")]
    out = tmp_path / "report.html"
    write_html(results, out, "experimento-01")

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "AudioScribe Benchmark" in content
    assert "experimento-01" in content
    assert "Ranking" in content
    assert "Cartola" in content
    assert "Comparação de Transcrições" in content


def test_write_html_empty(tmp_path):
    out = tmp_path / "report.html"
    write_html([], out, "vazio")
    assert not out.exists()


# --- _build_comparison ---

def test_build_comparison_structure():
    results = [make_result(), make_result(provider="openai")]
    by_song = {"cartola-as-rosas-nao-falam": results}
    comparison = _build_comparison(by_song)

    assert "cartola-as-rosas-nao-falam" in comparison
    song = comparison["cartola-as-rosas-nao-falam"]
    assert song["titulo"] == "As Rosas Não Falam"
    assert song["ground_truth"] == "As rosas não falam"
    assert len(song["entries"]) == 2
    assert "label" in song["entries"][0]
    assert "text" in song["entries"][0]


def test_build_comparison_baseline_uses_whisper_transcription():
    results = [make_result()]
    by_song = {"cartola-as-rosas-nao-falam": results}
    comparison = _build_comparison(by_song)

    entry = comparison["cartola-as-rosas-nao-falam"]["entries"][0]
    assert entry["text"] == "as rosas nao falam"


def test_build_comparison_refined_uses_refined_transcription():
    results = [make_result(provider="openai")]
    by_song = {"cartola-as-rosas-nao-falam": results}
    comparison = _build_comparison(by_song)

    entry = comparison["cartola-as-rosas-nao-falam"]["entries"][0]
    assert entry["text"] == "As rosas não falam"


# --- Rodadas ---

def _with_run(result, run):
    result.run = run
    return result


def test_write_csv_includes_split_and_run(tmp_path):
    out = tmp_path / "results.csv"
    write_csv([_with_run(make_result(), 1), _with_run(make_result(), 2)], out)

    rows = list(csv.DictReader(out.read_text(encoding="utf-8").splitlines()))
    assert [r["run"] for r in rows] == ["1", "2"]
    assert rows[0]["split"] == "dev"


def test_html_ranking_counts_unique_songs_with_runs(tmp_path):
    results = [_with_run(make_result(), 1), _with_run(make_result(), 2)]
    ranking = _build_ranking(results, ["wer"])

    assert ranking[0]["num_songs"] == 1
    assert ranking[0]["num_evaluations"] == 2


def test_html_labels_runs_when_multiple(tmp_path):
    out = tmp_path / "report.html"
    write_html([_with_run(make_result(), 1), _with_run(make_result(), 2)], out, "exp")

    content = out.read_text(encoding="utf-8")
    assert "rodada 2" in content
    assert "Rodadas: 2" in content


def test_html_no_run_label_with_single_run(tmp_path):
    out = tmp_path / "report.html"
    write_html([make_result()], out, "exp")

    assert "rodada 1" not in out.read_text(encoding="utf-8")
