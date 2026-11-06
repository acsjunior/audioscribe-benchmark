# AudioScribe Benchmark

Benchmark para descobrir a melhor forma de transcrever automaticamente letras de
**sambas antigos brasileiros (1920–1955)**.

É um caso difícil para reconhecimento de fala: gravações de 78 rpm com chiado e
saturação, vocabulário e gírias da época ("almofadinha", "batente", "níquel"),
contrações coloquiais e pronúncia característica do período.

## Como funciona

Para cada música do catálogo (`data/catalogo.csv`, com a letra validada de cada uma):

1. Baixa o áudio do Google Drive (com cache local)
2. Opcionalmente pré-processa o áudio — isolamento de voz (demucs) ou redução de
   ruído (noisereduce, DeepFilterNet)
3. Transcreve com a API da OpenAI (`whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`)
4. Opcionalmente refina a transcrição com um LLM (OpenAI, Anthropic ou Google),
   usando diferentes estratégias de prompt
5. Compara cada resultado com a letra validada (WER, CER, BERTScore) e gera um
   relatório HTML com o ranking das combinações

Cada combinação é configurada em um YAML em `config/experiments/`, e toda
execução inclui um **baseline** — a transcrição bruta, sem refinamento — para
medir o ganho real de cada estratégia.

## Resultados até agora

28 músicas, métrica WER (proporção de palavras erradas — menor é melhor):

| Abordagem | WER sem refinamento | Efeito do refinamento com LLM |
|---|---|---|
| `whisper-1` | ~0,27 | piora (melhor caso: 0,28) |
| **`gpt-4o-transcribe`** | **~0,17–0,21** | no máximo empata (prompt `conservative`) |
| `gpt-4o-transcribe` + demucs | 0,17 | piora |
| `whisper-1` + demucs | 0,36 | melhora levemente (0,35) |
| `whisper-1` + noisereduce | 0,61 | melhora levemente (0,59) |
| `whisper-1` + DeepFilterNet¹ | 0,69 | melhora levemente (0,66) |

¹ 25 músicas.

Conclusões:

- **O modelo de transcrição é o que mais importa.** `gpt-4o-transcribe` reduziu o
  erro de ~27% para ~17% das palavras.
- **Refinar com LLM não ajuda.** Os modelos tendem a reescrever ou "modernizar" a
  letra; o prompt mais contido (`conservative`) só consegue empatar com o baseline.
  O refinamento só melhora um pouco quando a transcrição de partida é muito ruim.
- **Limpar o áudio não ajuda.** Com `whisper-1`, todas as técnicas pioraram o
  resultado (noisereduce e DeepFilterNet de forma severa); com `gpt-4o-transcribe`,
  o demucs ficou neutro. As ferramentas são treinadas em áudio moderno e introduzem
  artefatos em gravações antigas.
- **Há variação entre execuções.** O baseline do `gpt-4o-transcribe` oscilou entre
  0,17 e 0,20 com a mesma configuração; diferenças pequenas podem ser ruído.

Até o momento, a melhor receita é a mais simples: `gpt-4o-transcribe` direto no
áudio original, sem pré-processamento e sem refinamento.

## Início rápido

Requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/acsjunior/audioscribe-benchmark.git
cd audioscribe-benchmark
uv sync --group dev
cp .env.example .env   # preencha as chaves de API (OpenAI, e opcionalmente Anthropic/Google)
```

Coloque o `credentials.json` (OAuth2 do Google Drive) na raiz do projeto e rode:

```bash
uv run python -m benchmark run --config config/experiments/example.yaml
```

Os resultados ficam em `results/{experimento}_{timestamp}/` (`results.csv`,
`results.json` e `report.html`).

O **[MANUAL.md](MANUAL.md)** tem o passo a passo completo: credenciais do Google
Drive, formato do catálogo, todas as opções de configuração, prompts disponíveis
e interpretação dos resultados.

## Desenvolvimento

```bash
uv run pytest
uv run ruff check src/
uv run ruff format src/
```

Stack: Python 3.11, uv, pytest, ruff, Pydantic, asyncio. Provedores de LLM e
métricas são plugáveis via registry — veja [CLAUDE.md](CLAUDE.md) para a
arquitetura.
