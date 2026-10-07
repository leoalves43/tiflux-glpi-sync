# Docs index

- `docs/ARCHITECTURE.md` — read when touching sync logic, adding an endpoint, or onboarding.
- `docs/decisions/LOG.md` — read when a design choice looks arbitrary and you need the why.
- `docs/state/HANDOFF.md` — read first, every session. Current status, what's next, open risks.
- `docs/specs/001-docker.md` — read when changing how/where the sync is scheduled or deployed.
- `docs/plans/001-docker.md` — read with the spec above; task checklist for the Docker move.
- `docs/specs/002-encerrar-legado.md` — read when closing in GLPI tickets opened by hand in Tiflux before the integration.
- `docs/plans/002-encerrar-legado.md` — read with the spec above; task checklist.
- `docs/specs/003-latencia-sincronizacao.md` — read when changing the followup rotation order or the loop interval.
- `docs/plans/003-latencia-sincronizacao.md` — read with the spec above; task checklist.
- `docs/specs/004-recusa-glpi-sem-reabrir-tiflux.md` — read when touching the GLPI-refusal -> Tiflux-reopen path.
- `docs/plans/004-recusa-glpi-sem-reabrir-tiflux.md` — read with the spec above; task checklist.
- `docs/specs/005-refatoracao.md` — read when refactoring without behavior change (constraints on call order and audit literals).
- `docs/plans/005-refatoracao.md` — read with the spec above; task checklist.
- `docs/specs/006-responsavel-apos-reabertura.md` — read when touching who is responsible in Tiflux after the integration reopens a ticket.
- `docs/plans/006-responsavel-apos-reabertura.md` — read with the spec above; task checklist.
- `docs/specs/007-limite-requisicoes-tiflux.md` — read when touching Tiflux HTTP calls, 429s or request pacing.
- `docs/plans/007-limite-requisicoes-tiflux.md` — read with the spec above; task checklist.
- `docs/data/audit_tables.toon` — read when writing SQL against either audit table (column names, types, conflict keys).

No other docs exist. A path not listed above does not exist — don't assume it.
