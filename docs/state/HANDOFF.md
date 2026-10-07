# Handoff

DONE (2026-10-07), local container rebuilt, 297 tests green (3.14 + 3.13):
- Spec/plan 003: all GLPI-open tickets scanned every run + 50 closed; loop 120 s.
- Spec/plan 004: failed Tiflux reopen after GLPI refusal keeps GLPI open,
  logs, retries every run; GLPI Solucionado scanned every run (#34759).
- Spec/plan 005: no-behavior refactor (followups in 3 modules, typed, short fns).

NEXT:
1. Tiflux permission "Revisar e avaliar tickets fechados" requested for the
   API user. #34759 closed by hand in GLPI; followup 77817 marked handled.
2. `git push` (003-005 are local only), then VPS `git pull`; after GLPI allows the VPS IP: `docker compose stop`
   locally, `up -d --build` on VPS.

RISKS:
- 120 s ≈ 2.5x GLPI requests; watch timeouts. `INTERVALO_SEGUNDOS=300` reverts.
- Hundreds of GLPI-open tickets would lengthen each run (no cap by design).
- VPS blocked (GLPI 302s its IP). Two schedulers on one DB = duplicates.

CONTEXT: specs/003-005, decisions/LOG.md 2026-10-07.
