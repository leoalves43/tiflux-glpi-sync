# Plan 004 — recusa no GLPI sem reabrir o Tiflux (spec: docs/specs/004-recusa-glpi-sem-reabrir-tiflux.md)

## Architecture delta
`_sincronizar_chamado_aberto` (sync/sincronizacao_followups.py): reabertura
falhou -> marca varrido e retorna (sem followups, sem `encerrar_em_cascata`).
`_reabrir_tiflux_apos_recusa_glpi` grava sempre a linha `glpi_para_tiflux`
da tentativa e, só no sucesso, a linha de cascata. Novo passo ao fim da
varredura de chamado aberto com Tiflux aberto: equaliza cascata
`encerramento` -> `reabertura_tiflux` (critério 7).

## Files touched
- `sync/sincronizacao_followups.py`, `tests/test_sincronizacao_followups.py`.
- `docs/data/audit_tables.toon` (tipo `reabertura_tiflux` em `glpi_para_tiflux`),
  `docs/decisions/LOG.md`, `docs/state/HANDOFF.md`.

## Risks
- Retentativa a cada execução gera um 403 + aviso por ciclo até a reabertura
  manual. Intencional (visível); some quando o Tiflux reabre.
- Linha nova com `id_origem` negativo em `glpi_para_tiflux`: leitores dessa
  direção filtram `status='sucesso'` + id positivo do GLPI, ou usam
  `id_destino` (NULL aqui) — conferido em db_followups.py.
- Critério 7 adiciona um SELECT por chamado aberto com Tiflux aberto.

## Tasks
- [x] 1. Falha na reabertura não encerra o GLPI, linha própria, log (crit. 1–6)
      + testes. Done: `python -m unittest` verde.
- [x] 2. Equalização após reabertura manual (crit. 7) + teste. Done: verde.
- [ ] 3. Rebuild do container; docs (toon, LOG, HANDOFF). Done: log sem erro.
