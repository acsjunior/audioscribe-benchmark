# AudioScribe Benchmark

## Objetivo

Pipeline de benchmark para avaliar a melhor abordagem de transcrição de letras de sambas antigos em português. O pipeline lê um catálogo CSV, baixa os áudios do Google Drive, transcreve via API do Whisper, opcionalmente refina as transcrições com LLMs, e compara os resultados com as letras do catálogo usando métricas de acurácia.

**Domínio específico:** sambas antigos em português — vocabulário arcaico, gírias da época, qualidade de áudio inferior.

**Foco principal:** entender se o refinamento com LLM melhora a acurácia e qual combinação de LLM + prompt produz os melhores resultados nesse contexto.

---

## Contexto de Domínio

Sambas antigos brasileiros das décadas de 1920-1950. Características relevantes para o benchmark:

- Vocabulário arcaico e gírias da época (ex: "batuque", "maxixe", "mufumbo")
- Gravações com qualidade de áudio inferior — ruído, saturação, velocidade variável
- Português coloquial com contrações e regionalismos (ex: "tá", "tô", "num")
- Pronúncia característica da época que pode confundir o Whisper
- Artistas de referência: Cartola, Nelson Cavaquinho, Sinhô, João da Baiana, Francisco Alves, Mário Reis

---

## Stack

| Componente | Escolha |
|---|---|
| Python | 3.11+ |
| Gerenciador de dependências | `uv` + `pyproject.toml` |
| Linting/formatação | `ruff` |
| Testes | `pytest` + mocks para APIs externas |
| Credenciais de API | `.env` via `python-dotenv` |
| Credenciais Google Drive | OAuth2 via `google-auth-oauthlib` |

---

## Estrutura de Diretórios

