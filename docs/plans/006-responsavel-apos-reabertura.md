# Plan 006 — responsável após reabertura (spec: docs/specs/006-responsavel-apos-reabertura.md)

## Architecture delta
`_sincronizar_chamado_aberto_no_glpi` (sync/sincronizacao_followups.py)
guarda `responsible.id` do ticket fechado antes de reabrir; depois do GET
pós-reabertura chama a nova função `restaurar_responsavel_apos_reabertura()`
(sync/cascata_status.py). Ela compara os responsáveis e, quando diferem ou
o GET falhou, chama `TifluxClient.atribuir_tecnico` (já existe). Sem
endpoint novo e sem escrita no banco.

## Files touched
- `sync/cascata_status.py`, `sync/sincronizacao_followups.py`.
- `tests/fake_clients.py` (fake guarda as atribuições e pode simular a
  perda do responsável na reabertura), `tests/test_cascata_status.py`.
- `docs/decisions/LOG.md`, `docs/state/HANDOFF.md`, `docs/INDEX.md`.

## Risks
- Nada irreversível. No pior caso, atribui de novo a mesma pessoa quando o
  GET falha (critério 4); o Tiflux pode registrar ou notificar essa troca.
- `atribuir_tecnico` cai para `PUT /tickets/{n}` se o `change_responsible`
  falhar; esse caminho ainda não foi testado num ticket reaberto, e uma falha
  ali só gera log (critério 5).

## Tasks
- [x] 1. `restaurar_responsavel_apos_reabertura` + chamada no fluxo de recusa
      + testes dos critérios 1–6. Done: `python -m unittest` verde.
- [ ] 2. Rebuild do container; LOG, HANDOFF. Done: log do container sem erro.
