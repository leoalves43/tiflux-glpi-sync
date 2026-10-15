# Plano 013 — Validação do GLPI no Tiflux

Spec: `docs/specs/013-validacao-glpi-no-tiflux.md`.

## Fatos lidos em 2026-10-15 (GET, sem escrita)
- `GET /Ticket/{id}/TicketValidation` -> lista com `id`, `users_id` (quem
  pediu), `users_id_validate` (validador), `status` (2 aguardando, 3 aprovada,
  4 recusada), `submission_date`, `validation_date`, `comment_submission`,
  `comment_validation` (HTML entity-encoded, como os followups).
- #35092: validação 1474, pedida por 1883 a 4867, status 2.
  #35140: validação 1480, pedida por 4988 a 4867, status 2.
- `Ticket.global_validation`: 1 = sem validação (#35092 está em 2).

## Arquitetura
- Novo módulo `sync/validacoes_glpi.py`: lê as validações, decide os eventos
  pendentes e publica via `tiflux.publicar_resposta_cliente` (autor = nome
  GLPI de quem pediu / do validador). Devolve (sucessos, erros) pro placar.
- Chamado em `sync/sincronizacao_followups.py` nos dois caminhos de chamado
  aberto no GLPI, logo após os followups GLPI -> Tiflux. Sem GET quando
  `global_validation == 1`.
- Auditoria (sem DDL): `direcao` = `validacao_pedido` | `validacao_resposta`,
  `tipo` = `publica`, `id_origem` = id da validação. A chave única
  (direcao, id_origem) garante um evento por validação; só `sucesso` conta
  como publicado, `erro` é retentado.
- Corte: `.env` `VALIDACAO_GLPI_DESDE_ID=1474`; ausente/0 = recurso desligado.
  Validação com id menor é ignorada.

## Arquivos
`sync/validacoes_glpi.py` (novo), `sync/glpi_client.py`
(`obter_validacoes`), `sync/db_followups.py` (ids publicados por direcao),
`sync/config.py`, `sync/sincronizacao_followups.py`, `exemplo.env`,
`tests/fake_clients.py`, testes novos, `docs/data/audit_tables.toon`,
`docs/ARCHITECTURE.md`, README, LOG.

## Riscos
- +1 GET no GLPI por chamado aberto com validação, a cada ciclo (5 min).
- Validação pra grupo (GLPI 11, `itemtype_target`) não existe nesta versão;
  se aparecer, o nome do validador sai "Desconhecido".
- Nada irreversível além das respostas publicadas no Tiflux.

## Tarefas
- [x] 0. (Pedido 2026-10-15, plano aprovado) Ciclo a cada 5 min alinhado ao
  relógio (12:00, 12:05...): `docker/loop_sincronizacao.sh`,
  `docker-compose.yml` (`INTERVALO_SEGUNDOS=300`, divisor de 3600), README,
  ARCHITECTURE, spec 003 (crit. 6). Done: logs com início em minuto múltiplo
  de 5; valor inválido sai com erro citando o valor.
- [x] 1. `GlpiClient.obter_validacoes` + config do corte. Done: testes
  (lista, falha HTTP -> vazio + log, config inválida cita o valor).
- [x] 2. `db_followups`: ids publicados com sucesso por direcao. Done: teste.
- [x] 3. `validacoes_glpi.py`: eventos pendentes (corte, pedido antes da
  resposta, já publicados), texto 🔐/✅/❌, publicação + auditoria. Done:
  testes AC 1-6, 8.
- [x] 4. Ligar em `sincronizacao_followups` (dois caminhos, pula
  `global_validation == 1`). Done: testes AC 7 + placar.
- [x] 5. Docs: toon, ARCHITECTURE, README, `exemplo.env`, LOG. Done: lint +
  suíte verde.
- [ ] 6. Deploy com `VALIDACAO_GLPI_DESDE_ID=1474`. Done: AC 9 nos logs e no
  Tiflux (#365227, #365366).
