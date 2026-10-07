# Handoff

DONE (2026-10-07), local container rebuilt, 324 tests green (3.14 + 3.13):
- Specs 003-007 shipped (see decisions/LOG.md 2026-10-07).
- Rate-limit study: a run scans 98 tickets (27 aberto + 21 solucionado + 50 fechado),
  ~1 GET /tickets/{n} each + /answers for the 48 open ≈ 145 Tiflux calls -> every run
  hits the reserve even with 0 followups. Tiflux had only 12 tickets updated in 8 h, 30 open.

NEXT:
1. Spec 008 APPROVED; plan 008 written, AWAITING APPROVAL. Proposal (change-driven Tiflux side: 1 `filter_by=open`
   listing + existing `update_start_datetime` listing; `/answers` only for updated tickets;
   per-ticket GET only on transitions; small safety sweep).
2. VPS deploy PAUSED by user — don't bring it up until asked.
3. Refactor 005 in prod: ticket create confirmed (#34900, 16:23); cascade write unconfirmed.

RISKS:
- 008: failed listing returns [] today — must not be read as "all closed".
- `updated_at` bump verified for web + e-mail answers (test GLPI #34900 / Tiflux #364678,
  still open — close after spec 008 tests); attachment answers not tested.

CONTEXT: specs/007, decisions/LOG.md 2026-10-07, sync/sincronizacao_followups.py.
