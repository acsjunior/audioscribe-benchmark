# Protocolo do Estudo

**Status:** rascunho (v0.2, 09/11/2026). Os itens marcados **[PENDENTE]** precisam de
decisão antes das execuções oficiais. Quando todos estiverem resolvidos, o protocolo é
congelado (versão 1.0, com data e commit). A partir daí, qualquer mudança é registrada
na seção 12, com justificativa, e reportada no trabalho.

Este documento é a metodologia do estudo. O [ROADMAP](ROADMAP.md) diz o que foi
construído, e o [MANUAL](MANUAL.md) diz como usar a ferramenta.

---

## 1. Pergunta de pesquisa

Transcrever letras de sambas gravados entre 1920 e 1955 é difícil: gravações em 78 rpm
com ruído, banda estreita, voz misturada aos instrumentos, vocabulário e pronúncia da
época. Modelos de transcrição automática erram palavras e às vezes pulam ou inventam
trechos inteiros, e a revisão só com texto por LLM corrige pelo que é *plausível*, não
pelo que foi *cantado*.

**Pergunta:** um modelo multimodal que **ouve a gravação** e confere um rascunho
automático, propondo alterações pontuais, produz uma transcrição mais fiel à letra
cantada do que o rascunho? Esse ganho vem de ouvir o áudio, e não só de revisar o
texto ou de usar um modelo melhor de ouvido?

## 2. Hipóteses

### Confirmatórias (testadas no conjunto de teste)

Cada hipótese compara **uma** configuração escolhida no conjunto de desenvolvimento
(seção 8) com sua referência, de forma pareada por música.

| # | Hipótese | Comparação |
|---|---|---|
| H1 | A conferência com áudio reduz o WER em relação ao rascunho | conferência vs. baseline |
| H2 | O ganho vem do áudio, e não só do formato de revisão | conferência vs. a mesma conferência sem áudio (`audio: none`) |
| H3 | Conferir um rascunho supera transcrever direto com o mesmo modelo | conferência vs. transcrição direta do mesmo modelo (E6) |

H2 e H3 só são interpretadas se H1 for confirmada.

**Sobre H3.** A conferência usa um modelo multimodal (ex.: `gpt-audio`) que recebe o
áudio *e* o rascunho. Se ela ganhar do rascunho, há duas explicações possíveis: (a)
conferir um rascunho ajuda; ou (b) o modelo multimodal simplesmente ouve melhor que o
transcritor do rascunho, e daria o mesmo resultado transcrevendo sozinho. H3 separa as
duas: o mesmo modelo transcreve direto, só com o áudio (E6). Se a conferência não superar
essa transcrição direta, o ganho é do modelo, não do método de conferência — e o método
mais simples (transcrever direto com ele) seria a recomendação.

### Exploratórias (relatadas como tais, sem pretensão confirmatória)

- Efeito dos metadados (título, autoria, intérprete) na conferência: memorização.
- Rascunho de uma rodada vs. rascunho de consenso (E5).
- Áudio original vs. voz isolada.
- Consenso (E5) sozinho vs. baseline.
- Revisão só com texto (prompts de refinamento) vs. baseline.
- Tipos de erro (substituição, omissão, inserção) por método.
- Relação entre o ganho e a década, o intérprete ou o WER do rascunho.

## 3. Conjunto de dados

### 3.1 Critério de inclusão

Uma gravação entra no estudo se cumprir **todos** os critérios:

1. **Gênero**: samba (classificação da Discografia Brasileira).
2. **Gravação** de 1955 ou antes.
3. **Domínio público**: todos os autores (letra e música) faleceram em 1955 ou antes. Em
   coautoria, conta o último coautor a falecer. Isso é verificado música a música, com o
   ano de morte de cada autor e a fonte registrados no catálogo (seção 3.4).
4. **Áudio disponível** na Discografia Brasileira (IMS).
5. **Letra cantada**: a gravação tem voz cantada em português durante a maior parte da
   duração.

**[PENDENTE]** Confirmar como a Discografia Brasileira calcula o "ano de domínio
público" do filtro (`publicDomainYear`): se considera os autores da obra ou só a
gravação. O critério 3 vale de qualquer forma; o filtro serve só para gerar candidatas.

