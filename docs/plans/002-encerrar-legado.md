# Plan 002 — encerrar legado (spec: docs/specs/002-encerrar-legado.md)

## Architecture delta
New CLI `python -m sync.encerrar_legado --id-glpi N --numero-tiflux M`.
Reuses the existing cascade close (`_encerrar_em_cascata` in
`sync/sincronizacao_followups.py`: technician, solution from last technician
answer, status Solucionado, cascade audit row). Writes nothing to
`api_glpi_tiflux`, so `main.py` loop, rotation and `mudancas_status_tiflux`
(all join on `api_glpi_tiflux.status='sucesso'`) never see the ticket.

## Files touched
- `sync/sincronizacao_followups.py` — rename `_encerrar_em_cascata` ->
  `encerrar_em_cascata` (public; now used by two modules).
- `sync/encerrar_legado.py` — new CLI.
- `tests/test_encerrar_legado.py` — new.
- `README.md`, `docs/ARCHITECTURE.md` (module table), `docs/decisions/LOG.md`,
  `docs/state/HANDOFF.md`, `docs/INDEX.md`.

## Risks
- Irreversible on GLPI side (solution + status). Mitigated: refuses unless
  Tiflux is closed and GLPI open; operator supplies the pair explicitly.
- Wrong pair typed -> wrong GLPI ticket solved. Print both titles in the
  result so the operator can check; test with one ticket first.
- Cascade audit row (`id_origem=-id_glpi`) is written in the followups table;
  harmless — every reader joins on `api_glpi_tiflux`.

## Tasks
- [x] 1. Make `encerrar_em_cascata` public. Done: tests green.
- [x] 2. `sync/encerrar_legado.py` + tests for criteria 1–6 (FakeGlpiClient,
      FakeTifluxClient, FakeConnection). Done: tests green.
- [x] 3. Docs (README usage, ARCHITECTURE row, LOG line, INDEX, HANDOFF).
      Done: INDEX lists spec/plan 002.
