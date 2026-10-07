# Handoff

DONE (2026-10-07), local container rebuilt, 304 tests green (3.14 + 3.13):
- Spec/plan 003: all GLPI-open tickets scanned every run + 50 closed; loop 120 s.
- Spec/plan 004: failed Tiflux reopen after GLPI refusal keeps GLPI open,
  logs, retries every run; GLPI Solucionado scanned every run (#34759).
- Spec/plan 005: no-behavior refactor (followups in 3 modules, typed, short fns).
- Spec/plan 006: after reopening Tiflux, previous responsible is re-assigned
  if missing/different (Tiflux seems to keep it; now enforced).

NEXT:
1. Next GLPI refusal: watch the log — Tiflux should reopen by itself and keep
   the técnico (a "atribuído de novo" line means Tiflux dropped it).
2. Confirm refactor write paths in prod (first ticket/followup/cascade after 11:34).
3. VPS deploy PAUSED by user (2026-10-07) — don't bring it up until asked.

RISKS:
- 120 s ≈ 2.5x GLPI requests; watch timeouts. `INTERVALO_SEGUNDOS=300` reverts.
- Hundreds of GLPI-open tickets would lengthen each run (no cap by design).
- If VPS resumes: GLPI 302s its IP; two schedulers on one DB = duplicates.

CONTEXT: specs/003-006, decisions/LOG.md 2026-10-07.
