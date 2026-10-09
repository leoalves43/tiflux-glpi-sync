# 010 — Mesa INFRAESTRUTURA e só o cliente da prefeitura

## Intent
A mesa INFRAESTRUTURA do Tiflux passa a fazer parte da integração, nos dois
sentidos, e a abertura Tiflux -> GLPI (spec 009) só pode trazer tickets do
cliente SP-CARAGUATATUBA-PM.

## User outcome
- Ticket novo na mesa INFRAESTRUTURA vira chamado no GLPI na categoria 348,
  com os demais campos da spec 009.
- Chamado do GLPI na categoria 348 vira ticket na mesa INFRAESTRUTURA.
- Os 2 tickets INFRAESTRUTURA abertos antes do corte (#364799, #364496) são
  importados uma vez, com as respostas públicas, sem eco para o Tiflux.

## Constraints
- INFRAESTRUTURA = mesa 38853; categoria GLPI 348 ("Embras > Infraestrutura").
- GLPI -> Tiflux na mesa 38853: prioridade "Solicitar um Atendimento"
  (123346), sem técnico fixo (padrão das demais mesas exceto ARRECADAÇÃO).
- Ticket de outro cliente nunca vira chamado no GLPI, mesmo se aparecer numa
  listagem ou numa retentativa.
- A data de corte continua valendo no ciclo; só o comando manual pode ignorá-la.

## Acceptance criteria
1. Ticket novo na mesa 38853 -> chamado GLPI categoria 348, entidade STII etc.
2. Chamado GLPI categoria 348 (com grupo observador) -> ticket na mesa 38853,
   prioridade 123346, sem técnico.
3. Ticket de cliente diferente de 762707 não é candidato à abertura.
4. `abrir_ticket_tiflux_no_glpi --ignorar-corte --aplicar` abre ticket anterior
   ao corte; sem a flag, recusa como hoje.
5. #364799 e #364496 existem no GLPI; as 2 respostas do #364496 chegam ao GLPI
   e nada volta ao Tiflux como resposta nova.

## Out of scope
Outras mesas; comunicações internas (continuam não cruzando).
