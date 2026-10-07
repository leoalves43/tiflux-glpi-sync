# Handoff

DONE (2026-10-07), local container rebuilt, 324 tests green (3.14 + 3.13):
- Specs 003-005: open+Solucionado GLPI tickets scanned every run (loop 120 s);
  failed Tiflux reopen keeps GLPI open and retries; no-behavior refactor.
- Spec 006: reopened Tiflux ticket gets its previous responsible back.
- Spec 007: Tiflux calls honor RateLimit headers and retry 429.

NEXT:
0. PUSH PENDING: `git push origin main` got GitHub 500 x3 (2026-10-07 13:57).
1. Next GLPI refusal: Tiflux reopens + keeps técnico ("atribuído de novo" = it didn't).
2. "⏳ Limite" lines are normal (a run uses ~120+ req/min); repeated 429
   failures are not. Restart the container between runs, not during one.
3. VPS deploy PAUSED by user (2026-10-07) — don't bring it up until asked.
4. Refactor 005 in prod: Tiflux->GLPI followup write OK (14:41); ticket create
   + cascade write still unconfirmed.

RISKS:
- 120 s loop ≈ 2.5x GLPI requests (`INTERVALO_SEGUNDOS=300` reverts); VPS resume = GLPI 302 + duplicates.

CONTEXT: specs/003-007, decisions/LOG.md 2026-10-07.
