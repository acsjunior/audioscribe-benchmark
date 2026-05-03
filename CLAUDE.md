# AudioScribe Benchmark

## Objetivo

Pipeline de benchmark para avaliar a melhor abordagem de transcrição de letras de sambas antigos em português. O pipeline transcreve áudios via API do Whisper, opcionalmente refina as transcrições com LLMs, e compara os resultados com letras validadas (ground truth) usando métricas de acurácia.

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
| Credenciais | `.env` via `python-dotenv` |

---

## Estrutura de Diretórios

```
audioscribe-benchmark/
├── CLAUDE.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── config/
│   └── experiments/
│       └── example.yaml          # modelo de configuração de bateria de testes
├── data/
│   └── dataset/
│       └── {artista-slug}-{titulo-slug}/
│           ├── audio.mp3
│           └── ground_truth.txt
├── prompts/
│   ├── minimalist.yaml
│   ├── rich_context.yaml
│   ├── archaic_vocab.yaml
│   └── few_shot.yaml
├── src/
│   └── benchmark/
│       ├── __init__.py
│       ├── models.py             # SongData, ExperimentResult
│       ├── dataset.py            # carregamento e parsing do dataset
│       ├── pipeline.py           # orquestrador principal
│       ├── cli.py                # entrypoint CLI
│       ├── config/
│       │   ├── __init__.py       # load_config()
│       │   └── schema.py         # modelos Pydantic do YAML de configuração
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── base.py           # BaseTranscriber (ABC)
│       │   └── whisper.py        # WhisperTranscriber (whisper-1 via API)
│       ├── refinement/
│       │   ├── __init__.py       # REFINER_REGISTRY, get_refiner()
│       │   ├── base.py           # BaseRefiner, PromptConfig, load_prompt()
│       │   ├── openai.py         # OpenAIRefiner (GPT-4o)
│       │   ├── anthropic.py      # AnthropicRefiner (Claude)
│       │   └── google.py         # GoogleRefiner (Gemini)
│       ├── metrics/
│       │   ├── __init__.py       # METRIC_REGISTRY, get_metrics()
│       │   ├── base.py           # BaseMetric (ABC)
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
│   ├── test_config/
│   ├── test_metrics/
│   ├── test_refinement/
│   └── test_utils/
├── logs/                         # logs de execução (gerado automaticamente)
└── results/                      # saída de cada execução (gerado automaticamente)
    └── {experimento}_{timestamp}/
        ├── results.csv
        ├── results.json
        └── report.html
```

---

## Convenções do Dataset

### Nomenclatura de pastas
Usar **slugify**: sem acentos, letras maiúsculas ou caracteres especiais. Espaços viram hífens.

```
cartola-as-rosas-nao-falam/
nelson-cavaquinho-folhas-secas/
```

### Formato do ground_truth.txt
Cabeçalho YAML-like com metadados, seguido de separador `---` e a letra:

```
artista: Cartola
titulo: As Rosas Não Falam
ano: 1976
album: Cartola
---
As rosas não falam
Apenas perfumam
...
```

---

## Arquitetura e Decisões

### Adapter Pattern — Refinamento com LLMs
Cada provedor (OpenAI, Anthropic, Google) tem seu próprio adapter implementando `BaseRefiner`. Adicionar um novo provedor requer apenas criar um novo arquivo em `refinement/` e registrá-lo em `REFINER_REGISTRY`. Nenhum outro arquivo precisa ser alterado.

### Módulos de Métricas
Cada métrica implementa `BaseMetric` e é registrada em `METRIC_REGISTRY`. Adicionar uma nova métrica requer apenas criar um arquivo em `metrics/` e registrá-lo. Métricas iniciais: WER, CER, BERTScore.

### Prompts como Arquivos Externos
Prompts definidos em arquivos YAML em `prompts/`. O código nunca hardcoda strings de prompt. Cada experimento registra o caminho e nome do prompt usado para rastreabilidade total.

### Configuração Centralizada via YAML
Cada bateria de testes tem seu próprio arquivo YAML em `config/experiments/`. O pipeline é disparado via CLI apontando para esse arquivo. Permite múltiplas configurações sem alterar código.

### asyncio desde o início
Todo o código de I/O usa `async/await` para permitir adição de concorrência no futuro sem refatoração. A execução atual é sequencial (`asyncio.run()`).

### Resiliência
Retry automático com backoff exponencial via `async_retry()`. Falhas isoladas (por experimento ou por música) nunca derrubam o pipeline. Erros são registrados com detalhes e a execução continua.

### Output
- `results.csv` e `results.json` por execução (futuramente migrável para SQLite)
- `report.html` gerado automaticamente com tabela comparativa e ranking por combinação LLM + prompt

---

## Credenciais

Configurar no arquivo `.env` na raiz do projeto:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

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