### 3.2 Critérios de exclusão

Uma candidata é excluída, **antes** de qualquer transcrição, se:

- a **fração cantada** da gravação for menor que **[EM DISCUSSÃO]** (ver abaixo);
- o áudio estiver incompleto, cortado ou com defeito que impeça ouvir a letra;
- não for possível estabelecer a letra de referência pelo procedimento da seção 4
  (trechos inaudíveis acima do limite da seção 4.3);
- for outra gravação da mesma composição já incluída (no máximo uma gravação por
  composição).

**Fração cantada.** Estimada por `scripts/sung_fraction.py`: energia da faixa de voz
isolada pelo demucs, em janelas de 50 ms, com limiar relativo à própria gravação (p95
− 20 dB) e suavização (pausas < 1 s contam como canto). Nas 28 músicas do dev:

| Limiar | Média | DP | Mín | Q1 | Mediana | Q3 | Máx |
|---|---|---|---|---|---|---|---|
| 15 dB | 62,6% | 11,7 | 28,1% | 58,1% | 63,4% | 71,2% | 83,8% |
| **20 dB** | **64,8%** | **10,8** | **34,4%** | **59,6%** | **66,1%** | **71,9%** | **85,5%** |
| 25 dB | 66,2% | 10,7 | 39,0% | 59,9% | 67,1% | 73,0% | 86,0% |

A estimativa é estável entre limiares (variação de poucos pontos por música). Uma
gravação típica do período tem cerca de um terço de introdução e interlúdios
instrumentais. Um corte em 75% cantado excluiria 25 das 28 músicas; os candidatos
razoáveis estão entre 40% (exclui 1) e 50% (exclui 2). Casos-limite são confirmados
ouvindo a gravação.

Exclusões e motivos são registrados (seção 3.4). Nenhuma música é excluída depois de
transcrita por causa do resultado.

### 3.3 Divisão em desenvolvimento e teste

| Conjunto | Composição | Uso |
|---|---|---|
| **Desenvolvimento** (`dev`) | as 28 músicas da fase exploratória que cumprirem o critério 3.1 (hoje uma por ano, 1928–1955) | livre: ajustar prompts, escolher configurações, depurar |
| **Teste** (`test`) | músicas novas, sorteadas entre as candidatas | uma única execução, no fim, com tudo congelado |

**Sorteio do teste:**

- candidatas: o filtro de domínio público da Discografia Brasileira (546 sambas em
  09/2026), menos as músicas do dev, menos as excluídas;
- sorteio estratificado por **década** (1920, 1930, 1940, 1950), proporcional ao número
  de candidatas em cada uma, com no máximo **3 músicas por intérprete**;
- semente registrada; o script do sorteio e a lista de candidatas (com data de acesso)
  ficam no repositório;
- se uma sorteada for excluída pelos critérios da seção 3.2, entra a próxima da ordem do
  sorteio no mesmo estrato.

**Tamanho:** não é fixado de antemão. A base será enriquecida com o máximo de músicas
possível, e o número final de músicas do teste é registrado no congelamento (seção 8),
antes de qualquer execução no teste. Referência mínima: 32 músicas.

**[EM DISCUSSÃO]** Com a base crescendo, rever se todas as músicas novas vão para o teste
ou se parte reforça o dev, e se o limite de 3 por intérprete descarta músicas demais.

O dev e o teste não compartilham composições.

### 3.4 Registro no catálogo

Colunas a acrescentar ao `data/catalogo.csv`:

| Coluna | Conteúdo |
|---|---|
| `Split` | `dev` ou `test` |
| `AnoGravacao` | ano da gravação |
| `AnoMorteAutores` | ano de morte do último autor a falecer |
| `FonteDominioPublico` | de onde veio o ano de morte (ex.: Dicionário Cravo Albin, página do IMS) |
| `DominioPublico` | `sim` / `não` |
| `LetraConferida` | data e responsável pela conferência da letra (seção 4) |
| `Exclusao` | vazio, ou o motivo da exclusão |

## 4. Letra de referência

A letra de referência é **o que foi cantado naquela gravação**, não a letra publicada da
composição.

### 4.1 Procedimento

Para cada música, **antes** de ver qualquer transcrição automática dela:

