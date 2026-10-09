# Handoff

DONE (2026-10-09), branch `feat/009-abertura-tiflux-para-glpi`, 442 tests green (3.14 + 3.13 image `tiflux-glpi-sync:teste-009`):
- Spec 009 + plan 009 approved; plan tasks 1-8 + 10 [x] (Pendente everywhere, title guard, rules, intent
  rows, GLPI writes, Tiflux rename/files, orchestration + CLI, Novo->Pendente backfill).
- Dry runs only (no writes): CLI on Tiflux #364844 (payload ok) / #364925 (correctly not candidate);
  backfill lists 3 Novo tickets: 34982, 34986, 34990.

NEXT (plan task 9, every write needs user OK):
1. User picks the go-live cutoff (ABERTURA_TIFLUX_DESDE) and opens a test ticket in Tiflux.
2. Stop prod container -> CLI `--aplicar` on the test ticket only -> GET Ticket, Ticket_User,
   Group_Ticket, phone row, Document_Item: entity 1, location 1685, status 4, 1 requester, HTML ok.
3. Full cycle from the branch (writes prod: real tickets get Pendente, post-cutoff tickets imported);
   GLPI-side test followup from an account != 4988 (anti-echo skips 4988); close; reopen.
4. Merge + rebuild container; THEN `python -m sync.pendente_retroativo --aplicar` (main flips back to Novo).

RISKS:
- Prod container runs `main`: no Pendente, no title guard. Don't run branch code alongside it.
- Requester gets GLPI new-ticket e-mail (user accepted). E-mail tickets carry big HTML + S3 links that expire.
- `pendente` intent rows are never auto-retried: resolve by hand (set sucesso + id, or delete).

CONTEXT: specs/009, plans/009 (verified facts section), data/audit_tables.toon (abertura_tiflux rows).
