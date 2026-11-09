# Manual de Uso — AudioScribe Benchmark

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalação](#2-instalação)
3. [Configuração das credenciais](#3-configuração-das-credenciais)
4. [Preparação do catálogo](#4-preparação-do-catálogo)
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
- Credenciais OAuth2 do Google Drive (para download dos áudios)

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

### 3.1 Chaves de API dos LLMs

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

Você só precisa preencher as chaves dos provedores que for usar no experimento.

### 3.2 Google Drive — OAuth2

Os áudios ficam em uma pasta privada do Google Drive e são baixados automaticamente.
Para isso é necessário um arquivo `credentials.json` com as credenciais OAuth2.

**Passos para obter o `credentials.json`:**

1. Acesse o [Google Cloud Console](https://console.cloud.google.com)
2. Crie um projeto (ou selecione um existente)
3. Ative a **Google Drive API**: menu lateral → **APIs e Serviços** → **Biblioteca** → pesquise "Google Drive API" → Ativar
4. Crie a credencial: **APIs e Serviços** → **Credenciais** → **Criar credenciais** → **ID do cliente OAuth**
5. Tipo de aplicativo: **App para computador** → preencha um nome → Criar
6. Faça o download do JSON gerado e renomeie para `credentials.json` na raiz do projeto
7. Configure a tela de consentimento: **APIs e Serviços** → **Tela de Permissão OAuth** → **Público Alvo** → adicione seu e-mail como **usuário de teste**

Na **primeira execução**, o browser abrirá para autenticação. O token é salvo em
`token.json` e reutilizado automaticamente nas próximas execuções.

> Ambos `credentials.json` e `token.json` estão no `.gitignore` e nunca devem ser
> commitados.

---

## 4. Preparação do catálogo

O arquivo `data/catalogo.csv` é a **fonte única de verdade** do dataset. Ele contém
os metadados de cada música, a letra validada (ground truth) e o link para o áudio
no Google Drive.

### 4.1 Colunas do catálogo

| Coluna | Descrição |
|---|---|
| `Música` | Título da música |
| `Autoria` | Compositor(es) |
| `Interpretação` | Intérprete(s) |
| `Acompanhamento` | Conjunto/orquestra (ignorado pelo pipeline) |
| `Disco` | Nome do disco/gravadora e número |
| `Ano` | Ano de gravação |
| `Gênero` | Gênero musical |
| `Letra` | Ground truth — letra completa e validada da música |
| `Arquivo` | Nome exato do arquivo MP3 no Google Drive (ex: `samba_cartola.mp3`) |
| `URL` | URL de compartilhamento do Google Drive |
| `Fonte` | URL da fonte da letra (ignorado) |
| `Acesso` | Data de acesso à fonte (ignorado) |
| `Split` | Opcional: `dev` (desenvolvimento) ou `test` (teste) — ver seção 4.4 |

Colunas extras (por exemplo, dados de verificação de domínio público) são
ignoradas pelo pipeline e podem ser acrescentadas livremente.

### 4.2 Ground truth (coluna `Letra`)

A coluna `Letra` deve conter a letra completa e validada da música, exatamente como
seria a transcrição perfeita. A qualidade do benchmark depende diretamente da
qualidade dessas letras — revise cada uma com atenção.

### 4.3 Download automático dos áudios

O pipeline baixa os áudios automaticamente do Google Drive na primeira vez que cada
música é processada. Os arquivos são salvos em `data/inputs/` usando o nome definido
na coluna `Arquivo`.

**Cache automático:** se o arquivo já existir em `data/inputs/`, o download é
ignorado. Isso permite interromper e retomar experimentos sem rebaixar áudios já
obtidos, e evita custos desnecessários de rede.

### 4.4 Desenvolvimento e teste (coluna `Split`)

A coluna `Split` separa as músicas em dois conjuntos:

- **`dev` (desenvolvimento):** usadas à vontade para criar e ajustar prompts e métodos.
- **`test` (teste):** reservadas para a avaliação final. Só devem ser rodadas uma
  vez, com as configurações já escolhidas — ajustar um prompt olhando o resultado
  delas torna a avaliação otimista.

Regras:

- Se a coluna não existir, todas as músicas são tratadas como `dev`.
- Se existir, toda linha precisa ter `dev` ou `test`; valor vazio ou diferente
  gera erro ao carregar o catálogo (para nenhuma música nova cair em `dev` por
  esquecimento).
- O experimento escolhe o conjunto com o campo `split` do YAML (seção 5.1). O
  padrão é `dev`; para rodar o teste é preciso escrever `split: test` (ou `all`).

---

## 5. Configuração dos experimentos

Os experimentos são definidos em arquivos YAML dentro de `config/experiments/`.
Você pode criar quantos arquivos quiser — um para cada bateria de testes.

### 5.1 Estrutura completa do arquivo de configuração

```yaml
experiment_name: "nome-do-experimento"  # usado para nomear a pasta de resultados

logging:
  mode: normal        # normal | verbose
  output_file: logs/experimento.log

retry:
  max_attempts: 3     # tentativas por chamada de API (inclui truncamentos)
  backoff_factor: 2.0 # fator de espera exponencial entre tentativas

transcription:
  provider: whisper
  model: whisper-1    # whisper-1 | gpt-4o-transcribe | gpt-4o-mini-transcribe
  # transcription_prompt: "prompt opcional para contextualizar o Whisper"
  # audio_preprocessing: demucs  # demucs | noisereduce | deepfilternet (ver seção 5.3)
  runs: 1             # transcrições independentes por música (ver seção 5.4)
  cache: true         # reaproveita transcrições já feitas (padrão: true)
  # cache_dir: data/transcriptions  # padrão: pasta "transcriptions" ao lado de audio_dir

refinement:
  - provider: openai       # openai | anthropic | google
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
    temperature: 0.0       # padrão — use 0.0 para resultados reproduzíveis

metrics:
  - wer
  - cer
  - bertscore

catalog_path: data/catalogo.csv
split: dev                 # dev | test | all — padrão: dev (ver seção 4.4)

drive:
  credentials_path: credentials.json
  token_path: token.json
  audio_dir: data/inputs   # onde os MP3s são baixados e cacheados

results_path: results

analysis:                  # opcional — ver seção 8.4
  bootstrap_samples: 10000
  confidence: 0.95
  severe_failure_threshold: 0.2
  seed: 0
  length_ratio_min: 0.7    # alerta "curta" (seção 8.5)
  length_ratio_max: 1.3    # alerta "longa"
```

### 5.2 Provedores e modelos disponíveis

| Provider | Modelos sugeridos |
|---|---|
| `openai` | `gpt-4o`, `gpt-4o-mini` |
| `anthropic` | `claude-opus-4-7`, `claude-sonnet-4-6` |
| `google` | `gemini-2.0-flash`, `gemini-1.5-pro` |

Para o Whisper:

| Modelo | Notas |
|---|---|
| `whisper-1` | Sem suporte a prompt de contexto |
| `gpt-4o-transcribe` | Suporta `transcription_prompt`; usa prompt padrão do projeto se omitido |
| `gpt-4o-mini-transcribe` | Versão mais leve; sem prompt padrão automático |

**Transcrição por LLM multimodal.** Além do `whisper` (API de transcrição da
OpenAI), `transcription.provider` aceita `google` (Gemini) e `openai-audio`
(`gpt-audio`, `gpt-audio-mini`): o LLM ouve o áudio e escreve a letra direto.
Serve de **grupo de controle** para a conferência com áudio: se transcrever direto
já rende o mesmo que conferir um rascunho, a conferência não acrescenta nada. O
prompt padrão não informa título, autoria nem intérprete (não dá para acertar por
memorização); `transcription_prompt` o substitui. Funciona com `runs`, cache e
`consensus`, mas só aceita áudio `.mp3`/`.wav` (não use com formatos convertidos).

```yaml
transcription:
  provider: openai-audio
  model: gpt-audio
  runs: 5
```

O Gemini precisa de `GOOGLE_API_KEY`. Respostas bloqueadas pelo provedor (filtro
de recitação de letras) contam como falha da rodada.

### 5.3 Pré-processamento de áudio

O campo `audio_preprocessing` aplica um tratamento ao MP3 antes de enviá-lo para
o Whisper. Apenas uma opção pode ser usada por experimento; omitir o campo
significa transcrever o MP3 original.

```yaml
transcription:
  provider: whisper
  model: gpt-4o-transcribe
  audio_preprocessing: demucs  # demucs | noisereduce | deepfilternet
```

| Valor | O que faz | Arquivo gerado em `data/inputs/` |
|---|---|---|
| `demucs` | Separa a voz dos instrumentos (modelo `htdemucs`) | `<nome>_vocals.wav` |
| `noisereduce` | Reduz ruído estacionário (chiado, hum) | `<nome>_denoised.wav` |
| `deepfilternet` | Supressão de ruído com rede neural (DeepFilterNet) | `<nome>_deepfiltered.wav` |

**Como funciona:**
- O Whisper transcreve o `.wav` processado — o MP3 original não é alterado
- Cache automático: se o `.wav` já existir, o processamento não roda novamente
- Se o pré-processamento falhar, a música é pulada e o erro aparece no log
- As três bibliotecas já estão nas dependências do projeto (`uv sync`); demucs e
  deepfilternet trazem PyTorch e são pesadas

> **Atenção:** essas ferramentas foram treinadas principalmente em áudio moderno.
> Nos experimentos até agora, todas pioraram o WER em gravações de 1920-1950
> (noisereduce e deepfilternet de forma severa). Teste com um subconjunto antes
> de rodar no dataset completo.

### 5.4 Rodadas e cache de transcrições

A mesma configuração de transcrição pode produzir resultados bem diferentes de
uma execução para outra — o modelo às vezes troca palavras, pula ou repete
trechos. Para medir com confiança, cada música pode ser transcrita várias vezes:

```yaml
transcription:
  model: gpt-4o-transcribe
  runs: 5
```

- Cada rodada gera uma linha de baseline, e cada refinamento configurado é
  aplicado à transcrição de **cada** rodada. As colunas `run` do CSV/JSON
  identificam a rodada.
- As transcrições ficam salvas em `data/transcriptions/`, separadas por modelo,
  prompt de transcrição e pré-processamento. Um experimento novo com a mesma
  configuração de transcrição **reaproveita** as transcrições salvas em vez de
  chamar a API — assim, dois experimentos de refinamento comparam métodos sobre
  exatamente as mesmas transcrições, e a transcrição não é paga de novo.
- Aumentar `runs` (por exemplo, de 3 para 5) só transcreve as rodadas que faltam.
- Se o arquivo de áudio mudar, as transcrições antigas daquela música são
  ignoradas e refeitas.
- Rodadas que falharem não são salvas e são refeitas na próxima execução.
- Para forçar transcrições novas sem apagar o cache, use `cache: false`.

> **Atenção:** o custo de refinamento cresce com o número de rodadas — com
> `runs: 5` e 4 refinamentos, são 20 chamadas de LLM por música.

**Transcrição de consenso.** Com `runs` ≥ 3, `consensus: true` adiciona o método
`consensus/medoid`: entre as rodadas de cada música, usa-se a transcrição mais
parecida com as demais (menor soma de distâncias de edição em palavras). Não chama
API nem usa a letra, e o texto é sempre uma das transcrições originais. Ele é
comparado com o baseline como qualquer outro método (seção 8.4): o ganho mostra
quanto escolher a transcrição "central" melhora sobre uma rodada qualquer.

```yaml
transcription:
  runs: 5
  consensus: true
```

### 5.5 Conferência com áudio

A conferência pega o rascunho (a transcrição de uma rodada, ou o consenso) e o
envia a um modelo que **ouve a gravação** e devolve uma lista de alterações
pontuais. O pipeline aplica as alterações; o modelo nunca reescreve a letra.

```yaml
verification:
  - provider: openai-audio        # openai-audio | google
    model: gpt-audio
    prompt_file: prompts/verification/edits_v1.yaml
    audio: original               # original | isolated | none
    metadata: false
    draft: run                    # run | consensus
    max_runs: 2                   # opcional: confere só as 2 primeiras rodadas
```

| Opção | Valores |
|---|---|
| `audio` | `original` (MP3 do catálogo), `isolated` (voz isolada com demucs), `none` (sem áudio: controle que mede quanto do ganho vem de ouvir) |
| `metadata` | `true` inclui título, autoria, intérprete e ano no prompt (mede o efeito de o modelo "conhecer" a música) |
| `draft` | `run` (cada rodada) ou `consensus` (a transcrição mais central, exige `runs` ≥ 3) |
| `max_runs` | quantas rodadas conferir por música (padrão: todas) |

Cada entrada é uma **variante** e aparece como um método próprio no relatório,
com o nome `edits_v1 · áudio=original · meta=não · rascunho=run`.

**Como o modelo indica as alterações.** O rascunho é dividido em segmentos
numerados (`[1] ...`, `[2] ...`) e o modelo responde em JSON:

```json
{"edits": [
  {"op": "replace", "segment": 4, "old": "toca sulto", "new": "toca surdo", "heard": "..."},
  {"op": "insert",  "segment": 7, "new": "trecho cantado que faltava"},
  {"op": "delete",  "segment": 9, "old": "trecho que não é cantado"}
]}
```

Uma alteração só é aplicada se o trecho `old` aparece exatamente uma vez no
segmento; caso contrário é rejeitada, com o motivo registrado. Uma resposta que
não seja esse JSON conta como **falha** da avaliação, não como "nenhuma
alteração".

Use as variantes para separar efeitos: compare com a transcrição direta do
**mesmo modelo** (seção 5.2), com `audio: none` e com `metadata: true`. Antes de
rodar o conjunto inteiro, teste o prompt em 2 ou 3 músicas de desenvolvimento.

### 5.6 Métricas disponíveis

| Métrica | Descrição | Interpretação |
|---|---|---|
| `wer` | Word Error Rate | Menor é melhor (0 = perfeito) |
| `cer` | Character Error Rate | Menor é melhor (0 = perfeito) |
| `bertscore` | BERTScore F1 | Maior é melhor (1 = perfeito) |

> **Normalização:** WER e CER convertem para minúsculas e ignoram pontuação antes
> do cálculo, penalizando apenas diferenças de conteúdo lexical. Acentuação é
> preservada — "nao" vs "não" ainda conta como erro.

### 5.7 Exemplos de baterias de testes

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
catalog_path: data/catalogo.csv
drive:
  audio_dir: data/inputs
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
catalog_path: data/catalogo.csv
drive:
  audio_dir: data/inputs
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
catalog_path: data/catalogo.csv
drive:
  audio_dir: data/inputs
```

---

## 6. Configuração dos prompts

Os prompts ficam em `prompts/` e são referenciados pelo campo `prompt_file` no YAML
do experimento.

### 6.1 Formato do arquivo de prompt

```yaml
name: nome-do-prompt          # identificador no relatório
description: "Descrição"      # texto livre para documentação
system: |
  Instrução de sistema para o LLM.
user: |
  Música: {titulo}
  Autoria: {autoria}
  Intérprete: {interpretacao}
  Ano: {ano}

  Instrução do usuário. Use {transcription} onde a
  transcrição do Whisper deve ser inserida.
examples:                     # opcional — para prompts few-shot
  - input: "texto de entrada"
    output: "texto corrigido"
```

### 6.2 Variáveis disponíveis nos prompts

O bloco `user:` suporta as seguintes variáveis, preenchidas automaticamente pelo
pipeline com os dados de cada música do catálogo:

| Variável | Origem |
|---|---|
| `{transcription}` | Transcrição bruta gerada pelo Whisper |
| `{titulo}` | Coluna `Música` do catálogo |
| `{autoria}` | Coluna `Autoria` do catálogo |
| `{interpretacao}` | Coluna `Interpretação` do catálogo |
| `{ano}` | Coluna `Ano` do catálogo |

Variáveis ausentes no template são substituídas por string vazia (sem erro).

### 6.3 Prompts disponíveis

| Arquivo | Estratégia |
|---|---|
| `prompts/minimalist.yaml` | Correção ortográfica mínima sem contexto adicional |
| `prompts/conservative.yaml` | Intervenção mínima com regras explícitas contra truncamento, inserção/remoção de palavras e dialetização |
| `prompts/targeted_domain.yaml` | Corrige erros típicos de ASR em 78 rpm (nomes próprios, vocabulário raro do samba), sem dialetizar |
| `prompts/rich_context.yaml` | Contexto histórico rico sobre sambas antigos |
| `prompts/archaic_vocab.yaml` | Foco em vocabulário arcaico, gírias e contrações fonéticas |
| `prompts/few_shot.yaml` | Exemplos de correção guiando o modelo (few-shot) |

### 6.4 Criando um prompt personalizado

Crie um novo arquivo em `prompts/` e referencie-o no YAML do experimento:

```yaml
name: meu_prompt
description: "Minha estratégia personalizada"
system: |
  Sua instrução de sistema aqui.
user: |
  Música: {titulo}
  Intérprete: {interpretacao}

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

Para refazer a análise estatística de uma execução que já existe (inclusive as
antigas, de antes das rodadas), sem chamar nenhuma API:

```bash
uv run python -m benchmark analyze results/<experimento>_<timestamp>/results.json
```

Opções: `-o PASTA` grava `stats.json` e `report.html` em outra pasta (por padrão,
sobrescreve os da pasta do `results.json`), `--severe-threshold` e `--seed`.

### 7.2 Acompanhando a execução

No modo `normal`, o log exibe o progresso de cada música e experimento:

```
INFO  Catálogo carregado: 28 música(s)
INFO  [1/28] Cartola — As Rosas Não Falam
INFO    Download concluído
INFO    Transcrição concluída
INFO    [1/4] openai/gpt-4o [prompts/minimalist.yaml]
INFO      OK — tokens: 312, tempo: 1823ms
INFO    [2/4] openai/gpt-4o [prompts/rich_context.yaml]
INFO      OK — tokens: 487, tempo: 2104ms
INFO  [2/28] Nelson Cavaquinho — Folhas Secas
INFO    Usando cache: folhas_secas.mp3
INFO    Transcrição concluída
...
INFO  Resultados salvos em: results/experimento-01_20260509_143022
```

Quando o áudio já foi baixado anteriormente, o log exibe `Usando cache: <arquivo>` e
o download é ignorado.

Para detalhes de cada chamada de API, use o modo `verbose` no YAML:

```yaml
logging:
  mode: verbose
```

### 7.3 Resiliência e retry

O pipeline tem retry automático com backoff exponencial para chamadas de API.
Se uma resposta do LLM for truncada por limite de tokens, ela é descartada e a
chamada é repetida automaticamente. Se o provedor *bloquear* a resposta (filtro
de conteúdo ou de recitação de letras), a avaliação é registrada como erro, sem
repetir a chamada: o bloqueio se repete e o texto devolvido viria cortado. Falhas isoladas nunca derrubam o pipeline —
o erro é registrado no CSV/HTML e a execução continua para as demais músicas.

---

## 8. Interpretando os resultados

Ao final de cada execução, os resultados são salvos em:

```
results/
└── {experiment_name}_{timestamp}/
    ├── results.csv    ← tabela com todos os experimentos
    ├── results.json   ← mesmos dados em formato JSON
    ├── stats.json     ← análise estatística (seção 8.4)
    └── report.html    ← relatório visual com ranking e análise estatística
```

### 8.1 Relatório HTML

Abra o `report.html` no navegador para visualizar:

- **Ranking por combinação:** média das métricas de cada combinação LLM + prompt,
  ordenada da melhor para a pior
- **Análise estatística:** comparação de cada método com o baseline, com
  intervalos de confiança (seção 8.4). **Prefira esta seção ao ranking** para
  concluir se um método ajuda: a média sozinha pode enganar
- **Resultados por música:** métricas individuais de cada experimento por música,
  facilitando a identificação de casos onde uma abordagem se destaca

### 8.2 Arquivo CSV

Cada linha representa uma avaliação: uma música × uma rodada × uma combinação
LLM + prompt. A linha com `refinement_provider` igual a `baseline` é a transcrição
bruta, sem nenhum refinamento.

Colunas principais:

| Coluna | Descrição |
|---|---|
| `song_id` | Identificador único gerado por slugify: `{interpretacao}-{titulo}` |
| `split` | Conjunto da música: `dev` ou `test` |
| `run` | Rodada de transcrição (1 a `runs`) |
| `titulo` | Título da música |
| `autoria` | Compositor(es) |
| `interpretacao` | Intérprete(s) |
| `disco` | Nome do disco |
| `ano` | Ano de gravação |
| `genero` | Gênero musical |
| `refinement_provider` | Provedor LLM (vazio = baseline sem refinamento) |
| `refinement_model` | Modelo utilizado |
| `prompt_name` | Nome do prompt |
| `prompt_file` | Caminho do arquivo de prompt |
| `wer` / `cer` / `bertscore` | Scores das métricas |
| `tokens_used` | Total de tokens consumidos |
| `response_time_ms` | Tempo de resposta da API em ms |
| `error` | Mensagem de erro, se houver |

### 8.3 Entendendo o baseline

Todo experimento inclui automaticamente uma linha de **baseline** por música:
a transcrição bruta do Whisper avaliada sem nenhum refinamento.
Isso permite medir exatamente o ganho (ou perda) de cada estratégia de LLM.

### 8.4 Análise estatística

A média das métricas (o ranking) pode enganar: a revisão com LLM costuma
melhorar levemente quase todas as músicas e, de vez em quando, destruir uma —
essa única falha puxa a média para o lado errado. Por isso o relatório traz, para
cada método e cada métrica, uma comparação **pareada** com o baseline.

**Como é calculada.** Cada revisão é comparada com o baseline da *mesma música e
da mesma rodada* (mesma transcrição de partida). O resultado é o **ganho**:
positivo significa que o método melhorou a métrica (para WER/CER, o valor
diminuiu; para BERTScore, aumentou). O ganho de uma música é a média das suas
rodadas — a música é a unidade de análise.

| Coluna | Como ler |
|---|---|
| Ganho médio [IC] | Média do ganho entre músicas, com intervalo de confiança (padrão 95%, por bootstrap). Sensível a falhas isoladas |
| Ganho mediano [IC] | Ganho da música típica. Pouco afetado por falhas isoladas |
| Melhorou / empatou / piorou | Em quantas músicas o método ganhou, empatou e perdeu para o baseline |
| p (Wilcoxon) | Teste de postos sinalizados sobre os ganhos por música. Não é corrigido para múltiplas comparações |
| Falhas graves | Avaliações em que a métrica piorou mais que o limite (padrão 0,2) |
| Pior caso | Música com a maior piora |

Em verde, o intervalo está todo acima de zero (melhora confiável); em vermelho,
todo abaixo (piora confiável). Se o intervalo inclui o zero, a diferença pode ser
só variação.

**Exemplo de leitura.** Ganho médio negativo e ganho mediano positivo, com 17
músicas melhores e 2 piores, indicam que o método ajuda na maioria das músicas
mas tem uma falha grave — olhe o "pior caso".

O resumo do baseline mostra a média, a mediana, o desvio entre músicas e, com
mais de uma rodada, a **variação entre rodadas** (desvio médio das rodadas de
uma mesma música): é o ruído da transcrição, que diferenças pequenas entre
métodos precisam superar.

Os parâmetros ficam no bloco opcional `analysis` do YAML:

```yaml
analysis:
  bootstrap_samples: 10000       # reamostragens do bootstrap
  confidence: 0.95               # nível dos intervalos
  severe_failure_threshold: 0.2  # piora que conta como falha grave
  seed: 0                        # semente (resultado reproduzível)
```

O `stats.json` guarda todos esses números para uso em tabelas e gráficos.

### 8.5 Diagnóstico de erros

O WER diz *quanto* errou, não *como*. A seção "Diagnóstico de Erros" do relatório
(chave `errors` do `stats.json`) separa o WER em três partes, dividindo pelo número
de palavras da letra, de modo que **substituições + omissões + inserções = WER**:

| Coluna | Significado |
|---|---|
| Substituições | Palavra ouvida/trocada por outra |
| Omissões | Palavra da letra que sumiu da transcrição |
| Inserções | Palavra na transcrição que não existe na letra |
| Razão de comprimento | Palavras da transcrição ÷ palavras da letra (mediana entre músicas) |

Alertas, contados por avaliação (música × rodada):

- **WER 0**: improvável em gravação de 78 rpm; suspeite de letra copiada,
  memorização do modelo ou erro na referência.
- **Curta** (razão < 0,7): trechos pulados. Numa revisão com LLM, é o sinal de
  resposta cortada ou recusada.
- **Longa** (razão > 1,3): trechos inventados ou repetidos.

Uma revisão que *omite* muito mais que o baseline está resumindo ou cortando, e
não corrigindo. O diagnóstico também funciona em resultados antigos:
`benchmark analyze results.json`.

### 8.6 Conferência com áudio: alterações

Quando há variantes de conferência, a seção "Conferência com Áudio: Alterações"
(chave `verification` do `stats.json`) mostra, por variante:

| Coluna | Como ler |
|---|---|
| Falhas (bloqueio / formato / outras) | Avaliações sem resultado: o provedor bloqueou (filtro de recitação), a resposta não era JSON válido ou outro erro. **Ficam fora da análise pareada**, então uma variante com muitas falhas pode parecer melhor do que é |
| Sem alteração | Respostas `{"edits": []}` |
| Propostas / aplicadas | Alterações sugeridas e as que passaram nas regras |
| Úteis / neutras / prejudiciais | Cada alteração aplicada, testada sozinha sobre o rascunho: reduziu, manteve ou aumentou o WER contra a letra |
| Reescritas | Avaliações em que mais de 30% das palavras mudaram (`analysis.max_change_fraction`) |
| Principal motivo de rejeição | Ex.: trecho não encontrado, ambíguo, sobreposto |

Muitas alterações prejudiciais indicam que o modelo "corrige" o que estava
certo; poucas propostas e muitas úteis indicam um verificador conservador e
preciso. O campo `verification` do `results.json` guarda, por avaliação, o
rascunho, os segmentos, cada alteração e a resposta bruta do modelo.

---

## 9. Dicas e boas práticas

**Comece pequeno:** teste com 2-3 músicas antes de rodar o catálogo completo.
Isso reduz custo e tempo, e permite validar que tudo está configurado corretamente.

**Reaproveite os áudios:** os MP3s baixados ficam em `data/inputs/`. Em experimentos
subsequentes, o pipeline detecta os arquivos existentes (pelo nome na coluna `Arquivo`)
e não faz novo download. Rode quantos experimentos quiser sem custo adicional de rede.

**Isole uma variável por vez:** para comparar prompts, mantenha o mesmo provedor e
modelo. Para comparar provedores, use o mesmo prompt.

**Use o modo verbose para debugging:** ative `mode: verbose` para ver exatamente o
que está sendo enviado e recebido das APIs.

**Acompanhe os logs:** os arquivos em `logs/` permitem revisar execuções anteriores,
incluindo erros e tempos de resposta.

**Nomeie os experimentos com clareza:** use nomes descritivos como
`comparacao-prompts-openai-2026-05` para facilitar a organização dos resultados.

**Ground truth é tudo:** o benchmark só é tão bom quanto a qualidade das letras
no catálogo. Revise cada entrada da coluna `Letra` com cuidado antes de rodar.

---

## 10. Solução de problemas

**Erro: `No API key was provided`**
Verifique se o arquivo `.env` existe na raiz do projeto e contém a chave correta.

**Erro: `FileNotFoundError` no catálogo**
Confirme que o campo `catalog_path` no YAML aponta para o arquivo correto
(padrão: `data/catalogo.csv`).

**Erro: `URL inválida do Google Drive`**
A URL na coluna `URL` do catálogo não segue o formato esperado. Deve conter
`/file/d/<ID>/`. Verifique o link de compartilhamento do arquivo no Drive.

**Erro: `Acesso bloqueado` no browser ao autenticar**
Seu e-mail não está na lista de usuários de teste do app OAuth.
Acesse: Google Cloud Console → APIs e Serviços → Tela de Permissão OAuth →
Público Alvo → adicione seu e-mail como usuário de teste.

**Música pulada com `Arquivo não encontrado e Google Drive não configurado`**
O arquivo MP3 não está em `data/inputs/` e o `credentials.json` não foi encontrado.
Verifique se o `credentials.json` está na raiz do projeto.

**Experimento registrado com erro no CSV**
Uma chamada de API falhou após todas as tentativas de retry (incluindo truncamentos).
Verifique o arquivo de log para detalhes. O pipeline continua normalmente.

**BERTScore muito lento na primeira execução**
Comportamento esperado — o modelo está sendo baixado (~1-2 GB). Nas execuções
seguintes, o cache é utilizado e a métrica roda normalmente.

**Resultado HTML vazio**
Ocorre quando todas as transcrições falharam (nenhum resultado gerado).
Verifique os logs para identificar a causa raiz.
