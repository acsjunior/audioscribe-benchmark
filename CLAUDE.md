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
│   └── inputs/               # áudios baixados do Google Drive (não commitados)
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
│       ├── config/
│       │   ├── __init__.py       # load_config()
│       │   └── schema.py         # modelos Pydantic do YAML de configuração
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── base.py           # BaseTranscriber (ABC)
│       │   └── whisper.py        # WhisperTranscriber (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
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
│       │   ├── json_reporter.py
│       │   └── html_reporter.py  # relatório HTML com tabela comparativa e ranking
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
│   ├── test_refinement/
│   ├── test_reporting/
│   ├── test_transcription/
│   └── test_utils/
├── logs/                         # logs de execução (gerado automaticamente)
└── results/                      # saída de cada execução (gerado automaticamente)
    └── {experimento}_{timestamp}/
        ├── results.csv
        ├── results.json
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

drive:
  credentials_path: credentials.json
  token_path: token.json
  audio_dir: data/inputs    # onde os MP3s são baixados/cacheados

results_path: results
```

---

## Arquitetura e Decisões

### Fluxo do Pipeline
Para cada música no catálogo:
1. Verifica se o MP3 já existe em `audio_dir` (cache)
2. Se não existe, baixa do Google Drive via API
3. Se `audio_preprocessing` estiver definido, pré-processa o áudio (com cache em `.wav`)
4. Transcreve com Whisper (ou variante)
5. Para cada configuração de refinamento: refina com o LLM especificado
6. Calcula métricas comparando com a letra do catálogo
7. Salva resultados incrementalmente ao final

### Catálogo CSV como Fonte Única
Não há pastas por música nem arquivos `ground_truth.md`. Todos os metadados e letras vivem em `data/catalogo.csv`. Os áudios são baixados sob demanda e cacheados em `data/inputs/`.

### Google Drive — Download com Cache
`gdrive.py` implementa OAuth2 via `google-auth-oauthlib`. Na primeira execução abre o browser para autenticação; o token é salvo em `token.json` e reutilizado automaticamente. O cache é verificado pelo nome do arquivo (coluna `Arquivo` do catálogo) dentro de `audio_dir`. Se o arquivo já existir localmente, o download é ignorado — tanto no pipeline (`pipeline.py`) quanto dentro de `download_audio()` (`gdrive.py`).

### Normalização nas Métricas
WER e CER normalizam os textos antes do cálculo: converte para minúsculas, remove pontuação e colapsa espaços/quebras de linha. Acentuação é preservada — diferenças como "não" vs "nao" continuam sendo contadas como erro.

### Adapter Pattern — Refinamento com LLMs
Cada provedor (OpenAI, Anthropic, Google) tem seu próprio adapter implementando `BaseRefiner`. Adicionar um novo provedor requer apenas criar um novo arquivo em `refinement/` e registrá-lo em `REFINER_REGISTRY`.

### Módulos de Métricas
Cada métrica implementa `BaseMetric` e é registrada em `METRIC_REGISTRY`. Métricas disponíveis: WER, CER, BERTScore.

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
Retry automático com backoff exponencial via `async_retry()`. Falhas isoladas (download, transcrição ou refinamento) nunca derrubam o pipeline — o erro é registrado e a execução continua. Respostas truncadas por limite de tokens levantam `TruncatedResponseError` (detectado via `finish_reason`/`stop_reason` de cada provedor), disparando o retry automaticamente. Se todas as tentativas falharem, o erro aparece no relatório.

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

# Rodar testes
uv run pytest

# Linting
uv run ruff check src/
uv run ruff format src/
```

> **Atenção:** a métrica BERTScore baixa um modelo de linguagem pesado (~1-2 GB) na primeira execução. Isso pode demorar alguns minutos dependendo da conexão. O modelo fica em cache após o primeiro download.