```
audioscribe-benchmark/
├── CLAUDE.md
├── ROADMAP.md                # plano de entregáveis (E0–E9) rumo ao estudo acadêmico
├── .env.example
├── .gitignore
├── pyproject.toml
├── credentials.json          # OAuth2 do Google Drive (não commitado)
├── token.json                # Token salvo após primeira auth (não commitado)
├── config/
│   └── experiments/
│       └── example.yaml      # modelo de configuração de bateria de testes
├── data/
│   ├── catalogo.csv          # fonte única de verdade: metadados + letras + URLs
│   ├── inputs/               # áudios baixados do Google Drive (não commitados)
│   └── transcriptions/       # cache de transcrições por configuração e rodada (não commitado)
├── prompts/
│   ├── minimalist.yaml
│   ├── conservative.yaml
│   ├── targeted_domain.yaml
│   ├── rich_context.yaml
│   ├── archaic_vocab.yaml
│   └── few_shot.yaml
├── src/
│   └── benchmark/
│       ├── __init__.py
│       ├── models.py             # SongData, ExperimentResult
│       ├── dataset.py            # load_catalog() — lê catalogo.csv
│       ├── gdrive.py             # OAuth2 + download do Google Drive
│       ├── voice_isolation.py    # pré-processamento: demucs (isola a voz)
│       ├── noise_reduction.py    # pré-processamento: noisereduce
│       ├── deep_filter.py        # pré-processamento: DeepFilterNet
│       ├── pipeline.py           # orquestrador principal
│       ├── cli.py                # entrypoint CLI
│       ├── __main__.py           # permite `python -m benchmark`
│       ├── config/
│       │   ├── __init__.py       # load_config()
│       │   └── schema.py         # modelos Pydantic do YAML de configuração
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── base.py           # BaseTranscriber (ABC)
│       │   ├── whisper.py        # WhisperTranscriber (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
│       │   ├── multimodal.py     # GeminiAudioLLM/OpenAIAudioLLM + transcritores multimodais (E6)
│       │   └── cache.py          # TranscriptionCache — cache em disco por configuração/rodada
│       ├── verification/         # conferência com áudio (E7)
│       │   ├── segments.py       # segment(): rascunho → segmentos numerados (determinístico)
│       │   ├── edits.py          # parse_edits(), apply_edits(), EditParseError
│       │   └── verifier.py       # Verifier, load_verification_prompt()
│       ├── refinement/
│       │   ├── __init__.py       # REFINER_REGISTRY, get_refiner()
│       │   ├── base.py           # BaseRefiner, PromptConfig, load_prompt()
│       │   ├── openai.py         # OpenAIRefiner (GPT-4o)
│       │   ├── anthropic.py      # AnthropicRefiner (Claude)
│       │   └── google.py         # GoogleRefiner (Gemini)
│       ├── metrics/
│       │   ├── __init__.py       # METRIC_REGISTRY, get_metrics()
│       │   ├── base.py           # BaseMetric (ABC) + normalize()
│       │   ├── wer.py            # WERMetric
│       │   ├── cer.py            # CERMetric
│       │   └── bertscore.py      # BERTScoreMetric
│       ├── reporting/
│       │   ├── __init__.py
│       │   ├── csv_reporter.py
│       │   ├── json_reporter.py  # write_json() / read_json()
│       │   ├── stats.py          # analyze(): análise pareada contra o baseline (E2)
│       │   ├── errors.py         # analyze_errors(): sub/omissão/inserção e alertas (E4)
│       │   ├── edits.py          # analyze_edits(): falhas, precisão por alteração, reescritas (E7)
│       │   ├── contrasts.py      # run_contrasts(): hipóteses confirmatórias (benchmark confirm)
│       │   └── html_reporter.py  # relatório HTML: ranking, análise estatística, comparações
│       └── utils/
│           ├── __init__.py
│           ├── logging.py        # setup_logging(), modos normal/verbose
│           └── retry.py          # async_retry() com backoff exponencial
├── tests/
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_config/
│   ├── test_dataset.py
│   ├── test_deep_filter.py
│   ├── test_noise_reduction.py
│   ├── test_voice_isolation.py
│   ├── test_metrics/
│   ├── test_models.py
│   ├── test_pipeline.py
│   ├── test_pipeline_runs.py     # rodadas, cache de transcrições, split e stats.json
│   ├── test_refinement/
│   ├── test_reporting/
│   ├── test_transcription/
│   └── test_utils/
├── logs/                         # logs de execução (gerado automaticamente)
└── results/                      # saída de cada execução (gerado automaticamente)
    └── {experimento}_{timestamp}/
        ├── results.csv
        ├── results.json
        ├── stats.json            # análise estatística (ver "Análise Estatística")
        └── report.html
```

---

## Formato do Catálogo

O arquivo `data/catalogo.csv` é a fonte única de verdade do dataset. Colunas esperadas:

| Coluna | Descrição |
|---|---|
| `Música` | Título da música |
| `Autoria` | Compositor(es) |
| `Interpretação` | Intérprete(s) |
| `Acompanhamento` | Conjunto/orquestra (ignorado pelo pipeline) |
| `Disco` | Nome do disco/gravadora e número |
| `Ano` | Ano de gravação |
| `Gênero` | Gênero musical |
| `Letra` | Ground truth — letra completa da música |
| `Arquivo` | Nome do arquivo MP3 no Google Drive |
| `URL` | URL de compartilhamento do Google Drive |
| `Fonte` | URL da fonte da informação (ignorado) |
| `Acesso` | Data de acesso (ignorado) |
| `Split` | Opcional: `dev` ou `test`. Ausente → todas as músicas são `dev`. Presente → todo valor precisa ser `dev` ou `test` (valor vazio ou inválido gera erro) |

Colunas extras são ignoradas pelo pipeline (ex.: colunas de verificação de domínio público).

O `song_id` é gerado automaticamente via slugify: `{interpretacao_slug}-{titulo_slug}`.

---

## Configuração do Experimento (YAML)

