# 008 — Consultar no Tiflux só o que mudou

## Intent
Toda execução consulta cada um dos ~98 chamados do rodízio no Tiflux (≈145
requisições, limite de 120/min), mesmo quando nada mudou: em 07/10 as
execuções de 15:22 a 15:30 sincronizaram 0 followups e ainda assim bateram
no limite. Em 8 h só 12 tickets mudaram no Tiflux. A sincronização deve
gastar requisições proporcionais às mudanças, não ao total de chamados.

## User outcome
O comportamento visível não muda (followups, encerramento/reabertura em
cascata, recusa no GLPI, responsável após reabertura), mas uma execução sem
mudanças faz poucas requisições ao Tiflux e não encosta mais no limite.

## Constraints
- Uma listagem do Tiflux só indica candidatos. Nenhuma escrita (encerrar,
  reabrir, publicar, atribuir) é decidida pela listagem: antes de agir, o
  ticket é lido individualmente, como hoje.
- Listagem que falha não é "lista vazia": nessa execução nada é concluído a
  partir dela, e a mudança não se perde — a próxima listagem bem-sucedida
  cobre desde a última que deu certo (mesmo se o container ficou parado
  mais de uma hora).
- Uma varredura completa, lenta e em rodízio, continua existindo como rede
  de segurança para o que a listagem eventualmente não apontar.
- Sem mudança de schema; nada muda no lado GLPI (sem limite de requisições).
- Mantém a proteção da spec 007.

## Acceptance criteria
1. Execução sem nenhuma mudança em nenhum lado: no máximo 5 requisições ao
   Tiflux (medido pelo log de requisições no teste).
2. Resposta nova no Tiflux chega ao GLPI na execução seguinte a ela.
3. Ticket encerrado/reaberto no Tiflux é espelhado no GLPI na execução
   seguinte, após leitura individual que confirma o status.
4. Recusa no GLPI (Solucionado -> aberto) com Tiflux fechado continua
   reabrindo o Tiflux na execução seguinte (spec 004/006).
5. Listagem do Tiflux com erro (HTTP ≠ 200 ou falha de rede): nenhum
   encerramento, reabertura ou publicação Tiflux->GLPI decorre dela; um
   aviso é logado; na execução seguinte bem-sucedida a mudança é aplicada.
6. Ticket fora da lista de abertos do Tiflux nunca é tratado como fechado
   sem a leitura individual confirmar `is_closed`.
7. Todo chamado sincronizado é conferido por completo pela varredura de
   segurança pelo menos uma vez por dia.
8. Followups GLPI->Tiflux seguem como hoje.

## Out of scope
Webhooks do Tiflux (não documentados; sem endereço público com a VPS
pausada); reduzir requisições ao GLPI; mudar o intervalo do loop.
