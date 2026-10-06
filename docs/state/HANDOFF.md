# Handoff

DONE (2026-10-06):
- Spec/plan 002: `sync.encerrar_legado` CLI (close GLPI for hand-opened Tiflux
  tickets, no history sync). 0f3e0f0: GLPI title not re-prefixed (GLPI #34840).
  265 tests green. Local container rebuilt with both; pushed to GitHub.
- Hand-opened Tiflux tickets reconciled: 34840/364448 and 34841/359311 linked
  (full sync); 29197/350369, 30489/353936, 32274/358390 linked with existing
  public followups/answers seeded as synced (only new activity flows);
  33545/361210 closed in GLPI via `encerrar_legado`. GLPI 34848 created by
  hand for Tiflux #188191 (Finanças, requester 460) and linked; 15 answers synced,
  timeline fixed (date/date_creation = Tiflux time). 1face39: answers oldest-first.
- Phone sync (3ab61fc). VPS deploy STOPPED: GLPI Caddy 302s the VPS IP.

NEXT:
1. VPS `git pull`; after IP is allowed: `docker compose stop` locally,
   `up -d --build` on VPS.

RISKS:
- Two schedulers on the same DB = duplicate Tiflux tickets/followups.
- `encerrar_legado` is irreversible on the GLPI side; wrong pair = wrong ticket.
- VPS: pg_hba/firewall must accept Docker bridge; remote Postgres no sslmode.

CONTEXT: specs/002-encerrar-legado.md, decisions/LOG.md 2026-10-06.
