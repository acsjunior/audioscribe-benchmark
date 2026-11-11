# Estado do projeto e próximos passos

**Atualizado em:** 11/11/2026. Ponto de partida de cada nova sessão de trabalho:
diz onde o projeto está, o que já foi decidido, o que falta decidir e o que fazer a
seguir. Ao fechar uma sessão, atualizar este arquivo.

| Documento | Para quê |
|---|---|
| [PROTOCOLO.md](PROTOCOLO.md) | Metodologia do estudo: hipóteses, dados, letra de referência, análise. Fonte das decisões; mudanças vão no registro de alterações (seção 13) |
| [ROADMAP.md](ROADMAP.md) | Entregáveis E0–E9 e o que já foi construído |
| [MANUAL.md](MANUAL.md) | Como usar a ferramenta |
| [CLAUDE.md](CLAUDE.md) | Arquitetura e decisões de código |

---

## 1. Onde estamos

- **Ferramenta pronta** (E1, E2, E4 concluídos; E5, E6, E7 implementados e ainda não
  medidos em dados reais). 299 testes passando.
- **Protocolo v0.13** em rascunho avançado, com poucos itens pendentes (seção 3).
- **Amostra definida**: lista de 250 composições em ordem sorteada
  ([ordem_amostragem.csv](data/candidatas/ordem_amostragem.csv), semente 20261110).
  Nenhuma letra conferida ainda.
- **Próximo passo**: conferir as letras na ordem da lista (seção 4, passo 1).

## 2. Decisões tomadas (resumo; detalhes no PROTOCOLO)

**Pergunta e hipóteses** (PROTOCOLO 1–2): a conferência com áudio por um modelo
multimodal melhora o rascunho? H1 conferência vs. rascunho; H2 vs. a mesma
conferência sem áudio; H3 vs. o mesmo modelo transcrevendo direto. H2 e H3 só se H1
for confirmada.

**Dados** (PROTOCOLO 3):
- Gênero exatamente "Samba", gravações de 1928 a 1955 (era elétrica; as mecânicas
  ficam fora), domínio público (gravação e todos os autores falecidos até 1955),
  áudio na Discografia Brasileira (IMS), letra cantada.
- Catálogo extraído em 10/11/2026 com o `~/Developer/db-scraper`: 546 candidatas →
  469 "Samba" → 312 de 1928 em diante → 274 cantadas (38 instrumentais excluídas na
  [revisão](data/candidatas/revisao_populacao.csv)) → 250 composições.
- Amostra **proporcional** ao acervo, estratificada e balanceada por década, uma
  gravação sorteada por composição, sem cotas por intérprete ou autor. Concentração
  (Francisco Alves ~22% como intérprete; Noel Rosa e Sinhô ~1/3 como autores) tratada
  por análise de sensibilidade com bootstrap por intérprete.
- **Dev = as 40 primeiras músicas incluídas** na ordem da lista; **teste = as
  incluídas seguintes**, meta de 120 (mínimo ~100, pelo poder para δ = 0,01). Uma
  excluída é sempre reposta pela próxima posição, nunca por escolha.
- O dev funciona como base de validação: nele se escolhem prompt, modelo e variante,
  pela regra "maior ganho de Hodges–Lehmann". O teste roda uma única vez, com tudo
  congelado.
- As 28 músicas da fase exploratória ficam fora do estudo (27 têm autor falecido
  depois de 1955); só são citadas como estudo exploratório.

**Letra de referência** (PROTOCOLO 4): o que foi cantado naquela gravação, conferido
ouvindo a gravação inteira duas vezes, **antes** de ver qualquer transcrição
automática; repetições registradas; contrações como cantadas; música com trechos
inaudíveis ou duvidosos é excluída em vez de entrar com palpite. Segunda pessoa
confere 20% das músicas de forma independente.

**Normalização** (PROTOCOLO 6.2): minúsculas, sem pontuação, acentos mantidos,
interjeições removidas e equivalências de grafia ("para o" = "pro"), em
[normalization.yaml](src/benchmark/metrics/normalization.yaml).

**Análise** (PROTOCOLO 7): unidade = música; Wilcoxon de postos sinalizados com zeros
de Pratt + Hodges–Lehmann com IC por bootstrap; WER do corpus como proteção contra
dano; sequência fixa H1 → {H2, H3 com Holm}; H1 confirmada = teste + IC do HL > 0 +
sem dano líquido no WER do corpus. Implementado em `benchmark confirm`.

**Memorização** (PROTOCOLO 10): áudio enviado com nome neutro e sem tags; prompts sem
metadados por padrão; a variante com metadados mede o efeito.

