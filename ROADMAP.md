# Roadmap

Plano de evolução do benchmark de um estudo exploratório para um protocolo
reproduzível, com vistas a um trabalho acadêmico.

## Contexto

A fase exploratória (maio/2026, 28 músicas, uma rodada por configuração) mostrou:

- **Variação grande entre execuções**: com a mesma configuração, o WER de uma
  mesma música chegou a variar 0,30 entre duas rodadas. Diferenças de 0,01–0,03
  entre métodos estão dentro desse ruído.
- **A média engana**: a revisão com LLM tende a melhorar levemente a maioria das
  músicas, mas falha de forma catastrófica em algumas, o que puxa a média para cima.
  É preciso medir separadamente o ganho típico (mediana, vitórias) e a taxa de
  falhas graves.
- **Revisão só com texto não tem evidência**: o LLM corrige pelo que é plausível,
  não pelo que foi cantado. Daí a hipótese de conferência com áudio (E7).

Os resultados dessa fase serão arquivados e citados como estudo exploratório.

## Conjunto de dados

- **Critério de inclusão**: gravação e composição em domínio público (gravação
  até 1955; todos os autores falecidos até 1955 — em coautoria, conta o último
  coautor vivo). Fonte de candidatas: filtro de domínio público da Discografia
  Brasileira (IMS), a confirmar como o site calcula o ano de domínio público.
- **Desenvolvimento (`dev`)**: as 28 músicas atuais que passarem no critério.
  Usadas livremente para ajustar prompts e métodos.
- **Teste (`test`)**: músicas novas, sorteadas (semente registrada) entre as
  candidatas, com no máximo 3 por intérprete e equilíbrio por década. Mínimo de
  32; ideal 40–45. Só rodadas uma vez, no final, com as configurações congeladas.
- **Letra de referência**: transcrita/conferida contra a gravação, seguindo um
  procedimento escrito único para todas as músicas (inclusive as 28 antigas).

## Entregáveis

### Fase 0 — Protocolo

**E0. Protocolo do estudo** — 📝 rascunho em [PROTOCOLO.md](PROTOCOLO.md) (itens pendentes marcados)
Documento com hipóteses, métrica principal, análise estatística, critérios de
inclusão, procedimento de conferência de letras, divisão dev/teste e registro de
versões de modelos. Vira a seção de metodologia do trabalho.

### Fase 1 — Medir direito

**E1. Repetições e cache de transcrições** — ✅ concluído
Cada música é transcrita `n` vezes (`transcription.runs`); as transcrições ficam em
cache em disco e são reaproveitadas entre experimentos, para que métodos de revisão
sejam comparados sobre exatamente as mesmas transcrições. Inclui a coluna `Split`
no catálogo e o filtro `split` no YAML (padrão `dev`).

**E2. Relatório estatístico** — ✅ concluído
Comparação pareada de cada método com o baseline (mesma música e rodada): ganho
médio e mediano com intervalo de confiança por bootstrap sobre as músicas, em
quantas músicas melhorou/empatou/piorou, Wilcoxon e taxa de falhas graves; no
baseline, o ruído entre rodadas. Sai em `stats.json` e no `report.html`, e o
comando `benchmark analyze` refaz a análise de resultados existentes.
Revisado com o E0: Wilcoxon com zeros pelo método de Pratt, estimativa de
Hodges–Lehmann, teste do sinal, WER do corpus com bootstrap pareado, p ajustado por
Holm/BH e o comando `benchmark confirm` para as hipóteses confirmatórias em sequência
fixa (PROTOCOLO 7.3).

> Na reanálise dos resultados exploratórios, a "piora" da revisão com LLM veio
> de uma única música (`alcides-gerardi-antonico`, piora de ~0,7–0,86 em todos os
> prompts); na música típica o ganho era pequeno e positivo. Investigar essa
> falha é parte do E4.

**E3. Remedir a linha de base** *(experimento)*
`whisper-1`, `gpt-4o-transcribe` e `gpt-4o-transcribe` + `conservative`, com
n=5, no conjunto dev. Define a referência a ser batida.

