# AudioScribe Benchmark

Ferramenta para comparar estratégias de transcrição automática de letras de
música a partir de áudio.

## O que é

O AudioScribe Benchmark é um pipeline que transcreve um conjunto de músicas com
diferentes combinações de modelo de transcrição, pré-processamento de áudio e
revisão por LLM, e mede a qualidade de cada resultado comparando com a letra
correta. O objetivo é responder, com números, qual combinação produz as melhores
transcrições para um determinado acervo.

O projeto foi construído para um acervo de sambas brasileiros antigos, mas
funciona com qualquer conjunto de músicas que tenha áudio e letra de referência.

## Para que serve

- Comparar modelos de transcrição de áudio entre si
- Avaliar se tratar o áudio antes (isolar a voz, reduzir ruído) melhora o resultado
- Avaliar se revisar a transcrição com um LLM melhora o resultado, e com qual
  provedor e prompt
- Testar novas estratégias de prompt de forma reproduzível e rastreável

## Como funciona

Para cada música do catálogo, o pipeline:

1. **Obtém o áudio**: baixa o MP3 do Google Drive (ou usa a cópia local, se já existir)
2. **Pré-processa** (opcional): isola a voz ou reduz o ruído do áudio
3. **Transcreve**: envia o áudio para um modelo de transcrição da OpenAI, uma ou
   várias vezes (rodadas), guardando as transcrições em cache para reaproveitar
   entre experimentos
4. **Refina** (opcional): pede a um ou mais LLMs que revisem a transcrição,
   cada um com o prompt configurado
5. **Avalia**: compara cada versão com a letra de referência usando métricas de
   acurácia
6. **Reporta**: salva os resultados em CSV, JSON e um relatório HTML com ranking

Toda execução inclui também um **baseline** (a transcrição sem nenhum
refinamento), para medir o ganho ou a perda de cada estratégia.

O catálogo pode separar músicas de **desenvolvimento** (para ajustar prompts e
métodos) e de **teste** (para a avaliação final), evitando que os métodos sejam
ajustados às mesmas músicas em que são avaliados.

### Componentes disponíveis

| Etapa | Opções |
|---|---|
| Transcrição | `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`; LLMs que ouvem áudio (`gpt-audio`, Gemini) |
| Consenso | a transcrição mais central entre várias rodadas |
| Pré-processamento | `demucs` (isolamento de voz), `noisereduce`, `deepfilternet` (redução de ruído) |
| Refinamento | OpenAI (GPT), Anthropic (Claude), Google (Gemini) |
| Conferência com áudio | um LLM multimodal ouve a gravação e propõe alterações pontuais no rascunho |
| Métricas | WER e CER (taxa de erro por palavra e caractere), BERTScore (similaridade semântica) |

## Instalação

Requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/acsjunior/audioscribe-benchmark.git
cd audioscribe-benchmark
uv sync --group dev
```

## Configuração

### 1. Chaves de API

```bash
cp .env.example .env
```

Preencha no `.env` as chaves dos provedores que for usar. A da OpenAI é
obrigatória, porque é usada na transcrição; as demais só se você usar esses
provedores no refinamento.

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

### 2. Acesso ao Google Drive

Os áudios são baixados de uma pasta do Google Drive via OAuth2. Gere um
`credentials.json` (tipo "App para computador") no Google Cloud Console, com a
Google Drive API ativada, e coloque na raiz do projeto. Na primeira execução o
navegador abre para autorizar o acesso, e o token fica salvo em `token.json`.

O passo a passo detalhado está no [MANUAL.md](MANUAL.md#32-google-drive--oauth2).

> Se os MP3s já estiverem em `data/inputs/` com o nome indicado no catálogo, o
> Google Drive não é necessário.

### 3. Catálogo de músicas

O arquivo `data/catalogo.csv` lista as músicas a avaliar. Cada linha traz os
metadados da música (título, autoria, intérprete, ano), a **letra de referência**
usada na avaliação, o nome do arquivo de áudio e o link do Google Drive. Uma
coluna opcional `Split` marca cada música como `dev` (desenvolvimento) ou `test`
(teste).

### 4. Experimento

Cada experimento é um arquivo YAML em `config/experiments/` que define quais
combinações testar:

```yaml
experiment_name: "meu-experimento"

transcription:
  provider: whisper
  model: gpt-4o-transcribe
  # audio_preprocessing: demucs   # opcional: demucs | noisereduce | deepfilternet
  runs: 5                         # transcrições independentes por música

refinement:                       # uma entrada por combinação LLM + prompt
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/conservative.yaml
  - provider: anthropic
    model: claude-sonnet-4-6
    prompt_file: prompts/rich_context.yaml

metrics: [wer, cer]

catalog_path: data/catalogo.csv
split: dev                        # dev | test | all
drive:
  audio_dir: data/inputs
```

Use `config/experiments/example.yaml` como ponto de partida.

### 5. Prompts

As instruções de revisão enviadas aos LLMs ficam em arquivos YAML em `prompts/`
e podem usar os metadados da música (`{titulo}`, `{autoria}`,
`{interpretacao}`, `{ano}`) e a transcrição (`{transcription}`). Para testar uma
nova estratégia, basta criar um arquivo novo e referenciá-lo no experimento.

## Uso

```bash
uv run python -m benchmark run --config config/experiments/example.yaml
```

Os resultados ficam em `results/{experimento}_{timestamp}/`:

| Arquivo | Conteúdo |
|---|---|
| `report.html` | Relatório visual com ranking, análise estatística e métricas por música |
| `results.csv` | Uma linha por música × rodada × combinação, com métricas, tokens e tempo |
| `results.json` | Os mesmos dados em JSON |
| `stats.json` | Análise estatística pareada contra o baseline (ganhos, intervalos de confiança, falhas graves) |

Os logs da execução ficam em `logs/`.

## Documentação

- **[MANUAL.md](MANUAL.md)**: guia completo de uso, com todas as opções de
  configuração, formato do catálogo, criação de prompts, leitura dos resultados
  e solução de problemas
- **[PROTOCOLO.md](PROTOCOLO.md)**: protocolo do estudo (hipóteses, dados, letras de
  referência, análise estatística)
- **[ROADMAP.md](ROADMAP.md)**: plano de entregáveis
- **[CLAUDE.md](CLAUDE.md)**: arquitetura e decisões técnicas do código

## Desenvolvimento

```bash
uv run pytest           # testes
uv run ruff check src/  # lint
uv run ruff format src/ # formatação
```

Provedores de LLM e métricas são plugáveis: para adicionar um novo, implemente a
classe base correspondente e registre-a no registry do módulo.
