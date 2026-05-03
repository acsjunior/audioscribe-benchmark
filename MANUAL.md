# Manual de Uso — AudioScribe Benchmark

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalação](#2-instalação)
3. [Configuração das credenciais](#3-configuração-das-credenciais)
4. [Preparação do dataset](#4-preparação-do-dataset)
5. [Configuração dos experimentos](#5-configuração-dos-experimentos)
6. [Configuração dos prompts](#6-configuração-dos-prompts)
7. [Executando o pipeline](#7-executando-o-pipeline)
8. [Interpretando os resultados](#8-interpretando-os-resultados)
9. [Dicas e boas práticas](#9-dicas-e-boas-práticas)
10. [Solução de problemas](#10-solução-de-problemas)

---

## 1. Pré-requisitos

- Python 3.11 ou superior
- [uv](https://docs.astral.sh/uv/) instalado
- Chaves de API dos provedores que deseja usar:
  - [OpenAI](https://platform.openai.com/api-keys) — para Whisper e GPT-4o
  - [Anthropic](https://console.anthropic.com/) — para Claude (opcional)
  - [Google](https://ai.google.dev/gemini-api/docs/api-key) — para Gemini (opcional)

---

## 2. Instalação

```bash
git clone https://github.com/acsjunior/audioscribe-benchmark.git
cd audioscribe-benchmark

# Instalar dependências
uv sync --group dev
```

> **Atenção:** na primeira vez que a métrica BERTScore for executada, ela baixará
> automaticamente um modelo de linguagem (~1-2 GB). Isso pode levar alguns minutos
> dependendo da sua conexão. O modelo fica em cache após o primeiro download.

---

## 3. Configuração das credenciais

Copie o arquivo de exemplo e preencha com suas chaves:

```bash
cp .env.example .env
```

Edite o `.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

Você só precisa preencher as chaves dos provedores que for usar.
O pipeline ignora automaticamente os provedores não configurados no experimento.

---

## 4. Preparação do dataset

### 4.1 Estrutura de pastas

Cada música deve ter sua própria pasta dentro de `data/dataset/`.
O nome da pasta deve seguir o padrão **slugify**: letras minúsculas, sem acentos,
espaços substituídos por hífens.

```
data/dataset/
├── cartola-as-rosas-nao-falam/
│   ├── audio.mp3
│   └── ground_truth.txt
├── nelson-cavaquinho-folhas-secas/
│   ├── audio.mp3
│   └── ground_truth.txt
└── joao-da-baiana-no-tabuleiro-da-baiana/
    ├── audio.mp3
    └── ground_truth.txt
```

### 4.2 Arquivo de áudio

- Formato: `.mp3`
- O nome do arquivo pode ser qualquer um — o pipeline encontra automaticamente o `.mp3` da pasta
- **Obrigatório:** deve haver exatamente um arquivo `.mp3` por pasta. Se houver zero ou mais de um, a música é ignorada com aviso no log
- Não há restrição de duração, mas arquivos muito longos aumentam o custo da API do Whisper

### 4.3 Ground truth (letra validada)

Crie o arquivo `ground_truth.txt` com o seguinte formato obrigatório:

```
artista: Cartola
titulo: As Rosas Não Falam
ano: 1976
album: Cartola
---
As rosas não falam
Apenas perfumam
E com seus encantos
Me fazem chorar
```

**Regras importantes:**
- O cabeçalho com os metadados é obrigatório
- O separador `---` deve estar em uma linha própria
- A letra começa imediatamente após o `---`
- Revise cuidadosamente a letra — a qualidade do ground truth é fundamental para a acurácia do benchmark
- Para anos incertos, você pode usar strings como `"c. 1932"` ou `"1930?"`

---

## 5. Configuração dos experimentos

Os experimentos são definidos em arquivos YAML dentro de `config/experiments/`.
Você pode criar quantos arquivos quiser — um para cada bateria de testes.

### 5.1 Estrutura do arquivo de configuração

```yaml
experiment_name: "nome-do-experimento"  # usado para nomear a pasta de resultados

logging:
  mode: normal        # normal | verbose
  output_file: logs/experimento.log

retry:
  max_attempts: 3     # tentativas por chamada de API
  backoff_factor: 2.0 # fator de espera exponencial entre tentativas

transcription:
  provider: whisper
  model: whisper-1

refinement:
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/rich_context.yaml

metrics:
  - wer
  - cer
  - bertscore

dataset_path: data/dataset
results_path: results
```

### 5.2 Provedores e modelos disponíveis

| Provider | Modelos sugeridos |
|---|---|
| `openai` | `gpt-4o`, `gpt-4o-mini` |
| `anthropic` | `claude-opus-4-7`, `claude-sonnet-4-6` |
| `google` | `gemini-2.0-flash`, `gemini-1.5-pro` |

### 5.3 Métricas disponíveis

| Métrica | Descrição | Interpretação |
|---|---|---|
| `wer` | Word Error Rate | Menor é melhor (0 = perfeito) |
| `cer` | Character Error Rate | Menor é melhor (0 = perfeito) |
| `bertscore` | BERTScore F1 | Maior é melhor (1 = perfeito) |

### 5.4 Exemplos de baterias de testes

**Teste rápido (só baseline + um prompt):**
```yaml
experiment_name: "teste-rapido"
refinement:
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
metrics:
  - wer
  - cer
```

**Comparação completa de prompts:**
```yaml
experiment_name: "comparacao-prompts-openai"
refinement:
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/rich_context.yaml
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/archaic_vocab.yaml
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/few_shot.yaml
metrics:
  - wer
  - cer
  - bertscore
```

**Comparação entre provedores:**
```yaml
experiment_name: "comparacao-provedores"
refinement:
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/rich_context.yaml
  - provider: anthropic
    model: claude-opus-4-7
    prompt_file: prompts/rich_context.yaml
  - provider: google
    model: gemini-2.0-flash
    prompt_file: prompts/rich_context.yaml
metrics:
  - wer
  - cer
  - bertscore
```

---

## 6. Configuração dos prompts

Os prompts ficam em `prompts/` e são referenciados pelo campo `prompt_file` no YAML do experimento.

### 6.1 Formato do arquivo de prompt

```yaml
name: nome-do-prompt          # identificador no relatório
description: "Descrição"      # texto livre para documentação
system: |
  Instrução de sistema para o LLM.
user: |
  Instrução do usuário. Use {transcription} onde a
  transcrição do Whisper deve ser inserida.
examples:                     # opcional — para prompts few-shot
  - input: "texto de entrada"
    output: "texto corrigido"
```

### 6.2 Prompts disponíveis

| Arquivo | Estratégia |
|---|---|
| `prompts/minimalist.yaml` | Correção ortográfica mínima |
| `prompts/rich_context.yaml` | Contexto rico sobre sambas antigos |
| `prompts/archaic_vocab.yaml` | Foco em vocabulário arcaico e gírias |
| `prompts/few_shot.yaml` | Exemplos de correção guiando o modelo |

### 6.3 Criando um prompt personalizado

Crie um novo arquivo em `prompts/` e referencie-o no YAML do experimento:

```yaml
name: meu_prompt
description: "Minha estratégia personalizada"
system: |
  Sua instrução de sistema aqui.
user: |
  Sua instrução aqui.

  {transcription}
```

---

## 7. Executando o pipeline

```bash
uv run python -m benchmark run --config config/experiments/example.yaml
```

### 7.1 Opções da CLI

```
Opções:
  -c, --config PATH  Caminho para o arquivo YAML do experimento  [obrigatório]
  --help             Exibe esta mensagem de ajuda
```

### 7.2 Acompanhando a execução

No modo `normal`, o log exibe o progresso de cada música e experimento:

```
INFO  Dataset carregado: 3 música(s)
INFO  [1/3] Cartola — As Rosas Não Falam
INFO    Transcrição concluída
INFO    [1/2] openai/gpt-4o [prompts/minimalist.yaml]
INFO      OK — tokens: 312, tempo: 1823ms
INFO    [2/2] openai/gpt-4o [prompts/rich_context.yaml]
INFO      OK — tokens: 487, tempo: 2104ms
INFO  [2/3] Nelson Cavaquinho — Folhas Secas
...
INFO  Resultados salvos em: results/experimento-01_20260503_143022
```

Para detalhes de cada chamada de API, use o modo `verbose` no YAML:

```yaml
logging:
  mode: verbose
```

---

## 8. Interpretando os resultados

Ao final de cada execução, os resultados são salvos em:

```
results/
└── {experiment_name}_{timestamp}/
    ├── results.csv    ← tabela com todos os experimentos
    ├── results.json   ← mesmos dados em formato JSON
    └── report.html    ← relatório visual com ranking
```

### 8.1 Relatório HTML

Abra o `report.html` no navegador para visualizar:

- **Ranking por combinação:** média das métricas de cada combinação LLM + prompt,
  ordenada da melhor para a pior
- **Resultados por música:** métricas individuais de cada experimento por música,
  facilitando a identificação de casos onde uma abordagem se destaca

### 8.2 Arquivo CSV

Cada linha representa um experimento (uma música × uma combinação LLM + prompt).
Útil para análises adicionais em planilhas ou Python/pandas.

Colunas principais:

| Coluna | Descrição |
|---|---|
| `song_id` | Identificador da pasta da música |
| `refinement_provider` | Provedor LLM (`baseline` se sem refinamento) |
| `refinement_model` | Modelo utilizado |
| `prompt_name` | Nome do prompt |
| `wer` / `cer` / `bertscore` | Scores das métricas |
| `tokens_used` | Total de tokens consumidos |
| `response_time_ms` | Tempo de resposta da API em ms |
| `error` | Mensagem de erro, se houver |

### 8.3 Entendendo o baseline

Todo experimento inclui automaticamente uma linha de **baseline** por música:
a transcrição bruta do Whisper avaliada sem nenhum refinamento.
Isso permite medir exatamente o ganho (ou perda) de cada estratégia de LLM.

---

## 9. Dicas e boas práticas

**Comece pequeno:** teste com 2-3 músicas antes de rodar o dataset completo.
Isso reduz custo e tempo, e permite validar que tudo está configurado corretamente.

**Isole uma variável por vez:** para comparar prompts, mantenha o mesmo provedor e modelo.
Para comparar provedores, use o mesmo prompt.

**Use o modo verbose para debugging:** ative `mode: verbose` para ver exatamente o
que está sendo enviado e recebido das APIs.

**Acompanhe os logs:** os arquivos em `logs/` permitem revisar execuções anteriores,
incluindo erros e tempos de resposta.

**Nomeie os experimentos com clareza:** use nomes descritivos como
`comparacao-prompts-openai-2026-05` para facilitar a organização dos resultados.

**Ground truth é tudo:** o benchmark só é tão bom quanto a qualidade das letras
validadas. Revise cada `ground_truth.txt` com cuidado antes de rodar o benchmark.

---

## 10. Solução de problemas

**Erro: `No API key was provided`**
Verifique se o arquivo `.env` existe na raiz do projeto e contém a chave correta.

**Erro: `Dataset path not found`**
Confirme que o campo `dataset_path` no YAML aponta para o diretório correto e que
ele contém subpastas com `audio.mp3` e `ground_truth.txt`.

**Erro: `Missing audio.mp3` ou `Missing ground_truth.txt`**
O pipeline avisa e pula a música. Verifique os nomes dos arquivos — devem ser
exatamente `audio.mp3` e `ground_truth.txt`.

**Experimento registrado com erro no CSV**
Uma chamada de API falhou após todas as tentativas de retry. Verifique o arquivo
de log para detalhes. O pipeline continua os demais experimentos normalmente.

**BERTScore muito lento na primeira execução**
Comportamento esperado — o modelo está sendo baixado (~1-2 GB). Nas execuções
seguintes, o cache é utilizado e a métrica roda normalmente.

**Resultado HTML vazio**
Ocorre quando todas as transcrições falharam (nenhum resultado gerado).
Verifique os logs para identificar a causa raiz.
