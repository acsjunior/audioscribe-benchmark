import json

import pytest
import yaml
from click.testing import CliRunner

from benchmark.cli import cli
from benchmark.models import ExperimentResult
from benchmark.reporting.contrasts import ContrastsConfig, load_contrasts, run_contrasts
from benchmark.reporting.json_reporter import write_json

TRUTH = " ".join(f"w{i}" for i in range(10))


def row(song, run, text, provider=None, prompt=None, error=None, wer=None):
    from benchmark.reporting.errors import diagnose

    r = ExperimentResult(
        song_id=song, titulo="", autoria="", interpretacao="", disco="", ano="", genero="",
        whisper_transcription=text if provider is None else "x",
        refinement_provider=provider, refinement_model="m" if provider else None,
        prompt_name=prompt, prompt_file=None,
        refined_transcription=text if provider else None,
        ground_truth=TRUTH, run=run, error=error,
    )
    if not error:
        r.metrics = {"wer": wer if wer is not None else diagnose(text, TRUTH)["wer"]}
    return r


def errs(k):
    """Texto com k palavras trocadas."""
    words = TRUTH.split()
    return " ".join("x" if i < k else w for i, w in enumerate(words))


@pytest.fixture
def results_file(tmp_path):
    rows = []
    for i in range(12):
        s = f"s{i}"
        rows += [
            row(s, 1, errs(3)),                                   # baseline
            row(s, 1, errs(1), provider="openai", prompt="bom"),  # melhora sempre
            row(s, 1, errs(3), provider="openai", prompt="igual"),  # empata
        ]
    rows.append(row("s0", 2, errs(3)))
    rows.append(row("s0", 2, "", provider="openai", prompt="bom", error="BlockedResponseError: x"))
    path = tmp_path / "results.json"
    write_json(rows, path)
    return str(path)


def _config(results, **extra):
    return ContrastsConfig(**{
        "analysis": {"bootstrap_samples": 500},
        "contrasts": [
            {"name": "H1", "reference": {"results": results, "method": "baseline"},
             "treatment": {"results": results, "method": "openai/m [bom]"}},
            {"name": "H2", "after": "H1",
             "reference": {"results": results, "method": "openai/m [igual]"},
             "treatment": {"results": results, "method": "openai/m [bom]"}},
        ],
        **extra,
    })


def test_gate_open_tests_children(results_file):
    out = run_contrasts(_config(results_file))
    h1, h2 = out["contrasts"]
    assert h1["rejected"]
    assert h1["gain_hl"] == pytest.approx(0.2)
    assert h1["ci_excludes_zero"]
    assert h1["corpus"]["gain"] == pytest.approx(0.2)
    assert h1["treatment_failures"] == 1
    assert h2["tested"]
    assert h2["rejected"]


def test_gate_closed_skips_children(results_file):
    cfg = _config(results_file)
    cfg.contrasts[0].treatment.method = "openai/m [igual]"
    h1, h2 = run_contrasts(cfg)["contrasts"]
    assert not h1["rejected"]
    assert h1["wilcoxon_p"] is None  # tudo empata
    assert not h2["tested"]
    assert not h2["rejected"]


def test_failures_as_draft_sensitivity(results_file):
    excl = run_contrasts(_config(results_file))["contrasts"][0]
    draft = run_contrasts(_config(results_file, failures="draft"))["contrasts"][0]
    # s0: rodada 2 falhou; como rascunho, vale o baseline (ganho 0 nessa rodada)
    assert excl["gain_distribution"]["min"] == pytest.approx(0.2)
    assert draft["gain_distribution"]["min"] == pytest.approx(0.1)


def test_unknown_method_lists_available(results_file):
    cfg = _config(results_file)
    cfg.contrasts[0].treatment.method = "nao existe"
    with pytest.raises(ValueError, match="Disponíveis"):
        run_contrasts(cfg)


def test_config_validation():
    side = {"results": "r.json", "method": "baseline"}
    with pytest.raises(ValueError, match="repetidos"):
        ContrastsConfig(contrasts=[{"name": "H1", "reference": side, "treatment": side}] * 2)
    with pytest.raises(ValueError, match="primeira família"):
        ContrastsConfig(contrasts=[
            {"name": "H1", "reference": side, "treatment": side},
            {"name": "H2", "after": "H9", "reference": side, "treatment": side},
        ])


def test_cli_confirm(results_file, tmp_path):
    cfg = _config(results_file).model_dump()
    path = tmp_path / "hipoteses.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    assert load_contrasts(path).alpha == 0.05

    result = CliRunner().invoke(cli, ["confirm", str(path)])

    assert result.exit_code == 0, result.output
    assert "H1: ganho HL +0.2000" in result.output
    assert "REJEITA H0" in result.output
    saved = json.loads((tmp_path / "hipoteses.json").read_text(encoding="utf-8"))
    assert [c["name"] for c in saved["contrasts"]] == ["H1", "H2"]


def test_criteria_and_confirmation(results_file):
    h1, h2 = run_contrasts(_config(results_file))["contrasts"]
    assert h1["criteria"] == {"test": True, "effect_ci_above_zero": True, "no_net_harm": True}
    assert h1["confirmed"]
    assert h1["severe_loss_rate"] == 0
    assert h1["severe_loss_rate_ci"][0] == 0
    assert 0 < h1["severe_loss_rate_ci"][1] < 0.4


def test_net_harm_blocks_confirmation(tmp_path):
    rows = []
    junk = TRUTH + " lixo" * 100  # 100 inserções numa letra de 10 palavras
    for i in range(60):  # melhora pequena em 60 músicas...
        rows += [row(f"s{i}", 1, errs(2)), row(f"s{i}", 1, errs(1), provider="openai", prompt="t")]
    for i in range(60, 66):  # ...e destrói 6
        rows += [row(f"s{i}", 1, errs(0)), row(f"s{i}", 1, junk, provider="openai", prompt="t")]
    path = tmp_path / "r.json"
    write_json(rows, path)
    cfg = ContrastsConfig(
        analysis={"bootstrap_samples": 500},
        contrasts=[{"name": "H1", "reference": {"results": str(path), "method": "baseline"},
                    "treatment": {"results": str(path), "method": "openai/m [t]"}}],
    )
    (h1,) = run_contrasts(cfg)["contrasts"]
    assert h1["rejected"]  # o teste vê a música típica melhorar...
    assert not h1["criteria"]["no_net_harm"]  # ...mas o total de erros piora
    assert not h1["confirmed"]
