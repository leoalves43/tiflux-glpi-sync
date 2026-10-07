# 004 — Recusa no GLPI não pode ser desfeita quando o Tiflux não reabre

## Intent
GLPI #34759 (07/10): requerente recusou a solução; a integração tentou reabrir
o Tiflux #364160, recebeu 403 (token sem permissão para reabrir ticket
totalmente fechado — LOG 2026-09-16) e, na mesma execução, encerrou o GLPI de
novo em cascata. A recusa sumiu e o erro foi sobrescrito na auditoria.

## User outcome
Recusa no GLPI com Tiflux impossível de reabrir: o GLPI continua aberto, o
erro fica visível (log + auditoria) e a integração retenta a cada execução até
o Tiflux ser reaberto (por ela ou à mão). Reaberto à mão, o fluxo segue normal.

## Constraints
- Sem mudança de schema; sem chamada nova de API.
- Recusa com reabertura bem-sucedida continua como hoje.

## Acceptance criteria
1. Reabertura do Tiflux falha -> GLPI não é encerrado de novo na execução.
2. A falha grava linha própria (`glpi_para_tiflux`, `reabertura_tiflux`,
   `id_origem=-id_glpi`, `erro`, mensagem da API) e não altera a linha de
   cascata (`tiflux_para_glpi`), que segue `encerramento`/`sucesso`.
3. A falha é logada com chamado, ticket e erro, pedindo reabertura manual.
4. Na falha, nenhum followup GLPI->Tiflux é tentado (seria 422).
5. Execução seguinte retenta a reabertura enquanto GLPI aberto + Tiflux fechado.
6. Reabertura bem-sucedida grava `sucesso` nas duas linhas.
7. GLPI aberto + Tiflux aberto + última cascata `encerramento` (Tiflux
   reaberto à mão) -> cascata registra `reabertura_tiflux`/`sucesso`, para que
   um fechamento posterior do técnico encerre o GLPI em vez de reabrir o Tiflux.

8. Chamado Solucionado no GLPI (status 5, ainda recusável) é conferido em
   toda execução, junto com os abertos; só Fechado (6) fica no lote limitado.
   (07/10: 20 solucionados, 156 fechados.)

## Out of scope
Obter a permissão de reabertura no Tiflux; recuperar recusas antigas já
desfeitas (#34759 é corrigido à mão).
