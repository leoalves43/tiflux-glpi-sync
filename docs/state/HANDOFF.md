# Handoff

DONE (2026-10-07), local container rebuilt, 324 tests green (3.14 + 3.13):
- Specs 003-007 shipped (see decisions/LOG.md 2026-10-07).
- Rate-limit study: a run scans 98 tickets (27 aberto + 21 solucionado + 50 fechado),
  ~1 GET /tickets/{n} each + /answers for the 48 open ≈ 145 Tiflux calls -> every run
  hits the reserve even with 0 followups. Tiflux had only 12 tickets updated in 8 h, 30 open.

NEXT:
1. Spec 008 written, AWAITING USER APPROVAL (then plan). Proposal (change-driven Tiflux side: 1 `filter_by=open`
   listing + existing `update_start_datetime` listing; `/answers` only for updated tickets;
   per-ticket GET only on transitions; small safety sweep). Then write spec 008.
2. VPS deploy PAUSED by user — don't bring it up until asked.
3. Refactor 005 in prod: ticket create + cascade write still unconfirmed.

RISKS:
- 008: failed listing returns [] today — must not be read as "all closed".
- `updated_at` bump on answer verified on 4 tickets only (not e-mail/portal answers).

CONTEXT: specs/007, decisions/LOG.md 2026-10-07, sync/sincronizacao_followups.py.
