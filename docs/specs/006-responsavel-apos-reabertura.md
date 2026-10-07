# 006 — Reabertura do Tiflux mantém o técnico responsável

## Intent
Quando a integração reabre um ticket no Tiflux (recusa da solução no GLPI),
o ticket precisa voltar para o técnico que era o responsável antes de
reabrir. Hoje isso acontece só porque o Tiflux preserva o responsável
(observado em 21 tickets reabertos até 07/10), e não porque a integração
garante isso.

## User outcome
Depois da reabertura feita pela integração, o ticket no Tiflux tem o mesmo
responsável que tinha quando estava fechado. Se não tiver, a integração
atribui esse técnico de novo e registra o que aconteceu no log.

## Constraints
- Sem mudança de schema.
- Só vale para reaberturas feitas pela integração; reabertura manual no
  Tiflux segue a escolha de quem reabriu.
- Uma falha ao restaurar o responsável não desfaz a reabertura nem impede a
  sincronização dos followups.

## Acceptance criteria
1. Reaberto com o mesmo responsável de antes -> nenhuma atribuição é feita.
2. Reaberto sem responsável ou com outro responsável -> o responsável de
   antes é atribuído de novo, e isso é logado com o chamado, o ticket e o técnico.
3. Ticket fechado sem responsável antes de reabrir -> nenhuma atribuição.
4. Se a consulta ao ticket depois de reabrir falhar, o responsável de antes é
   atribuído de novo mesmo assim (atribuir é idempotente; não há outra
   chance, porque a próxima execução não reabre de novo).
5. Se a atribuição falhar, isso é logado com o chamado, o ticket, o técnico e
   o erro da API, e a execução segue (followups publicados normalmente).
6. Reabertura que falhou -> nenhuma tentativa de atribuição.

## Out of scope
Reaberturas manuais no Tiflux; responsável no GLPI; corrigir tickets
reabertos no passado.
