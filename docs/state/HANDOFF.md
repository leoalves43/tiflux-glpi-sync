# Handoff

DONE (2026-10-07), local container rebuilt, 297 tests green (3.14 + 3.13):
- Spec/plan 003: all GLPI-open tickets scanned every run + 50 closed; loop 120 s.
- Spec/plan 004: failed Tiflux reopen after GLPI refusal keeps GLPI open,
  logs, retries every run; GLPI Solucionado scanned every run (#34759).

NEXT:
1. Spec/plan 005 refactor done: followups split into 3 modules, typed, <=20-line fns.
2. Tiflux permission "Revisar e avaliar tickets fechados" requested for the
   API user. #34759 closed by hand in GLPI; followup 77817 marked handled.
3. VPS `git pull`; after GLPI allows the VPS IP: `docker compose stop`
   locally, `up -d --build` on VPS.

RISKS:
- 120 s ≈ 2.5x GLPI requests; watch timeouts. `INTERVALO_SEGUNDOS=300` reverts.
- Hundreds of GLPI-open tickets would lengthen each run (no cap by design).
- VPS blocked (GLPI 302s its IP). Two schedulers on one DB = duplicates.

CONTEXT: specs/003, specs/004, decisions/LOG.md 2026-10-07.
