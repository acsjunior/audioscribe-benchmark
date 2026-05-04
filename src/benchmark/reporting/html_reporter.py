import html as html_lib
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from jinja2 import Template

from ..models import ExperimentResult

_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>AudioScribe Benchmark — {{ experiment_name }}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 2rem; background: #f8fafc; color: #1e293b; }
    h1 { margin-bottom: 0.25rem; }
    h2 { color: #334155; margin-top: 2.5rem; }
    h3 { color: #475569; margin-top: 1.5rem; font-size: 1rem; }
    .meta { color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); margin-bottom: 1.5rem; }
    th { background: #1e293b; color: white; padding: .65rem 1rem; text-align: left; font-size: .8rem; font-weight: 600; white-space: nowrap; }
    td { padding: .6rem 1rem; border-bottom: 1px solid #e2e8f0; font-size: .82rem; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f1f5f9; }
    .rank-1 td { background: #fef9c3; font-weight: 600; }
    .rank-2 td { background: #f0fdf4; }
    .rank-3 td { background: #eff6ff; }
    .baseline { color: #94a3b8; font-style: italic; }
    .error-cell { color: #ef4444; font-size: .78rem; }
    .cmp-grid { display: flex; gap: 1rem; overflow-x: auto; margin-bottom: 2rem; padding-bottom: .5rem; }
    .cmp-col { flex: 0 0 260px; background: white; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .cmp-header { font-weight: 600; font-size: .75rem; color: #334155; margin-bottom: .5rem; padding-bottom: .5rem; border-bottom: 1px solid #e2e8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cmp-header.gt { color: #0f766e; }
    .cmp-body { font-size: .78rem; line-height: 1.8; word-break: break-word; }
    .w-ok  { color: #16a34a; }
    .w-err { color: #dc2626; }
  </style>
</head>
<body>
  <h1>AudioScribe Benchmark</h1>
  <div class="meta">
    Experimento: <strong>{{ experiment_name }}</strong> &nbsp;·&nbsp;
    Gerado em: {{ generated_at }} &nbsp;·&nbsp;
    Músicas: {{ num_songs }} &nbsp;·&nbsp;
    Experimentos: {{ num_experiments }}
  </div>

  <h2>Ranking por Combinação</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Provedor / Modelo</th><th>Prompt</th>
        {% for m in metric_names %}<th>{{ m | upper }}</th>{% endfor %}
        <th>Músicas</th>
      </tr>
    </thead>
    <tbody>
      {% for row in ranking %}
      <tr class="{% if loop.index == 1 %}rank-1{% elif loop.index == 2 %}rank-2{% elif loop.index == 3 %}rank-3{% endif %}">
        <td>{{ loop.index }}</td>
        <td>{% if row.provider == "baseline" %}<span class="baseline">baseline (whisper)</span>{% else %}{{ row.provider }}/{{ row.model }}{% endif %}</td>
        <td>{{ row.prompt or "—" }}</td>
        {% for m in metric_names %}
        <td>{% if row.avg_metrics.get(m) is not none %}{{ "%.4f" | format(row.avg_metrics[m]) }}{% else %}—{% endif %}</td>
        {% endfor %}
        <td>{{ row.num_songs }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Resultados por Música</h2>
  {% for song_id, song_results in by_song.items() %}
  <h3>{{ song_results[0].interpretacao }} — {{ song_results[0].titulo }}{% if song_results[0].ano %} ({{ song_results[0].ano }}){% endif %}</h3>
  <table>
    <thead>
      <tr>
        <th>Experimento</th>
        {% for m in metric_names %}<th>{{ m | upper }}</th>{% endfor %}
        <th>Tokens</th><th>Tempo (ms)</th>
      </tr>
    </thead>
    <tbody>
      {% for r in song_results %}
      <tr>
        <td>{% if r.error %}<span class="error-cell">ERRO: {{ r.error }}</span>{% else %}{{ r.experiment_label }}{% endif %}</td>
        {% for m in metric_names %}
        <td>{% if r.metrics.get(m) is not none %}{{ "%.4f" | format(r.metrics[m]) }}{% else %}—{% endif %}</td>
        {% endfor %}
        <td>{{ r.tokens_used if r.tokens_used is not none else "—" }}</td>
        <td>{{ "%.0f" | format(r.response_time_ms) if r.response_time_ms is not none else "—" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endfor %}

  <h2>Comparação Visual de Transcrições</h2>
  <p style="font-size:.82rem;color:#64748b;margin-top:-.5rem">
    <span class="w-ok">■</span> palavra correta &nbsp;
    <span class="w-err">■</span> palavra divergente do ground truth
  </p>
  {% for song_id, song_cmp in comparison.items() %}
  <h3>{{ song_cmp.interpretacao }} — {{ song_cmp.titulo }}{% if song_cmp.ano %} ({{ song_cmp.ano }}){% endif %}</h3>
  <div class="cmp-grid">
    <div class="cmp-col">
      <div class="cmp-header gt">Ground Truth</div>
      <div class="cmp-body">{{ song_cmp.ground_truth | e | replace("\n", "<br>") }}</div>
    </div>
    {% for entry in song_cmp.entries %}
    <div class="cmp-col">
      <div class="cmp-header">{{ entry.label }}</div>
      <div class="cmp-body">{{ entry.diff_html | safe }}</div>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</body>
</html>"""


def _highlight_diff(reference: str, hypothesis: str) -> str:
    """Return hypothesis as HTML with words colored green (match) or red (diverge) vs reference."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()

    if not hyp_words:
        return '<span class="w-err">(vazio)</span>'

    matcher = SequenceMatcher(None, ref_words, hyp_words, autojunk=False)
    parts: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        css = "w-ok" if tag == "equal" else "w-err"
        for word in hyp_words[j1:j2]:
            parts.append(f'<span class="{css}">{html_lib.escape(word)}</span>')

    return " ".join(parts)


def _build_comparison(
    by_song: dict[str, list[ExperimentResult]],
) -> dict[str, dict]:
    comparison: dict[str, dict] = {}
    for song_id, song_results in by_song.items():
        ground_truth = song_results[0].ground_truth
        entries = []
        for r in song_results:
            text = r.refined_transcription if r.refined_transcription else r.whisper_transcription
            entries.append({
                "label": r.experiment_label,
                "diff_html": _highlight_diff(ground_truth, text),
            })
        comparison[song_id] = {
            "interpretacao": song_results[0].interpretacao,
            "titulo": song_results[0].titulo,
            "ano": song_results[0].ano,
            "ground_truth": ground_truth,
            "entries": entries,
        }
    return comparison


def _build_ranking(results: list[ExperimentResult], metric_names: list[str]) -> list[dict]:
    by_combo: dict[tuple, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        key = (r.refinement_provider or "baseline", r.refinement_model or "", r.prompt_name or "")
        by_combo[key].append(r)

    ranking = []
    for (provider, model, prompt), combo_results in by_combo.items():
        avg_metrics: dict[str, float | None] = {}
        for m in metric_names:
            vals = [r.metrics[m] for r in combo_results if r.metrics.get(m) is not None]
            avg_metrics[m] = sum(vals) / len(vals) if vals else None
        ranking.append({
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "avg_metrics": avg_metrics,
            "num_songs": len(combo_results),
        })

    if metric_names:
        primary = metric_names[0]
        reverse = "score" in primary.lower()
        ranking.sort(
            key=lambda x: x["avg_metrics"].get(primary)
            if x["avg_metrics"].get(primary) is not None
            else (float("inf") if not reverse else float("-inf")),
            reverse=reverse,
        )

    return ranking


def write_html(results: list[ExperimentResult], output_path: Path, experiment_name: str) -> None:
    if not results:
        return

    metric_names = list(results[0].metrics.keys())
    by_song: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        by_song[r.song_id].append(r)

    ranking = _build_ranking(results, metric_names)
    comparison = _build_comparison(dict(by_song))

    html = Template(_TEMPLATE).render(
        experiment_name=experiment_name,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        num_songs=len(by_song),
        num_experiments=len(results),
        metric_names=metric_names,
        ranking=ranking,
        by_song=dict(by_song),
        comparison=comparison,
    )

    output_path.write_text(html, encoding="utf-8")
