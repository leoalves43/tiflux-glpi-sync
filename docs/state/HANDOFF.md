# Handoff

DONE (2026-10-09), specs 009-012 on main and deployed, 457 tests green:
- 009 live (cutoff 2026-10-09T17:25:00Z in .env): Tiflux #364984 -> GLPI #35009; answers both ways,
  close, reopen ok. GLPI #35007 = first test, Solucionado and unlinked by hand. Backfill Novo->Pendente done.
- Spec 010 deployed 16:12: INFRAESTRUTURA 38853 <-> cat 348 both ways; only client 762707 to GLPI;
  inactive requester -> 4988; #364799 -> GLPI #35018, #364496 -> #35019 (answers in, no echo).
- Spec 011 deployed 16:48: GLPI -> Tiflux scope = category (no observer group); integration adds
  group 22 next to technician 4988. First run: 22 ignored, 0 created (as checked beforehand).
- Spec 012: ARRECADAÇÃO tickets -> stage 233286 "Em Atendimento - Residentes" after technician.

NEXT:
1. Watch first real tickets: Tiflux-opened ("🆕") and GLPI one without group (group 22 added?); first ARRECADAÇÃO one (stage 233286?). Close test GLPI #35009 / Tiflux #364984.
2. Untested live: ticket opened+closed between runs (AC 9).

RISKS:
- Files > ~2 MB fail on GLPI's PHP upload limit (logged, ticket still created). Infra fix.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