1. Partir de uma letra publicada (fonte registrada na coluna `Fonte`) ou de uma
   transcrição própria.
2. Ouvir a gravação inteira, do começo ao fim, acompanhando a letra.
3. Ajustar a letra ao que é cantado:
   - **repetições**: registrar todas as vezes que um trecho é cantado (refrão, versos
     repetidos), na ordem;
   - **trechos não cantados**: remover estrofes da letra publicada que não aparecem na
     gravação;
   - **variações**: se o cantor troca uma palavra em relação à letra publicada, vale o
     que foi cantado;
   - **falas e cacos**: **[PENDENTE]** incluir ou não falas do intérprete (anúncios,
     "breques", interjeições soltas como "ô", "ai").
4. Ouvir uma segunda vez, inteira, conferindo a versão final.
5. **Decidir a inclusão**: depois da audição completa, a música pode ser **excluída** se
   tiver trechos de dúvida ou inaudíveis (seção 4.3). Essa decisão é tomada **antes** de
   qualquer transcrição automática da música, para não depender de o modelo ter acertado
   ou errado ali; o motivo é registrado em `Exclusao`.
6. Registrar a data e o responsável em `LetraConferida`.

O passo 3 de repetições é importante: no baseline exploratório, 12% das palavras que a
transcrição tinha a mais formavam trechos que existem na letra. Pelo menos parte disso
é refrão cantado e não registrado na referência, e penalizaria uma transcrição correta.
**As 28 letras do dev também passam por este procedimento.**

### 4.2 Grafia

- Ortografia padrão atual, inclusive para palavras de época.
- Contrações faladas, na forma cantada: **[PENDENTE]** "pro" ou "para o", "tá" ou "está"
  (proposta: como foi cantado, já que é isso que o transcritor ouve).
- Pontuação e quebras de linha são livres: a avaliação ignora pontuação, maiúsculas e
  quebras de linha (seção 6.2).

### 4.3 Trechos inaudíveis ou duvidosos

A letra de referência só contém trechos que o anotador ouviu com segurança. Se a
gravação tiver trechos de dúvida ou inaudíveis, a música é excluída (passo 5 da seção
4.1), em vez de entrar com um palpite: um palpite errado penalizaria uma transcrição
correta, e um certo premiaria a memorização.

### 4.4 Concordância entre anotadores (recomendado)

**[PENDENTE]** Uma segunda pessoa confere de forma independente uma amostra aleatória
(proposta: 20% das músicas, sorteadas). O relatório traz o WER entre as duas versões da
referência. Isso mostra o piso de erro da própria referência: diferenças entre métodos
menores que essa discordância não podem ser atribuídas aos métodos.

## 5. Métodos comparados

| Método | Descrição | Entregável |
|---|---|---|
| Baseline | transcrição do modelo de transcrição, sem revisão | E1/E3 |
| Revisão só com texto | LLM revisa o texto da transcrição | (existente) |
| Consenso | a transcrição mais central entre as rodadas | E5 |
| Transcrição direta multimodal | LLM ouve o áudio e escreve a letra | E6 |
| Conferência com áudio | LLM ouve o áudio e propõe alterações no rascunho | E7 |

**Baseline do estudo:** **[PENDENTE: definido pelo E3]**, entre `whisper-1` e
`gpt-4o-transcribe`. Na fase exploratória o `gpt-4o-transcribe` foi melhor (WER ≈ 0,17–0,21
contra ≈ 0,27), mas com uma rodada só.

**Prompt de transcrição:** o `gpt-4o-transcribe` usa o prompt padrão do código
(`DEFAULT_PROMPT_GPT4O_TRANSCRIBE`), que descreve o gênero e a época e cita artistas do
período, mas não a música transcrita. Fica fixo para todas as músicas.

**Áudio anônimo:** todo áudio é enviado aos modelos com nome de arquivo neutro
(`audio.mp3`) e sem tags ID3 (`audio_utils.py`). Sem isso, a API de transcrição recebe o
nome do arquivo, que é "Música - Intérprete.mp3". Metadados só chegam ao modelo quando a
variante os inclui explicitamente no prompt (seção 10).

**Prompts de conferência:** ajustados **só no dev** (piloto, seção 8). O prompt usado no
teste é congelado com nome e hash.