```yaml
experiment_name: "experimento-01"

logging:
  mode: normal          # normal | verbose
  output_file: logs/experimento-01.log

retry:
  max_attempts: 3
  backoff_factor: 2.0

transcription:
  provider: whisper
  model: whisper-1      # whisper-1 | gpt-4o-transcribe | gpt-4o-mini-transcribe
  # transcription_prompt: "prompt opcional"  # gpt-4o-transcribe usa prompt padrão se omitido
  # audio_preprocessing: demucs  # demucs | noisereduce | deepfilternet (omitir = sem pré-processamento)
  runs: 1                 # transcrições independentes por música (padrão 1)
  cache: true             # reaproveita transcrições salvas (padrão true)
  # cache_dir: data/transcriptions  # padrão: <pai de drive.audio_dir>/transcriptions

refinement:
  - provider: openai        # openai | anthropic | google
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
    temperature: 0.0        # padrão

metrics:
  - wer
  - cer
  - bertscore

catalog_path: data/catalogo.csv
split: dev                # dev | test | all (padrão dev)

drive:
  credentials_path: credentials.json
  token_path: token.json
  audio_dir: data/inputs    # onde os MP3s são baixados/cacheados

results_path: results
```

---

## Arquitetura e Decisões

### Fluxo do Pipeline
Filtra o catálogo pelo `split` do YAML. Para cada música selecionada:
1. Verifica se o MP3 já existe em `audio_dir` (cache)
2. Se não existe, baixa do Google Drive via API
3. Se `audio_preprocessing` estiver definido, pré-processa o áudio (com cache em `.wav`)
4. Para cada rodada `1..runs`:
   1. Obtém a transcrição do cache ou da API (e salva no cache)
   2. Avalia a transcrição bruta (linha de baseline da rodada)
   3. Para cada configuração de refinamento: refina essa transcrição com o LLM e avalia
5. Ao final, grava CSV, JSON e HTML (cada linha traz `run` e `split`)

Uma falha numa rodada pula só aquela rodada; ela não é salva no cache e é refeita na próxima execução.

### Rodadas e Cache de Transcrições
As transcrições variam entre execuções com a mesma configuração (o WER de uma música chegou a variar 0,30), então cada música pode ser transcrita `runs` vezes. As transcrições ficam em `TranscriptionCache` (`transcription/cache.py`):

```
data/transcriptions/<modelo>__<pré-processamento|original>__<p+hash8 do prompt|noprompt>/
├── config.json              # modelo, prompt efetivo e pré-processamento
└── <song_id>/run_01.json    # texto, run, sha256 do áudio, created_at, ...
```

- A chave usa o **prompt efetivo** (`effective_prompt()` em `whisper.py`, que inclui o prompt padrão do `gpt-4o-transcribe`), então mudar o prompt, o modelo ou o pré-processamento gera um conjunto novo.
- Cada entrada guarda o `sha256` do áudio transcrito. Se o arquivo mudar, a entrada é ignorada e a rodada é retranscrita.
- Aumentar `runs` só transcreve as rodadas que faltam.
- Propósito: comparar métodos de refinamento sobre exatamente as mesmas transcrições, e não pagar transcrição de novo a cada experimento.

### Transcrição de consenso (E5)
`consensus.py`: com `transcription.consensus: true` (exige `runs >= 3`, validado no schema), cada música ganha o método `consensus/medoid`: entre as `n` transcrições, a de menor soma de distâncias de edição em palavras (texto normalizado, `jiwer.process_words`) para as demais; empate → menor rodada. É uma *escolha*, nunca uma fusão, e não usa a letra nem API. O mesmo texto é registrado em cada rodada (para o pareamento música × rodada com o baseline), então o ganho por música é a média sobre as rodadas, mas `num_evaluations` e falhas graves contam `n` vezes. Se menos de 3 rodadas forem válidas na música, o consenso dela é ignorado (aviso no log). Aparece nas tabelas como método sem prompt (`consensus/medoid`).

