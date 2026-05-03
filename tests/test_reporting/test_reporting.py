import csv
import json

from benchmark.models import ExperimentResult
from benchmark.reporting.csv_reporter import write_csv
from benchmark.reporting.html_reporter import write_html
from benchmark.reporting.json_reporter import write_json


def make_result(provider=None, prompt="minimalist", wer=0.3, cer=0.2) -> ExperimentResult:
    return ExperimentResult(
        song_id="cartola-as-rosas-nao-falam",
        artista="Cartola",
        titulo="As Rosas Não Falam",
        ano="1976",
        album="Cartola",
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


def test_write_json(tmp_path):
    results = [make_result(provider="openai")]
    out = tmp_path / "results.json"
    write_json(results, out)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["song_id"] == "cartola-as-rosas-nao-falam"
    assert data[0]["metrics"]["wer"] == 0.3


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


def test_write_html_empty(tmp_path):
    out = tmp_path / "report.html"
    write_html([], out, "vazio")
    assert not out.exists()