**E4. Diagnóstico de tipos de erro** — ✅ concluído
WER decomposto em substituições, omissões e inserções; razão de comprimento
transcrição/letra; alertas para resultados suspeitos (WER 0, transcrição curta ou
longa demais). Sai em `stats.json` (`errors`) e no `report.html`.

> **Falha de `alcides-gerardi-antonico` esclarecida**: não era erro de revisão. O
> `gpt-4o` devolvia a letra cortada em ~18 palavras (razão de comprimento 0,11–0,23)
> com `finish_reason=content_filter` — filtro de conteúdo/recitação, reproduzido 3/3
> com temperatura 0. O texto parcial era avaliado como se fosse a revisão. Agora
> respostas bloqueadas viram erro (`BlockedResponseError`), sem retry. Outros casos
> curtos dos resultados antigos (razão ~0,5, ex.: `ze-zilda-paulo-da-portela`) podem
> ter a mesma causa ou ser resumo do modelo; não verificado. Na rodada oficial, a taxa de
> bloqueio por provedor deve ser reportada à parte, pois bloqueios saem da análise
> pareada como erros.

### Fase 2 — Métodos sem conferência

**E5. Transcrição de consenso** — ✅ implementado (falta medir em dados reais, no E3)
Entre as `n` transcrições, escolher a mais parecida com as demais (medoide). Não
usa a letra de referência nem API; serve de método e de rascunho para o E7.

**E6. Modelo multimodal transcrevendo direto** *(grupo de controle)* — ✅ implementado (falta medir; Gemini sem teste ao vivo)
Transcritor baseado em LLM com entrada de áudio (Gemini / gpt-4o-audio). Separa o
efeito "modelo melhor de ouvido" do efeito "conferência" no E7.

### Fase 3 — Conferência com áudio

**E7. Conferência com áudio** — ✅ implementado (falta piloto do prompt e medição)
Etapa nova que recebe áudio + rascunho (+ metadados) e devolve uma lista de
alterações auditáveis, aplicadas pelo pipeline. Variantes: rascunho de uma rodada
vs. consenso; com vs. sem metadados (efeito de memorização); áudio original, voz
isolada ou nenhum (controle só texto).

Desenho (revisado antes da implementação):
- o rascunho é dividido por código em **segmentos numerados** (os rascunhos vêm em
  parágrafo único, e o refrão se repete);
- operações `replace`, `delete` e `insert` (trechos pulados e inventados também são
  corrigíveis); `old` precisa ser único no segmento;
- resposta mal formada é **erro**, nunca "nenhuma alteração";
- **precisão por alteração** (útil/neutra/prejudicial) e taxa de falhas por variante;
- a comparação com o E6 é sempre com **o mesmo modelo**.

Próximos passos: piloto em 3 músicas dev para ajustar o prompt (no teste ao vivo, o
`gpt-audio` propôs alteração só de pontuação e nenhum `delete` num rascunho longo
demais); depois, 2 rodadas por música no dev. A referência deve registrar as
repetições cantadas (no baseline antigo, 12% das palavras inseridas eram trechos
que existem na letra), senão restaurar um refrão cantado é penalizado — regra a
fixar no procedimento de letras do E0.

> **Ponto de decisão**: sem ganho acima do ruído, a hipótese está respondida.

**E8. Conferência por trecho**
Áudio segmentado (timestamps do `whisper-1`) e conferido trecho a trecho, para
reduzir erros de atenção em áudio longo.

**E9. Conferência dirigida por discordância**
Só os trechos em que as `n` transcrições discordam vão para conferência.

## Dependências

| # | Entregável | Depende de | Custo de API |
|---|---|---|---|
| E0 | Protocolo | — | nenhum |
| E1 | Repetições + cache + split | — | baixo |
| E2 | Relatório estatístico | E1 | nenhum |
| E3 | Remedir linha de base | E1, E2 | baixo |
| E4 | Tipos de erro | E1 | nenhum |
| E5 | Consenso | E1 | nenhum |
| E6 | Multimodal direto | E1 | médio |
| E7 | Conferência com áudio | E5, E6 | médio/alto |
| E8 | Conferência por trecho | E7 | alto |
| E9 | Conferência dirigida | E5, E8 | médio |

As execuções oficiais (E3 em diante e a rodada final no conjunto de teste) só
acontecem com o catálogo final e o protocolo (E0) definidos.
