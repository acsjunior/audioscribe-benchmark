from benchmark.config.schema import AnalysisConfig
from benchmark.models import ExperimentResult
from benchmark.reporting.edits import analyze_edits
from benchmark.reporting.stats import analyze
from benchmark.verification.edits import Edit, EditOutcome, apply_edits
from benchmark.verification.segments import segment

TRUTH = "ele está dançando na corda bamba toca cuíca toca surdo e tamborim"
DRAFT = "ele está dançando na porta-bamba, toca cuíca, toca sulto e tamborim"


def _verified(edits, run=1, song="s1"):
    segs = segment(DRAFT)
    text, outcomes = apply_edits(segs, edits)
    return ExperimentResult(
        song_id=song, titulo="", autoria="", interpretacao="", disco="", ano="", genero="",
        whisper_transcription=DRAFT, refinement_provider="verify:openai-audio",
        refinement_model="gpt-audio", prompt_name="edits_v1 · áudio=original",
        prompt_file=None, refined_transcription=text, ground_truth=TRUTH, run=run,
        metrics={"wer": 0.0},
        verification={
            "draft": DRAFT, "segments": segs, "draft_kind": "run", "audio": "original",
            "metadata": False, "num_applied": sum(o.applied for o in outcomes),
            "edits": [o.to_dict() for o in outcomes],
        },
    )


def _failed(error, run):
    r = _verified([], run=run)
    r.verification = None
    r.refined_transcription = None
    r.error = error
    return r


def test_edit_effects_and_failures():
    results = [
        _verified([
            Edit("replace", 1, "sulto", "surdo"),          # útil
            Edit("replace", 1, "tamborim", "tamboril"),    # prejudicial
            Edit("replace", 1, "naoexiste", "x"),          # rejeitada
        ]),
        _verified([], run=2),
        _failed("BlockedResponseError: bloqueou", 3),
        _failed("EditParseError: JSON inválido", 4),
    ]
    (m,) = analyze_edits(results, AnalysisConfig())["methods"]
    assert m["num_evaluations"] == 4
    assert m["failures"] == {"blocked": 1, "malformed": 1, "other": 0}
    assert m["failure_rate"] == 0.5
    assert m["no_edit_responses"] == 1
    assert (m["edits_proposed"], m["edits_applied"], m["edits_rejected"]) == (3, 2, 1)
    assert (m["edits_helpful"], m["edits_harmful"], m["edits_neutral"]) == (1, 1, 0)
    assert m["rejection_reasons"] == {"trecho não encontrado no segmento": 1}


def test_rewrite_alert():
    r = _verified([Edit("delete", 1, "toca cuíca, toca sulto e tamborim")])
    (m,) = analyze_edits([r], AnalysisConfig(max_change_fraction=0.3))["methods"]
    assert m["rewrite_alerts"] == 1
    assert m["flagged"][0]["change_fraction"] > 0.3


def test_stats_include_verification_only_for_verify_rows():
    out = analyze([_verified([])], ["wer"], AnalysisConfig())
    assert len(out["verification"]["methods"]) == 1
    assert isinstance(EditOutcome(Edit("insert", 0, new="x"), True).to_dict(), dict)