### Transcrição multimodal direta (E6)
`transcription/multimodal.py`: `transcription.provider` aceita `whisper` (padrão, API de transcrição), `google` (`GeminiTranscriber`, áudio inline via `types.Part.from_bytes`) e `openai-audio` (`OpenAIAudioTranscriber`, Chat Completions com `input_audio`, `modalities=["text"]`; modelos `gpt-audio`, `gpt-audio-mini` — o `gpt-4o-audio-preview` não existe mais na conta). É o **grupo de controle do E7**: separa "modelo que ouve melhor" de "conferir rascunho com o áudio". O prompt padrão (`DEFAULT_MULTIMODAL_PROMPT`) é neutro, **sem título, autoria ou intérprete**, para não permitir acerto por memorização; `transcription_prompt` o substitui, e o prompt efetivo entra na chave do cache. Só `.mp3` e `.wav` (aceitos pelas duas APIs). Bloqueio (`RECITATION`/`SAFETY`/`content_filter`) → `BlockedResponseError`, truncamento → `TruncatedResponseError`, resposta vazia → `RuntimeError`. A saída tem os espaços de fim de linha removidos. Verificado ao vivo só com `gpt-audio` (1 música); o caminho do Gemini está coberto por testes com mock, mas **não foi executado com a API real** (sem `GOOGLE_API_KEY` no `.env`).

### Conferência com áudio (E7)
Bloco `verification:` (lista; uma entrada por variante): `provider` (`openai-audio` | `google`), `model`, `prompt_file` (`prompts/verification/`), `audio` (`original` = MP3 do catálogo, mesmo se a transcrição usou pré-processamento | `isolated` = demucs sobre o original, calculado uma vez por música | `none` = controle só com texto), `metadata` (bool), `draft` (`run` | `consensus`; consenso exige `runs >= 3`, validado no schema), `max_runs` (confere só as N primeiras rodadas).

- **Fluxo** (`verification/`): rascunho → `segment()` (corta em pontuação/fim de linha a partir de 8 palavras, força em 15; os rascunhos do `gpt-4o-transcribe` vêm num parágrafo só) → modelo multimodal com `system` + mensagem (marcadores `{segments}`, `{metadata}`, `{audio_note}` trocados por `str.replace`, porque o prompt contém JSON) → `parse_edits()` → `apply_edits()`.
- **Operações**: `replace`/`delete` (com `old`, que precisa aparecer **uma única vez** no segmento como palavras inteiras) e `insert` (depois do segmento N; 0 = início). Rejeitadas com motivo: segmento inexistente, trecho não encontrado/ambíguo, sem efeito, sobreposta. O modelo nunca reescreve o texto.
- **Resposta mal formada = erro** (`EditParseError`), nunca "nenhuma alteração" (seria um falso empate). "Nenhuma alteração" só com `{"edits": []}` explícito.
- **Resultado**: linha com `refinement_provider = "verify:<provider>"`, `prompt_name = "<prompt> · áudio=… · meta=… · rascunho=…"`, uma por rodada conferida (pareada com o baseline da rodada). Campo `verification` no JSON: rascunho, segmentos, alterações com destino, resposta bruta. CSV: `edits_proposed`, `edits_applied`. Erros gravados como `"<Classe>: mensagem"`.
- **Auditoria** (`reporting/edits.py`, chave `verification` do `stats.json`, seção "Conferência com Áudio" do HTML): falhas por tipo (bloqueio/formato/outras — saem da análise pareada, por isso ficam aqui), respostas sem alteração, propostas/aplicadas/motivos de rejeição, **precisão por alteração** (cada alteração aplicada sozinha sobre o rascunho: útil/neutra/prejudicial pelo WER) e alertas de reescrita (`analysis.max_change_fraction`, padrão 0,3).
- **Comparações do estudo**: conferência vs. baseline; vs. E6 **do mesmo modelo** (efeito de conferir, além de ouvir melhor); vs. `audio: none` (efeito do áudio); com vs. sem metadados (memorização).
- **Teste ao vivo** (`gpt-audio`, 2 músicas, rascunhos antigos): `alcides-gerardi-antonico` WER 0,089 → 0,041 (10 alterações, sem bloqueio); `francisco-alves-que-infeliz-sorte` 0,549 → 0,522. O modelo propôs uma alteração só de pontuação (proibida no prompt), nenhum `delete` no rascunho longo demais, e `heard` sempre "nitidamente X" — não é evidência. Ajustar o prompt no piloto (3 músicas dev) antes da bateria.

