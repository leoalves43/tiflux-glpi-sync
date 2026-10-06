# Handoff

DONE (2026-10-06):
- Spec/plan 002: `sync.encerrar_legado` CLI (close GLPI for hand-opened Tiflux
  tickets, no history sync). 0f3e0f0: GLPI title not re-prefixed (GLPI #34840).
  264 tests green. Running container still has the old image until rebuilt.
- 34840/364448 auto-linked by the loop 14:41.
- Phone sync (3ab61fc). VPS deploy STOPPED: GLPI Caddy 302s the VPS IP.

NEXT:
1. User runs scratchpad `vincular.py` (blocked for the agent): links 34841/359311
   (full sync) and 29197/350369, 30489/353936, 32274/358390 (existing public
   followups/answers seeded as synced). Then
   `encerrar_legado --id-glpi 33545 --numero-tiflux 361210`. Tiflux #188191: user deciding.
2. Rebuild container; push; VPS `git pull`; move scheduler once IP is allowed.

RISKS:
- Two schedulers on the same DB = duplicate Tiflux tickets/followups.
- `encerrar_legado` is irreversible on the GLPI side; wrong pair = wrong ticket.
- VPS: pg_hba/firewall must accept Docker bridge; remote Postgres no sslmode.

CONTEXT: specs/002-encerrar-legado.md, decisions/LOG.md 2026-10-06.