## 6. Medidas

### 6.1 Métrica principal

**WER** (taxa de erro por palavra) entre a transcrição final e a letra de referência.

### 6.2 Normalização

Antes de qualquer métrica: minúsculas; pontuação substituída por espaço (inclusive
hífen: "corda-bamba" vira "corda bamba"); espaços e quebras de linha colapsados;
**acentos mantidos**. Implementação: `metrics/base.py::normalize`.

### 6.3 Medidas secundárias

- CER (taxa de erro por caractere) e BERTScore (similaridade semântica).
- Decomposição do WER: substituições, omissões e inserções; razão de comprimento.
- Conferência: taxa de falhas (bloqueio, formato), alterações propostas/aplicadas,
  precisão por alteração (úteis / neutras / prejudiciais), alertas de reescrita.

## 7. Desenho experimental e análise

### 7.1 Rodadas

- Transcrição: **n = 5** rodadas independentes por música e configuração
  **[PENDENTE: confirmar após E3]**.
- Conferência e revisão: aplicadas às **2 primeiras rodadas** de cada música
  (`max_runs: 2`) **[PENDENTE: confirmar após o piloto, conforme o custo]**.
- Todas as transcrições ficam em cache: todos os métodos são comparados sobre os
  mesmos rascunhos.
- Temperatura 0 em todas as chamadas a LLM.

### 7.2 Unidade de análise e ganho

- **Unidade = música.** Rodadas da mesma música não são independentes.
- **Ganho** por avaliação = WER(referência do método) − WER(método), pareado por música
  e rodada; positivo = melhora. **Ganho por música** = média do ganho nas rodadas.

### 7.3 Teste das hipóteses

**[EM DISCUSSÃO]** Escolha do teste estatístico e da correção para múltiplas
comparações (proposta inicial: Wilcoxon e Holm). A decisão, com a justificativa, entra
aqui.

**Critério de sucesso (H1):** a hipótese é confirmada se, ao mesmo tempo:

1. o teste escolhido acima rejeitar a hipótese nula, já com a correção para
   múltiplas comparações, a α = 0,05;
2. o limite inferior do IC 95% do efeito estimado for maior que zero;
3. a taxa de falhas graves (avaliações em que o WER piora mais de 0,2 em relação ao
   rascunho) for no máximo **[PENDENTE: proposta 5%]**. A média esconde falhas raras e
   catastróficas; este critério impede que um método que melhora pouco quase sempre e
   destrói algumas músicas seja declarado bem-sucedido.

> Nota de implementação: a correção de Holm ainda não está no código
> (`reporting/stats.py` reporta p-valores sem correção). Precisa ser acrescentada antes
> da execução no teste, ou aplicada à mão sobre os três p-valores.

Também é relatado se o ganho mediano supera o **ruído entre rodadas** do baseline (desvio
médio do WER entre rodadas da mesma música), para dar escala ao efeito.

**[PENDENTE]** Tamanho mínimo de efeito com relevância prática (proposta: ganho mediano
de 0,02 de WER, cerca de 3 palavras numa letra mediana de 157 palavras).

### 7.4 Falhas e dados ausentes

- **Bloqueio do provedor** (filtro de conteúdo/recitação) e **resposta mal formada**:
  a avaliação sai da análise pareada e é contada como falha do método. A taxa de falha
  por método é relatada junto ao ganho. **Análise de sensibilidade:** repetir H1
  contando cada falha como ganho zero (o método devolveria o rascunho).
- **Falha de transcrição** numa rodada: a rodada fica sem baseline e sai de todas as
  comparações. Se uma música tiver menos de 3 rodadas válidas, ela é relatada e
  excluída das comparações que dependem de consenso.
- Nenhuma música é excluída por ter resultado ruim.

### 7.5 Relatório

Para cada método, sobre as músicas:

- **distribuição** do WER e do ganho: média, desvio padrão, mínimo, Q1, mediana (Q2),
  Q3 e máximo;
- ganho médio e mediano com IC, vitórias / empates / derrotas, p-valor;
- falhas graves, falhas do provedor e piores casos. Os
resultados do dev são relatados à parte e rotulados como desenvolvimento.

## 8. Ordem das execuções

