# Handoff

DONE (2026-10-09), spec 009 merged to main and deployed (container rebuilt 14:42), 443 tests green:
- Live (cutoff ABERTURA_TIFLUX_DESDE=2026-10-09T17:25:00Z in .env): Tiflux #364984 -> GLPI #35009
  (entity 1, loc 1685, cat 272, Pendente, png copied); answers both ways; close -> Solucionado;
  API reopen -> Pendente. GLPI #35007 = first test, Solucionado and unlinked by hand.
- Backfill applied: GLPI 34982, 34986, 34990 Novo -> Pendente; 0 Novo left. Idle run: 5 Tiflux req.

NEXT:
1. Watch first real Tiflux-opened tickets (log line "🆕"). Close test GLPI #35009 / Tiflux #364984.
2. Untested live: ticket opened+closed between runs (AC 9).

RISKS:
- Files > ~2 MB fail on GLPI's PHP upload limit (logged, ticket still created). Infra fix.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
