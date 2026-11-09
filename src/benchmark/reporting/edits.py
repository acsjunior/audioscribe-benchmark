"""Auditoria das alterações da conferência com áudio (E7).

Para cada variante de conferência:

- **falhas**: avaliações com erro, separadas em bloqueio do provedor
  (``BlockedResponseError``), resposta mal formada (``EditParseError``) e outras. Elas
  saem da análise pareada, por isso a taxa precisa ser vista aqui;
- **alterações** propostas, aplicadas e rejeitadas (com os motivos), e quantas
  respostas foram "nenhuma alteração";
- **precisão por alteração**: cada alteração aplicada é testada sozinha sobre o
  rascunho; ela é *útil* se reduz o WER contra a letra, *prejudicial* se aumenta e
  *neutra* se não muda. Isso mostra se o verificador erra por mexer demais ou por
  mexer mal;
- **alerta de reescrita**: avaliações em que mais de ``max_change_fraction`` das
  palavras do rascunho mudaram (o verificador deveria fazer correções pontuais).
"""

from collections import Counter, defaultdict

from ..config.schema import AnalysisConfig
from ..consensus import edit_distance
from ..models import ExperimentResult
from ..verification.edits import Edit, apply_edits
from .errors import diagnose

TOLERANCE = 1e-9
MAX_FLAGGED = 10


def is_verification(result: ExperimentResult) -> bool:
    return (result.refinement_provider or "").startswith("verify:")


def _failure_kind(error: str) -> str:
    if error.startswith("BlockedResponseError"):
        return "blocked"
    if error.startswith("EditParseError"):
        return "malformed"
    return "other"


def _edit_effects(result: ExperimentResult) -> Counter:
    v = result.verification
    base = diagnose(v["draft"], result.ground_truth)
    effects: Counter = Counter()
    if base is None:
        return effects
    fields = ("op", "segment", "old", "new", "heard")
    for e in v["edits"]:
        if not e["applied"]:
            continue
        edit = Edit(**{k: e[k] for k in fields})
        text, _ = apply_edits(v["segments"], [edit])
        delta = diagnose(text, result.ground_truth)["wer"] - base["wer"]
        effects["helpful" if delta < -TOLERANCE else "harmful" if delta > TOLERANCE
                else "neutral"] += 1
    return effects


def _summary(rows: list[ExperimentResult], config: AnalysisConfig) -> dict:
    failures = Counter(_failure_kind(r.error) for r in rows if r.error)
    ok = [r for r in rows if not r.error and r.verification]

    proposed = applied = no_edits = 0
    reasons: Counter = Counter()
    effects: Counter = Counter()
    flagged = []
    for r in ok:
        v = r.verification
        proposed += len(v["edits"])
        applied += v["num_applied"]
        no_edits += not v["edits"]
        reasons.update(e["reason"] for e in v["edits"] if not e["applied"])
        effects += _edit_effects(r)
        n_draft = len(v["draft"].split())
        change = edit_distance(v["draft"], r.evaluated_transcription) / max(n_draft, 1)
        if change > config.max_change_fraction:
            flagged.append({"song_id": r.song_id, "run": r.run, "change_fraction": change})

    total = len(rows)
    tested = sum(effects.values())
    flagged.sort(key=lambda f: f["change_fraction"], reverse=True)
    return {
        "num_evaluations": total,
        "num_failures": sum(failures.values()),
        "failure_rate": sum(failures.values()) / total if total else 0.0,
        "failures": {k: failures.get(k, 0) for k in ("blocked", "malformed", "other")},
        "no_edit_responses": no_edits,
        "edits_proposed": proposed,
        "edits_applied": applied,
        "edits_rejected": proposed - applied,
        "rejection_reasons": dict(reasons.most_common()),
        "edits_helpful": effects["helpful"],
        "edits_harmful": effects["harmful"],
        "edits_neutral": effects["neutral"],
        "helpful_rate": effects["helpful"] / tested if tested else None,
        "harmful_rate": effects["harmful"] / tested if tested else None,
        "rewrite_alerts": len(flagged),
        "flagged": flagged[:MAX_FLAGGED],
    }


def analyze_edits(results: list[ExperimentResult], config: AnalysisConfig) -> dict:
    groups: dict[tuple[str, str, str], list[ExperimentResult]] = defaultdict(list)
    for r in results:
        if is_verification(r):
            groups[(r.refinement_provider, r.refinement_model or "", r.prompt_name or "")].append(r)
    methods = [
        {"provider": p, "model": m, "prompt": n, **_summary(rows, config)}
        for (p, m, n), rows in sorted(groups.items())
    ]
    return {"max_change_fraction": config.max_change_fraction, "methods": methods}
