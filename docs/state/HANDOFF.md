# Handoff

DONE (2026-10-06), all pushed, local container rebuilt, 265 tests green:
- Spec/plan 002 `sync.encerrar_legado`; GLPI title no longer double-prefixed;
  Tiflux answers published oldest-first (1face39).
- Hand-opened Tiflux tickets reconciled: 34840/364448, 34841/359311 full sync;
  29197/350369, 30489/353936, 32274/358390 only new activity (old seeded);
  33545/361210 closed; GLPI 34848 created for #188191; 34848/34841 dates fixed.
- VPS deploy STOPPED: GLPI Caddy 302s the VPS IP (waiting on prefeitura TI).

NEXT:
1. VPS `git pull`; after IP is allowed: `docker compose stop` locally,
   `up -d --build` on VPS.

RISKS:
- Two schedulers on the same DB = duplicate Tiflux tickets/followups.
- `encerrar_legado` is irreversible on the GLPI side; wrong pair = wrong ticket.
- VPS: pg_hba/firewall must accept Docker bridge; remote Postgres no sslmode.

CONTEXT: specs/002-encerrar-legado.md, decisions/LOG.md 2026-10-06.