**Registro de custo**: transcrição e conferência guardam tokens e tempo de cada
chamada (`usage` no cache e no `results.json`). Não muda a análise; serve para
comparar custo entre métodos e para pesquisas futuras sobre orçamento de chamadas.

## 3. Pendências de decisão

| Item | Proposta atual | Quando decidir |
|---|---|---|
| Mínimo de palavras na letra (PROTOCOLO 3.2) | 50 palavras após a normalização | Antes de conferir as letras |
| Ganho mínimo com relevância prática (PROTOCOLO 7.3) | 10% de redução relativa do WER do corpus do baseline, fixado depois do E3 e relatado também em valor absoluto | Depois do E3, antes do congelamento |
| Modelo do baseline (PROTOCOLO 5) | `whisper-1` ou `gpt-4o-transcribe` | Pelo E3 |
| Rodadas por música (PROTOCOLO 7.1) | n = 5 | Depois do E3 |
| Rodadas conferidas (`max_runs`, PROTOCOLO 7.1) | 2 | Depois do piloto do E7, conforme o custo |

## 4. Próximos passos, em ordem

1. **Conferir as letras** em [ordem_amostragem.csv](data/candidatas/ordem_amostragem.csv),
   a partir da posição 1, pelo procedimento do PROTOCOLO 4. Para cada música, marcar
   `status` (`incluida` ou `excluida`) e, se excluída, `motivo_exclusao`. Depois:
   `uv run python scripts/assign_splits.py data/candidatas/ordem_amostragem.csv`
   (as 40 primeiras incluídas viram `dev`; para na primeira posição não conferida).
   - Atenção à posição 8, *Um Beijo Só* (Luciano Perrone, 1932): Perrone era
     baterista, a gravação pode ser instrumental.
2. **Levar as músicas conferidas para o catálogo** (`data/catalogo.csv`), com letra,
   áudio, `Split` e as colunas da PROTOCOLO 3.4. **Ainda não definido como**: o
   pipeline baixa áudio do Google Drive (colunas `Arquivo` e `URL`), e a lista traz
   `audio_url` do site do IMS. Decidir entre baixar os MP3 do IMS para
   `data/inputs/` (o db-scraper tem rotina de download) ou subir para o Drive.
3. **Sortear os 20% da segunda anotação** (semente registrada) e passar para a
   segunda pessoa, que não pode ver a primeira versão nem transcrições automáticas.
4. **E3 no dev**: `whisper-1` e `gpt-4o-transcribe`, n = 5. Define o baseline, o ruído
   entre rodadas e o ganho mínimo relevante.
5. **Piloto do E7** em 3 músicas do dev: ajustar o prompt de conferência (no teste ao
   vivo, o `gpt-audio` propôs alteração só de pontuação e nenhum `delete`).
6. **Refazer a simulação de poder** (`scripts/power.py`) com os ganhos do E7 no dev.
7. **Bateria no dev**: todos os métodos e variantes; escolha pela regra do protocolo.
8. **Congelamento**: protocolo v1.0, configurações, prompts, versões de modelo, commit
   e YAML das hipóteses (`benchmark confirm`).
9. **Execução única no teste** e relatório. E8/E9 só se o E7 mostrar ganho.

## 5. Colaboradores

Duas pessoas foram convidadas para contribuir. Há um documento de apresentação do
estudo para elas (objetivo, método, como contribuir), no claude.ai, privado até ser
compartilhado: <https://claude.ai/artifact/7wx9ButDMY3LMKA25jpscu>. Frentes propostas:
conferência de letras, segunda anotação independente (20%) e revisão do protocolo.
Divisão de tarefas, prazos e crédito ainda em aberto.

## 6. Avisos e pendências técnicas

- **db-scraper**: a paginação do `~/Developer/db-scraper` para na página 1 (o seletor
  do link "próxima" está obsoleto). O catálogo foi extraído com um laço externo que
  passa `&_p=N` na URL. Correção ainda não feita.
- **Gemini**: os caminhos com Gemini (E6 e E7) só foram testados com dublês; não há
  `GOOGLE_API_KEY` no `.env`.
- **Cache antigo**: transcrições salvas antes do registro de custo não têm `usage`.
- **Prompt padrão do `gpt-4o-transcribe`** cita artistas do período, mas não a música
  transcrita; fica fixo para todas as músicas (PROTOCOLO 5).
- **Dados para pesquisa futura**: manter cache de todas as rodadas, `results.json` de
  todas as avaliações do dev e a auditoria de cada correção do E7. Experimentos novos
  fora do protocolo (ex.: fundir transcrições do teste, outros modelos) só depois da
  execução confirmatória no teste, para não contaminar o estudo.
