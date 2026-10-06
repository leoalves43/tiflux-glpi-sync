# Handoff

DONE (2026-10-06):
- Spec/plan 002: `python -m sync.encerrar_legado --id-glpi N --numero-tiflux M`
  closes in GLPI a chamado whose Tiflux ticket was opened by hand before the
  integration. No history sync, no `api_glpi_tiflux` row. 263 tests green.
  Not yet run against production.
- Listed open Tiflux tickets with no audit row (Infraestrutura excluded): 6
  (#188191, #350369, #353936, #358390, #359311, #364448). All still open in
  Tiflux, so the CLI would refuse them today.
- Requestor phone sync (3ab61fc). VPS deploy STOPPED: GLPI's Caddy answers
  302 for the VPS egress IP; waiting on prefeitura TI.

NEXT:
1. Push; on VPS `git pull`. Run `encerrar_legado` on one closed pair first.
2. After IP is allowed: `docker compose stop` locally, `up -d --build` on VPS.

RISKS:
- Two schedulers on the same DB = duplicate Tiflux tickets/followups.
- `encerrar_legado` is irreversible on the GLPI side; wrong pair = wrong ticket.
- Ticket without phone on a desk that requires phone still 422s.
- VPS: pg_hba/firewall must accept Docker bridge; remote Postgres no sslmode.

CONTEXT: specs/002-encerrar-legado.md, decisions/LOG.md 2026-10-06.
