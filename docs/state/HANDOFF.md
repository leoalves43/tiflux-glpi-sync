# Handoff

DONE (2026-10-09), branch `feat/009-abertura-tiflux-para-glpi`, 443 tests green (3.14 + 3.13):
- Spec/plan 009 tasks 1-8 + 10 [x]. Live (container stopped, cutoff 2026-10-09T17:25:00Z in .env):
  Tiflux #364984 -> GLPI #35009 (entity 1, loc 1685, cat 272, Pendente, png copied); answer both
  ways; Tiflux close -> Solucionado; API reopen -> Pendente. GLPI #35000/#35002 -> Tiflux, Pendente.
- GLPI #35007 = first test, Solucionado and unlinked (audit numero_tiflux NULL) by hand.

NEXT:
1. Container is STOPPED: merge to main + `docker compose up -d --build` (ABERTURA_TIFLUX_DESDE is in .env).
2. Then `python -m sync.pendente_retroativo --aplicar` (dry run: 34982, 34986, 34990).
3. Untested live: ticket opened+closed between runs (AC 9). Files > ~2 MB fail on GLPI's PHP upload limit.

RISKS:
- Prod container runs `main`: no Pendente, no title guard. Don't run branch code alongside it.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
