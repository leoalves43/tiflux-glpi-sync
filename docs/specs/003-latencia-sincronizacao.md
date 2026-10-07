# 003 — Reduzir o atraso de sincronização de chamados e followups

## Intent
Um followup novo levava até ~20 min para atravessar (Tiflux #364569: resposta
às 09:34, no GLPI às 09:50). Causa: o rodízio de 50 chamados por execução
divide as vagas entre abertos e fechados no GLPI (2026-10-07: 28 abertos, 176
fechados), então um chamado aberto só é revisitado a cada ~4 execuções. Somado
ao intervalo de 5 min entre execuções, chamados novos também esperam até 5 min.

## User outcome
Chamado novo no GLPI e followup novo em qualquer sentido aparecem no outro
sistema em até ~2,5 min (um intervalo + uma execução), enquanto houver até 50
chamados abertos sincronizados.

## Constraints
- Nenhuma chamada nova de API por chamado; o volume por execução não cresce.
- Chamados fechados no GLPI continuam sendo revisitados (a detecção de solução
  recusada no GLPI -> reabrir o Tiflux depende disso), mesmo que mais devagar.
- Execuções continuam sem sobreposição (o loop dorme só depois de terminar).
- O intervalo continua configurável sem rebuild (variável de ambiente).

## Acceptance criteria
1. Com até 50 chamados abertos sincronizados, todos entram em toda execução,
   antes de qualquer chamado fechado.
2. Chamado sincronizado e nunca varrido entra antes dos fechados.
3. Entre os abertos, a ordem continua sendo o de varredura mais antiga primeiro
   (rodízio justo quando houver mais de 50 abertos).
4. As vagas que sobram vão para os fechados, do de varredura mais antiga para o
   mais recente; um chamado fechado acaba sempre sendo revisitado.
5. Só chamados `status='sucesso'` entram no rodízio (regra atual mantida).
6. O intervalo padrão entre execuções no container é 120 s.
7. Os testes existentes continuam passando; a nova ordem tem teste próprio.

## Out of scope
Usar o `updated_at` do Tiflux como gatilho de followup; aumentar o tamanho do
lote; mudar a sondagem de chamados do GLPI; o deploy na VPS (segue o HANDOFF).
