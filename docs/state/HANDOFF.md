# Handoff

DONE (2026-10-09), specs 009 + 010 on main and deployed, 451 tests green:
- 009 live (cutoff 2026-10-09T17:25:00Z in .env): Tiflux #364984 -> GLPI #35009; answers both ways,
  close, reopen ok. GLPI #35007 = first test, Solucionado and unlinked by hand.
- Backfill applied: GLPI 34982, 34986, 34990 Novo -> Pendente; 0 Novo left. Idle run: 5 Tiflux req.

- Spec 010 deployed 16:12: INFRAESTRUTURA 38853 <-> cat 348 both ways; only client 762707 to GLPI;
  inactive requester -> 4988; #364799 -> GLPI #35018, #364496 -> #35019 (answers in, no echo).

NEXT:
1. Watch first real Tiflux-opened tickets (log line "🆕"). Close test GLPI #35009 / Tiflux #364984.
2. Untested live: ticket opened+closed between runs (AC 9).

RISKS:
- Files > ~2 MB fail on GLPI's PHP upload limit (logged, ticket still created). Infra fix.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