### Áudio anônimo
`audio_utils.py::anonymous_audio()` é o único caminho do áudio para as APIs: nome neutro (`audio.mp3`/`audio.wav`; a API de transcrição recebe o nome do arquivo no upload, que seria "Música - Intérprete.mp3") e MP3 sem tags ID3v2/ID3v1 (`strip_id3`). Usado por `WhisperTranscriber` (passa `file=(nome, bytes)`) e pelos clientes multimodais. Metadados só chegam ao modelo via `verification[].metadata: true`. Motivo: o estudo mede memorização comparando com/sem metadados (PROTOCOLO seção 10).

### Fração cantada
`scripts/sung_fraction.py <mp3s>`: estimativa da fração da duração com voz (critério de inclusão, PROTOCOLO 3.2), a partir do `*_vocals.wav` do demucs (gerado se faltar): RMS em janelas de 50 ms, limiar p95 − 20 dB (mostra também 15 e 25), mediana 0,5 s, fecha pausas < 1 s, remove ilhas < 0,5 s. No dev: mediana 66%, mín 34%.

### Simulação de poder
`scripts/power.py <results.json> [--methods ...] [--effects 0.01 0.02 0.04] [--sizes ...] [--exclude-songs ...]`: poder por número de músicas, por reamostragem. Usa o formato dos ganhos por música de métodos medidos (empates exatos mantidos na proporção observada; não nulos centrados no HL de cada método) e soma δ (ganho típico entre músicas alteradas). Critérios: H1 (Wilcoxon-Pratt p < 0,05), H1 confirmada (+ sem dano líquido, aproximado pelo IC normal do ganho médio), H2/H3 (p < 0,025). Resultados preliminares no PROTOCOLO 3.3; refazer com os ganhos do E7 no dev.

### Amostragem (PROTOCOLO 3.3)
`benchmark/sampling.py` + `scripts/sampling_order.py <candidatas.csv> <saida.csv> --seed 20261110 --review data/candidatas/revisao_populacao.csv`. Candidatas: `data/candidatas/discografia_samba_dp_2026-11-10.csv` (db-scraper, 546 linhas; o scraper só pagina com um script externo que passa `_p=N`). População: `genero == "Samba"` exato e ano 1928–1955 (era elétrica), menos as instrumentais confirmadas no arquivo de revisão (`acao=instrumental`; `acao=composicao` força a chave de composição; só valem linhas com `confirmado=sim`). Uma gravação **sorteada** por composição (`composition_key`: título sem parênteses + autores ordenados, normalizados). Ordem aleatória **balanceada por década** (`balanced_order`: em todo prefixo as décadas ficam a menos de 1 da proporção). Posições 1–25 = dev, demais = test. Colunas `status`/`motivo_exclusao` para a conferência. Sem limite por intérprete/autor (amostra proporcional); concentração tratada por sensibilidade (bootstrap por intérprete).

### Split dev/test
A coluna `Split` do catálogo separa as músicas de desenvolvimento (ajuste de prompts e métodos) das de teste (rodadas uma vez, no final, com tudo congelado). O YAML usa `split: dev` por padrão. Rodar o teste exige `split: test` (ou `all`) explicitamente, para evitar contaminação acidental. Ver `ROADMAP.md`.

### Catálogo CSV como Fonte Única
Não há pastas por música nem arquivos `ground_truth.md`. Todos os metadados e letras vivem em `data/catalogo.csv`. Os áudios são baixados sob demanda e cacheados em `data/inputs/`.

### Google Drive — Download com Cache
`gdrive.py` implementa OAuth2 via `google-auth-oauthlib`. Na primeira execução abre o browser para autenticação; o token é salvo em `token.json` e reutilizado automaticamente. O cache é verificado pelo nome do arquivo (coluna `Arquivo` do catálogo) dentro de `audio_dir`. Se o arquivo já existir localmente, o download é ignorado — tanto no pipeline (`pipeline.py`) quanto dentro de `download_audio()` (`gdrive.py`).

