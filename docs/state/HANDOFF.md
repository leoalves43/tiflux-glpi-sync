# Handoff

DONE (2026-10-06):
- Requestor phone sync: GLPI ticket Fields plugin phone -> Tiflux requestor
  (PUT when differs, on register too). Fixes 422 "Requestor telephone can not
  be blank" on desk FINANÇAS (GLPI #34812, now Tiflux #364468). 252 tests green.
  Local container rebuilt and running clean.
- VPS deploy built but STOPPED: GLPI's Caddy answers 302 -> /pmc/ for the VPS
  egress IP. Waiting on prefeitura TI. VPS `.env` needs 644.

NEXT:
1. On VPS: `git pull` (GitHub has 3ab61fc, phone sync).
2. After IP is allowed: `docker compose stop` locally, `up -d --build` on VPS.

RISKS:
- Two schedulers on the same DB = duplicate Tiflux tickets/followups.
- Ticket without phone in the plugin on a desk that requires phone still 422s.
- Plugin itemtype name is instance-specific (`sync/glpi_client.py` constant).
- VPS: pg_hba/firewall must accept Docker bridge (172.16.0.0/12).
- Remote Postgres has no sslmode set.

CONTEXT: decisions/LOG.md 2026-10-06, 2026-10-02; specs/001-docker.md.
