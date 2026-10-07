# Handoff

DONE (2026-10-07), local container rebuilt, 277 tests green:
- Spec/plan 003: all GLPI-open tickets scanned every run + 50 closed; loop 120 s.
- Spec/plan 004: failed Tiflux reopen after GLPI refusal keeps GLPI open,
  logs a warning and retries every run (was re-closing GLPI, #34759).

NEXT:
1. Tiflux #364160 needs reopening: API + user both get 403 on fully closed;
   the integration then reopens GLPI #34759 and posts followup 77817.
2. Tiflux admin: grant "Revisar e avaliar tickets fechados" to API user (or relink #34759).
3. VPS `git pull`; after GLPI allows the VPS IP: `docker compose stop`
   locally, `up -d --build` on VPS.

RISKS:
- 120 s ≈ 2.5x GLPI requests; watch timeouts. `INTERVALO_SEGUNDOS=300` reverts.
- Hundreds of GLPI-open tickets would lengthen each run (no cap by design).
- VPS blocked (GLPI 302s its IP). Two schedulers on one DB = duplicates.

CONTEXT: specs/003, specs/004, decisions/LOG.md 2026-10-07.
