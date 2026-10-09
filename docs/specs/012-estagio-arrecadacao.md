# 012 — ARRECADAÇÃO já entra no estágio "Em Atendimento - Residentes"

## Intent
Ticket criado pela integração (GLPI -> Tiflux) na mesa ARRECADAÇÃO já vai
para o técnico Leonardo Silva; deve ir também para o estágio
"Em Atendimento - Residentes", sem passo manual.

## User outcome
Chamado do GLPI com categoria da ARRECADAÇÃO aparece no Tiflux atribuído ao
Leonardo e no estágio "Em Atendimento - Residentes" (233286).

## Constraints
- Só a mesa ARRECADAÇÃO (37964); as demais seguem no estágio inicial.
- Mover de estágio depois de criar e atribuir o técnico; falha só avisa (o
  ticket já existe; reprocessar duplicaria).
- Fora do escopo: reabertura em cascata (cai no primeiro estágio do Tiflux),
  tickets abertos direto no Tiflux.

## Acceptance criteria
1. Chamado GLPI -> mesa 37964: ticket com técnico 117180 e stage 233286.
2. Outra mesa: nenhuma troca de estágio.
3. Falha na troca: aviso no log, chamado 'sucesso'.
