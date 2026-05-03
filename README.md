# AudioScribe Benchmark

Pipeline de benchmark para avaliar a melhor abordagem de transcrição de letras de sambas antigos em português. O pipeline transcreve áudios via API do Whisper, opcionalmente refina as transcrições com LLMs, e compara os resultados com letras validadas (ground truth) usando métricas de acurácia.

## Contexto

O domínio é específico: sambas brasileiros das décadas de 1920-1950, com vocabulário arcaico, gírias da época, qualidade de áudio inferior e pronúncia característica do português carioca popular. Essa especificidade torna o benchmark especialmente relevante para entender se — e quanto — o refinamento com LLM melhora a acurácia nesse cenário desafiador.

## Funcionalidades

- Transcrição de áudios MP3 via API do Whisper (`whisper-1`)
- Refinamento das transcrições com OpenAI (GPT-4o), Anthropic (Claude) e Google (Gemini)
- Suporte a múltiplas estratégias de prompt definidas em arquivos YAML externos
- Cálculo de métricas WER, CER e BERTScore para cada experimento
- Relatório HTML automático com tabela comparativa e ranking das melhores combinações
- Resultados exportados em CSV e JSON por execução
- Retry automático com backoff exponencial em falhas de API
- Logs em terminal e arquivo, com modos `normal` e `verbose`

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Instalação

```bash
git clone <repo>
cd audioscribe-benchmark

# Instalar dependências
uv sync --group dev

# Configurar credenciais
cp .env.example .env
# edite o .env com suas chaves de API
```

## Dataset

Organize os áudios e letras validadas em `data/dataset/`, uma pasta por música:

```
data/dataset/
└── cartola-as-rosas-nao-falam/
    ├── audio.mp3
    └── ground_truth.md
```

Os nomes de pasta devem seguir o padrão **slugify** (sem acentos, espaços ou caracteres especiais).

O arquivo `ground_truth.md` usa o formato **Markdown com frontmatter YAML**:

```markdown
---
titulo: As Rosas Não Falam
autoria: Cartola
interpretacao: Cartola
disco: Cartola
ano: 1976
---
As rosas não falam
Apenas perfumam
...
```

## Uso

Crie um arquivo de configuração em `config/experiments/` (veja `example.yaml` como referência) e execute:

```bash
uv run python -m benchmark run --config config/experiments/example.yaml
```

Os resultados serão salvos em `results/{experimento}_{timestamp}/`:

```
results/experimento-01_20260503_143000/
├── results.csv
├── results.json
└── report.html
```

## Prompts

As estratégias de refinamento disponíveis em `prompts/` são:

| Arquivo | Estratégia |
|---|---|
| `minimalist.yaml` | Correção ortográfica mínima |
| `rich_context.yaml` | Contexto rico sobre sambas antigos |
| `archaic_vocab.yaml` | Foco em vocabulário arcaico e gírias |
| `few_shot.yaml` | Exemplos de correção guiando o modelo |

## Testes

```bash
uv run pytest
uv run pytest --cov=benchmark --cov-report=html
```

## Linting

```bash
uv run ruff check src/
uv run ruff format src/
```