1. **Catálogo final**: inclusão/exclusão, sorteio do teste, letras conferidas (seções 3
   e 4).
2. **E3, no dev**: `whisper-1` e `gpt-4o-transcribe`, n = 5. Define o baseline e mede o
   ruído entre rodadas.
3. **Piloto do E7, no dev**: 3 músicas, ajuste do prompt de conferência.
4. **Bateria no dev**: todos os métodos e variantes (seção 5). Escolha, **no dev**, da
   configuração de cada hipótese:
   - conferência: a variante com maior ganho mediano no dev;
   - controle sem áudio e transcrição direta: a mesma configuração, só mudando o fator
     testado.
5. **Congelamento**: protocolo v1.0, configurações, prompts, versões de modelo e commit
   registrados.
6. **Execução única no teste**: `split: test`, configurações congeladas. Nada é ajustado
   depois.

Se a etapa 4 mostrar que a conferência não ganha nada nem no dev, o estudo segue para o
teste mesmo assim, com a melhor configuração do dev: um resultado negativo também é
resultado (ponto de decisão do roadmap sobre E8/E9).

## 9. Reprodutibilidade

- Código: commit registrado de cada execução oficial.
- Configurações: os YAML de cada execução, versionados.
- Modelos: nomes exatos e data da execução (`whisper-1`, `gpt-4o-transcribe`,
  `gpt-audio`, …). Modelos de API mudam sem aviso; a data é o melhor registro possível.
- Transcrições: o cache (`data/transcriptions/`) guarda cada transcrição com o hash do
  áudio e do prompt.
- Resultados: `results.json` guarda, por avaliação, os textos, as métricas e, na
  conferência, a resposta bruta do modelo e o destino de cada alteração.
- Sorteios: semente e script no repositório.

## 10. Ameaças à validade

- **Memorização**: os modelos podem conhecer letras famosas e "acertar" sem ouvir.
  Mitigação em duas partes:
  1. **por padrão, nada identifica a música**: áudio com nome neutro e sem tags ID3, e
     prompts sem título, autoria, intérprete ou ano;
  2. **efeito medido**: a mesma variante de conferência roda com e sem metadados
     (`metadata: true/false`), sobre os mesmos rascunhos e o mesmo áudio. A diferença
     pareada entre as duas estima quanto do resultado vem de o modelo saber qual é a
     música. Hipótese exploratória.

  Um modelo ainda pode reconhecer a música pelo próprio áudio; isso não é controlável e
  é relatado como limitação.
- **Referência imperfeita**: mitigada pelo procedimento da seção 4 e pela concordância
  entre anotadores (4.4).
- **Não determinismo das APIs**: mesmo com temperatura 0, as respostas variam; mitigado
  pelas rodadas e pela análise pareada.
- **Modelos que mudam ou somem**: o `gpt-4o-audio-preview` deixou de existir durante o
  projeto. Mitigação: registro de versão e data (seção 9).
- **Generalização**: sambas de 1928–1955 de um único acervo; os resultados não se
  estendem automaticamente a outros gêneros ou épocas.
- **Viés de seleção**: músicas bloqueadas pelos filtros de recitação tendem a ser as mais
  conhecidas; a taxa de falha por método é relatada.

## 11. Estudo exploratório anterior

A fase exploratória (maio/2026; 28 músicas; uma rodada por configuração) motivou este
protocolo e é citada como estudo exploratório. Seus resultados ficam arquivados e não
entram nas análises confirmatórias. Principais achados: grande variação entre rodadas da
mesma configuração; a média enganava por uma única falha (`alcides-gerardi-antonico`,
causada pelo filtro de conteúdo do `gpt-4o`); o pré-processamento de áudio não ajudou.

## 12. Registro de alterações do protocolo

| Versão | Data | Alteração | Motivo |
|---|---|---|---|
| 0.1 | 09/11/2026 | Rascunho inicial | — |
| 0.2 | 09/11/2026 | H3 explicada; fração cantada medida no dev (3.2); tamanho do teste em aberto (3.3); exclusão por trechos duvidosos após a audição, antes da transcrição (4.1, 4.3); áudio anônimo (5, 10); distribuição completa no relatório (7.5); teste estatístico em discussão (7.3) | Revisão do rascunho |