### Normalização nas Métricas
`metrics/base.py::normalize` (usada por WER, CER, diagnóstico de erros e consenso), igual para referência e transcrição: minúsculas, apóstrofo removido ("p'ra" → "pra"), pontuação → espaço, espaços colapsados, acentos preservados ("não" vs "nao" continua erro); depois remove as **interjeições** e aplica as **equivalências de grafia** de `metrics/normalization.yaml` ("para o" → "pro", "está" → "tá"…; expressões mais longas primeiro). A lista faz parte do protocolo (PROTOCOLO 4.2/6.2): só variantes sem ambiguidade, e mudá-la muda os resultados. `basic_normalize` faz só a primeira parte.

### Adapter Pattern — Refinamento com LLMs
Cada provedor (OpenAI, Anthropic, Google) tem seu próprio adapter implementando `BaseRefiner`. Adicionar um novo provedor requer apenas criar um novo arquivo em `refinement/` e registrá-lo em `REFINER_REGISTRY`.

### Módulos de Métricas
Cada métrica implementa `BaseMetric` e é registrada em `METRIC_REGISTRY`. Métricas disponíveis: WER, CER, BERTScore.

### Análise Estatística
`reporting/stats.py` compara cada método de refinamento com o baseline de forma **pareada**: a revisão de uma transcrição é comparada com o baseline daquela mesma música e rodada (mesmo texto de partida). Resultado em `stats.json` e na seção "Análise Estatística" do `report.html`.

- **Ganho** = `baseline - método` (WER/CER) ou `método - baseline` (BERTScore; `higher_is_better()` = nome contém "score"). Positivo sempre é melhora.
- **Unidade de análise = música**: o ganho por música é a média do ganho nas rodadas, porque rodadas da mesma música não são independentes.
- Por método: ganho médio, mediano e **Hodges–Lehmann** (`gain_hl`, mediana das médias de Walsh; a estimativa que corresponde ao Wilcoxon), cada um com IC por bootstrap percentil (reamostrando músicas; `seed` fixo → determinístico); melhorou/empatou/piorou com **teste do sinal** (`sign_test_p`, binomial exato); **Wilcoxon bilateral com zeros pelo método de Pratt** (`wilcoxon_p`; antes os empates eram descartados, o que tornava o teste otimista) e ajustes entre os métodos da métrica (`wilcoxon_p_holm`, `wilcoxon_p_bh`, uso exploratório); falhas graves com IC de Clopper–Pearson (`severe_failure_rate_ci`). Métodos ordenados por `gain_hl`.
- **WER do corpus** (`corpus`, só na métrica `wer`): erros totais ÷ palavras totais (recalculados dos textos via `errors.diagnose`, média das rodadas por música), ganho com IC por bootstrap pareado sobre músicas e `prob_improvement` (Bisani & Ney, 2004). Enxerga falhas catastróficas que o ganho típico ignora — nos dados exploratórios, `minimalist` tem HL +0,015 e corpus −0,011.
- Escolha dos testes fundamentada no PROTOCOLO 7.3.
- **Falha grave** = avaliação (música × rodada) com piora maior que `analysis.severe_failure_threshold` (padrão 0,2) — a revisão com LLM costuma melhorar quase todas as músicas e destruir algumas; a média esconde isso, a mediana e a taxa de falhas graves não. `worst_cases` lista as 3 piores.
- `distribution` (baseline e métodos) e `gain_distribution` (métodos): média, desvio padrão, mín, Q1, mediana, Q3, máx sobre as médias por música; tabela de distribuição no HTML.
- Baseline: média, mediana, desvio entre músicas e `mean_std_between_runs` (desvio médio entre rodadas de uma mesma música, o "ruído" da transcrição; `null` com 1 rodada).
- Avaliações com erro ou métrica nula e linhas sem baseline pareado são ignoradas.
- Configuração no YAML: bloco `analysis` (`bootstrap_samples`, `confidence`, `seed`, `severe_failure_threshold`, `length_ratio_min`, `length_ratio_max`). Se a análise falhar, o pipeline registra um aviso e ainda grava CSV/JSON/HTML.
- `benchmark confirm <hipoteses.yaml>` testa as hipóteses confirmatórias (ver abaixo).
- `benchmark analyze <results.json>` refaz `stats.json` e `report.html` a partir de resultados já existentes (inclusive de execuções antigas, sem `run`/`split`).

