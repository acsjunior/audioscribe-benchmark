from collections import defaultdict
from datetime import datetime
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
    .note { color: #64748b; font-size: .8rem; line-height: 1.5; max-width: 100ch; }
    .gain-pos { color: #15803d; font-weight: 600; }
    .gain-neg { color: #b91c1c; font-weight: 600; }
    td.num, th.num { text-align: right; white-space: nowrap; }
  </style>
</head>
<body>
  {% macro num(x) %}{% if x is none %}—{% else %}{{ "%.3f" | format(x) }}{% endif %}{% endmacro %}
  {% macro gain(x) %}{% if x is none %}—{% else %}{{ "%+.3f" | format(x) }}{% endif %}{% endmacro %}
  {% macro ci(c) %}{% if c %}[{{ "%+.3f" | format(c[0]) }}; {{ "%+.3f" | format(c[1]) }}]{% else %}—{% endif %}{% endmacro %}
  {% macro sig(s) %}{% if s > 0 %}gain-pos{% elif s < 0 %}gain-neg{% endif %}{% endmacro %}
  <h1>AudioScribe Benchmark</h1>
  <div class="meta">
    Experimento: <strong>{{ experiment_name }}</strong> &nbsp;·&nbsp;
    Gerado em: {{ generated_at }} &nbsp;·&nbsp;
    Músicas: {{ num_songs }} &nbsp;·&nbsp;
    Rodadas: {{ num_runs }} &nbsp;·&nbsp;
    Experimentos: {{ num_experiments }}
  </div>

  <h2>Ranking por Combinação</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Provedor / Modelo</th><th>Prompt</th>
        {% for m in metric_names %}<th>{{ m | upper }}</th>{% endfor %}
        <th>Músicas</th><th>Avaliações</th>
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
        <td>{{ row.num_evaluations }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% if analysis %}
  <h2>Análise Estatística</h2>
  <p class="note">
    Cada método é comparado com o baseline <strong>da mesma música e rodada</strong>
    (mesma transcrição de partida). O <strong>ganho</strong> é positivo quando o método
    melhora a métrica e é calculado por música (média das rodadas). Os intervalos
    ({{ "%.0f" | format(analysis.settings.confidence * 100) }}%) vêm de bootstrap
    sobre as músicas; em verde/vermelho, quando o intervalo exclui o zero.
    <strong>Falha grave</strong>: avaliação em que o método piora a métrica em mais de
    {{ "%.2f" | format(analysis.settings.severe_failure_threshold) }} em relação ao baseline.
    <strong>Ganho típico (HL)</strong>: estimativa de Hodges–Lehmann, a que corresponde ao
    teste de Wilcoxon (postos sinalizados, zeros pelo método de Pratt, bilateral); ao lado,
    o p-valor ajustado por Holm entre os métodos desta tabela. O teste do sinal acompanha
    melhorou/empatou/piorou. <strong>Δ WER do corpus</strong>: erros totais ÷ palavras
    totais, com bootstrap pareado — ao contrário do ganho típico, enxerga o tamanho de uma
    falha catastrófica. Estas comparações são exploratórias; as hipóteses confirmatórias
    são testadas com <code>benchmark confirm</code>.
  </p>
  {% for metric, ma in analysis.metrics.items() %}
  <h3>{{ metric | upper }} — {{ "menor é melhor" if ma.direction == "lower" else "maior é melhor" }}</h3>
  <p class="note">
    Baseline: média {{ num(ma.baseline.mean) }} · mediana {{ num(ma.baseline.median) }}
    · desvio entre músicas {{ num(ma.baseline.std_between_songs) }}
    {% if ma.baseline.mean_std_between_runs is not none %}
    · variação entre rodadas (desvio médio por música) {{ num(ma.baseline.mean_std_between_runs) }}
    {% endif %}
    · {{ ma.baseline.num_songs }} músicas
  </p>
  {% if ma.methods %}
  <table>
    <thead>
      <tr>
        <th>Método</th><th>Prompt</th><th class="num">Músicas</th>
        <th class="num">Média</th><th class="num">Mediana</th>
        <th class="num">Ganho médio [IC]</th><th class="num">Ganho típico HL [IC]</th>
        <th class="num">Melhorou / empatou / piorou (p sinal)</th>
        <th class="num">p Wilcoxon (Holm)</th><th class="num">Δ WER corpus [IC]</th>
        <th class="num">Falhas graves</th><th>Pior caso</th>
      </tr>
    </thead>
    <tbody>
      {% for m in ma.methods %}
      <tr>
        <td>{{ m.provider }}/{{ m.model }}</td>
        <td>{{ m.prompt or "—" }}</td>
        <td class="num">{{ m.num_songs }}</td>
        <td class="num">{{ num(m.mean) }}</td>
        <td class="num">{{ num(m.median) }}</td>
        <td class="num {{ sig(m.gain_mean_sig) }}">{{ gain(m.gain_mean) }} {{ ci(m.gain_mean_ci) }}</td>
        <td class="num {{ sig(m.gain_hl_sig) }}">{{ gain(m.gain_hl) }} {{ ci(m.gain_hl_ci) }}</td>
        <td class="num">{{ m.wins }} / {{ m.ties }} / {{ m.losses }}{% if m.sign_test_p is not none %} ({{ "%.4f" | format(m.sign_test_p) }}){% endif %}</td>
        <td class="num">{% if m.wilcoxon_p is none %}—{% else %}{{ "%.4f" | format(m.wilcoxon_p) }} ({{ "%.4f" | format(m.wilcoxon_p_holm) }}){% endif %}</td>
        <td class="num {% if m.corpus %}{{ sig(m.corpus.gain_sig) }}{% endif %}">{% if m.corpus %}{{ gain(m.corpus.gain) }} {{ ci(m.corpus.gain_ci) }}{% else %}—{% endif %}</td>
        <td class="num">{{ m.severe_failures }} ({{ "%.1f" | format(m.severe_failure_rate * 100) }}%{% if m.severe_failure_rate_ci %}; IC {{ "%.0f" | format(m.severe_failure_rate_ci[0] * 100) }}–{{ "%.0f" | format(m.severe_failure_rate_ci[1] * 100) }}%{% endif %})</td>
        <td>{% if m.worst_cases %}{{ m.worst_cases[0].song_id }} ({{ gain(m.worst_cases[0].gain) }}){% else %}—{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="note">Nenhum método de refinamento para comparar com o baseline.</p>
  {% endif %}

  <p class="note">Distribuição sobre as músicas (valor de cada música = média das rodadas).
    Para os métodos, também a distribuição do <strong>ganho</strong> contra o baseline.</p>
  <table>
    <thead>
      <tr>
        <th>Método</th><th>Prompt</th><th>Grandeza</th>
        <th class="num">Média</th><th class="num">Desvio padrão</th><th class="num">Mín</th>
        <th class="num">Q1</th><th class="num">Mediana (Q2)</th><th class="num">Q3</th><th class="num">Máx</th>
      </tr>
    </thead>
    <tbody>
      {% set d = ma.baseline.distribution %}
      <tr>
        <td>baseline</td><td>—</td><td>{{ metric | upper }}</td>
        <td class="num">{{ num(d.mean) }}</td><td class="num">{{ num(d.std) }}</td><td class="num">{{ num(d.min) }}</td>
        <td class="num">{{ num(d.q1) }}</td><td class="num">{{ num(d.median) }}</td><td class="num">{{ num(d.q3) }}</td><td class="num">{{ num(d.max) }}</td>
      </tr>
      {% for m in ma.methods %}
      {% for label, d in [(metric | upper, m.distribution), ("ganho", m.gain_distribution)] %}
      <tr>
        <td>{{ m.provider }}/{{ m.model }}</td><td>{{ m.prompt or "—" }}</td><td>{{ label }}</td>
        <td class="num">{{ num(d.mean) }}</td><td class="num">{{ num(d.std) }}</td><td class="num">{{ num(d.min) }}</td>
        <td class="num">{{ num(d.q1) }}</td><td class="num">{{ num(d.median) }}</td><td class="num">{{ num(d.q3) }}</td><td class="num">{{ num(d.max) }}</td>
      </tr>
      {% endfor %}
      {% endfor %}
    </tbody>
  </table>
  {% endfor %}

  {% if analysis.errors and analysis.errors.methods %}
  <h2>Diagnóstico de Erros</h2>
  <p class="note">
    O WER decomposto sobre as palavras da letra: <strong>substituições</strong> +
    <strong>omissões</strong> + <strong>inserções</strong> = WER (médias por música).
    A <strong>razão de comprimento</strong> é palavras da transcrição / palavras da letra
    (mediana entre músicas). Alertas por avaliação: <em>WER 0</em> (suspeito em
    gravação antiga), <em>curta</em> (razão &lt; {{ analysis.errors.length_ratio_min }},
    trechos omitidos) e <em>longa</em> (razão &gt; {{ analysis.errors.length_ratio_max }},
    trechos inventados ou repetidos).
  </p>
  <table>
    <thead>
      <tr>
        <th>Método</th><th>Prompt</th><th class="num">Músicas</th>
        <th class="num">Substituições</th><th class="num">Omissões</th><th class="num">Inserções</th>
        <th class="num">Razão de comprimento</th>
        <th class="num">WER 0</th><th class="num">Curtas</th><th class="num">Longas</th>
        <th>Caso mais extremo</th>
      </tr>
    </thead>
    <tbody>
      {% for m in analysis.errors.methods %}
      <tr>
        <td>{% if m.provider %}{{ m.provider }}/{{ m.model }}{% else %}baseline{% endif %}</td>
        <td>{{ m.prompt or "—" }}</td>
        <td class="num">{{ m.num_songs }}</td>
        <td class="num">{{ num(m.sub_rate) }}</td>
        <td class="num">{{ num(m.del_rate) }}</td>
        <td class="num">{{ num(m.ins_rate) }}</td>
        <td class="num">{{ num(m.length_ratio_median) }}</td>
        <td class="num">{{ m.alerts.wer_zero }}</td>
        <td class="num">{{ m.alerts.curta }}</td>
        <td class="num">{{ m.alerts.longa }}</td>
        <td>{% if m.flagged %}{{ m.flagged[0].song_id }} (razão {{ num(m.flagged[0].length_ratio) }}){% else %}—{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if analysis.verification and analysis.verification.methods %}
  <h2>Conferência com Áudio: Alterações</h2>
  <p class="note">
    Cada alteração aplicada é testada <strong>sozinha</strong> sobre o rascunho:
    <strong>útil</strong> se reduz o WER contra a letra, <strong>prejudicial</strong> se
    aumenta. <strong>Falhas</strong> (bloqueio do provedor, resposta mal formada) saem da
    análise pareada acima e só aparecem aqui. <strong>Reescritas</strong>: avaliações em
    que mais de {{ "%.0f" | format(analysis.verification.max_change_fraction * 100) }}%
    das palavras do rascunho mudaram.
  </p>
  <table>
    <thead>
      <tr>
        <th>Variante</th><th class="num">Avaliações</th>
        <th class="num">Falhas (bloqueio / formato / outras)</th>
        <th class="num">Sem alteração</th>
        <th class="num">Propostas / aplicadas</th>
        <th class="num">Úteis / neutras / prejudiciais</th>
        <th class="num">Reescritas</th><th>Principal motivo de rejeição</th>
      </tr>
    </thead>
    <tbody>
      {% for m in analysis.verification.methods %}
      <tr>
        <td>{{ m.model }} — {{ m.prompt }}</td>
        <td class="num">{{ m.num_evaluations }}</td>
        <td class="num">{{ m.num_failures }} ({{ m.failures.blocked }} / {{ m.failures.malformed }} / {{ m.failures.other }})</td>
        <td class="num">{{ m.no_edit_responses }}</td>
        <td class="num">{{ m.edits_proposed }} / {{ m.edits_applied }}</td>
        <td class="num">{{ m.edits_helpful }} / {{ m.edits_neutral }} / {{ m.edits_harmful }}</td>
        <td class="num">{{ m.rewrite_alerts }}</td>
        <td>{% if m.rejection_reasons %}{{ (m.rejection_reasons | list)[0] }}{% else %}—{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
  {% endif %}

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
        <td>{% if r.error %}<span class="error-cell">ERRO: {{ r.error }}</span>{% else %}{{ r.experiment_label }}{% endif %}{% if multi_run %} · rodada {{ r.run }}{% endif %}</td>
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

  <h2>Comparação de Transcrições</h2>
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
      <div class="cmp-body">{{ entry.text | e | replace("\n", "<br>") }}</div>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</body>
</html>"""


def _build_comparison(
    by_song: dict[str, list[ExperimentResult]], multi_run: bool = False
) -> dict[str, dict]:
    comparison: dict[str, dict] = {}
    for song_id, song_results in by_song.items():
        ground_truth = song_results[0].ground_truth
        entries = []
        for r in song_results:
            text = r.refined_transcription if r.refined_transcription else r.whisper_transcription
            label = f"{r.experiment_label} · rodada {r.run}" if multi_run else r.experiment_label
            entries.append({"label": label, "text": text})
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
            "num_songs": len({r.song_id for r in combo_results}),
            "num_evaluations": len(combo_results),
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


def write_html(
    results: list[ExperimentResult],
    output_path: Path,
    experiment_name: str,
    analysis: dict | None = None,
) -> None:
    if not results:
        return

    metric_names = list(results[0].metrics.keys())
    by_song: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        by_song[r.song_id].append(r)

    num_runs = max(r.run for r in results)
    multi_run = num_runs > 1

    ranking = _build_ranking(results, metric_names)
    comparison = _build_comparison(dict(by_song), multi_run=multi_run)

    html = Template(_TEMPLATE).render(
        experiment_name=experiment_name,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        num_songs=len(by_song),
        num_runs=num_runs,
        multi_run=multi_run,
        num_experiments=len(results),
        metric_names=metric_names,
        ranking=ranking,
        analysis=analysis,
        by_song=dict(by_song),
        comparison=comparison,
    )

    output_path.write_text(html, encoding="utf-8")
