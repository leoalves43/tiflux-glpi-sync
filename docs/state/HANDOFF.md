# Handoff

DONE (2026-10-09), branch `feat/009-abertura-tiflux-para-glpi`, 442 tests green (3.14 + 3.13 image `tiflux-glpi-sync:teste-009`):
- Spec 009 + plan 009 approved; plan tasks 1-8 [x] (Pendente everywhere, title guard, rules, intent
  rows, GLPI writes, Tiflux rename/files, orchestration + CLI, Novo->Pendente backfill).
- Dry runs only (no writes): CLI on Tiflux #364844 (payload ok) / #364925 (correctly not candidate);
  backfill lists 3 Novo tickets: 34982, 34986, 34990.

NEXT:
1. Plan task 9, live, each step with user OK: stop prod container, set ABERTURA_TIFLUX_DESDE, test ticket
   in Tiflux -> one cycle `python glpi_tiflux.py` from the branch -> check GLPI fields (entity 1 + location
   1685 actually saved, status 4, requester, observer 22, phone, attachment), Tiflux title "(id)".
2. Answers both ways, close, reopen; then `python -m sync.pendente_retroativo --aplicar`.
3. Task 10 docs (ARCHITECTURE, README, LOG); merge to main + rebuild container (user decides).

RISKS:
- Prod container runs `main`: no Pendente, no title guard. Don't run branch code alongside it.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