### Diagnóstico de Erros
`reporting/errors.py` decompõe o WER de cada avaliação (música × rodada × método) sobre as palavras normalizadas (`jiwer.process_words`): substituições + omissões + inserções, divididas pelo nº de palavras da letra (somam o WER). Calculado a partir dos textos em `results.json`, então `benchmark analyze` o gera também para resultados antigos. Sai em `stats.json` (chave `errors`) e na seção "Diagnóstico de Erros" do `report.html`.

- **Razão de comprimento** = palavras da transcrição / palavras da letra (mediana entre músicas): < 1 trechos pulados, > 1 trechos inventados/repetidos.
- **Alertas por avaliação**: `wer_zero` (WER exatamente 0, suspeito em 78 rpm), `curta` (razão < `analysis.length_ratio_min`, padrão 0,7), `longa` (razão > `analysis.length_ratio_max`, padrão 1,3). `flagged` lista até 10 casos por método, os mais distantes de 1.
- Baseline aparece como método sem provedor. Avaliações com erro são ignoradas.

### Respostas bloqueadas
`BlockedResponseError` (em `refinement/base.py`) é levantado quando o provedor bloqueia a resposta: OpenAI `finish_reason=content_filter`, Anthropic `stop_reason=refusal`, Google `SAFETY/RECITATION/BLOCKLIST/PROHIBITED_CONTENT/SPII`. É `NonRetryableError` (`utils/retry.py`): com temperatura 0 o bloqueio se repete, então não há retry. Antes disso a resposta parcial era avaliada como se fosse a revisão — foi a causa da falha de `alcides-gerardi-antonico` na fase exploratória (gpt-4o, filtro de conteúdo/recitação cortava a saída em ~18 palavras; reproduzido 3/3 com `minimalist`).

### Hipóteses confirmatórias (`benchmark confirm`)
`reporting/contrasts.py`: um YAML declara contrastes (`reference`/`treatment` = `{results: <results.json>, method: <rótulo do relatório ou "baseline">}`), `alpha`, `metric`, `failures` (`exclude` | `draft`: falha vira o baseline da mesma música e rodada, análise de sensibilidade) e `analysis`. Pareamento **por música** (média das rodadas de cada lado), então os dois lados podem vir de execuções diferentes (ex.: conferência vs. transcrição direta do E6). **Sequência fixa**: contrastes sem `after` = primeira família (Holm entre eles); `after: X` (X da primeira família) = família testada com Holm só se X for rejeitado, senão `tested: false`. Mesmas medidas do `stats.json` (HL + IC, Wilcoxon-Pratt, sinal, corpus, distribuição, taxa de perdas graves por música com IC de Clopper–Pearson). **Veredito** (`criteria`, `confirmed`): `test` (rejeição com p ajustado), `effect_ci_above_zero` (IC do HL > 0) e `no_net_harm` (limite superior do IC do ganho no WER do corpus ≥ 0); o portão da sequência fixa usa só `test`. Saída: `<yaml>.json` e resumo no terminal.

### Prompts como Arquivos Externos
Prompts definidos em arquivos YAML em `prompts/`. O código nunca hardcoda strings de prompt. Cada experimento registra o caminho e nome do prompt usado para rastreabilidade total.

### Pré-processamento de Áudio
O campo `transcription.audio_preprocessing` aceita um único valor (ou é omitido para não pré-processar):

| Valor | Módulo | Função | Arquivo gerado em `audio_dir` |
|---|---|---|---|
| `demucs` | `voice_isolation.py` | `isolate_voice()` — separa o stem de voz (modelo `htdemucs`) | `<nome>_vocals.wav` |
| `noisereduce` | `noise_reduction.py` | `reduce_noise()` — redução de ruído estacionário | `<nome>_denoised.wav` |
| `deepfilternet` | `deep_filter.py` | `filter_noise()` — supressão de ruído com DeepFilterNet | `<nome>_deepfiltered.wav` |

Todos seguem o mesmo padrão: cache pelo `.wav` gerado (se já existe, não reprocessa); import da biblioteca no nível do módulo dentro de `try/except`, levantando `ImportError` com instrução de instalação se ausente; falha no pré-processamento pula a música (registrada no log) sem derrubar o pipeline. As três bibliotecas estão nas dependências do `pyproject.toml`.

`deep_filter.py` injeta um shim de compatibilidade (`torchaudio.backend.common.AudioMetaData` e `torchaudio.info`) antes de importar `df`, porque o deepfilternet 0.5.x depende de APIs removidas no torchaudio ≥ 2.3.

### Achados dos Experimentos (até 10/05/2026)
- `gpt-4o-transcribe` é o maior ganho: WER baseline ~0,17–0,21 vs ~0,27 do `whisper-1`.
- Refinamento com LLM em geral piora o WER; `conservative` é o único prompt que empata com o baseline.
- Pré-processamento de áudio (demucs, noisereduce, deepfilternet) piorou o baseline em todos os testes — noisereduce e deepfilternet de forma severa.
- O baseline do `gpt-4o-transcribe` varia entre execuções com a mesma config (0,170 vs 0,202 em `gpt4o-transcribe-02`); diferenças pequenas de WER podem ser ruído.

### Metadata nos Prompts
O bloco `user:` dos prompts suporta variáveis `{titulo}`, `{autoria}`, `{interpretacao}`, `{ano}` além de `{transcription}`. O pipeline extrai esses valores do catálogo e os passa para `PromptConfig.format_user()`, que usa `str.format_map(defaultdict(str, ...))` para interpolação segura — variáveis ausentes no template viram string vazia sem KeyError. Isso dá ao LLM contexto de título/artista para ancorar as correções.

### asyncio desde o início
Todo o código de I/O usa `async/await` para permitir adição de concorrência no futuro sem refatoração. A execução atual é sequencial (`asyncio.run()`).

### Resiliência e Detecção de Truncamento
Retry automático com backoff exponencial via `async_retry()`. Falhas isoladas (download, transcrição ou refinamento) nunca derrubam o pipeline — o erro é registrado e a execução continua. Respostas truncadas por limite de tokens levantam `TruncatedResponseError` (detectado via `finish_reason`/`stop_reason` de cada provedor), disparando o retry automaticamente. Respostas bloqueadas pelo provedor levantam `BlockedResponseError`, sem retry (ver "Respostas bloqueadas"). Se todas as tentativas falharem, o erro aparece no relatório.

---

## Credenciais

**APIs de LLM** — configurar no arquivo `.env`:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

**Google Drive** — OAuth2:
1. Criar projeto no [Google Cloud Console](https://console.cloud.google.com)
2. Ativar a Google Drive API
3. Criar credencial OAuth → App para computador → baixar como `credentials.json`
4. Na primeira execução o browser abrirá para autenticação; `token.json` é salvo automaticamente

Ambos os arquivos estão no `.gitignore` e nunca devem ser commitados.

---

## Comandos Úteis

```bash
# Instalar dependências
uv sync

# Executar uma bateria de testes
uv run python -m benchmark run --config config/experiments/example.yaml

# Refazer a análise estatística de uma execução existente
uv run python -m benchmark analyze results/<experimento>_<timestamp>/results.json

# Rodar testes
uv run pytest

# Linting
uv run ruff check src/
uv run ruff format src/
```

> **Atenção:** a métrica BERTScore baixa um modelo de linguagem pesado (~1-2 GB) na primeira execução. Isso pode demorar alguns minutos dependendo da conexão. O modelo fica em cache após o primeiro download.
