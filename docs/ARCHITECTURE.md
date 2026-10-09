# Architecture

Package `sync/`, entrypoint `glpi_tiflux.py` (shim for `sync.main.main` — keep the name, the
scheduler calls it). Docker container `tiflux-glpi-sync` (`docker/loop_sincronizacao.sh`: run, sleep
`INTERVALO_SEGUNDOS`=120, never overlaps); manual: `python glpi_tiflux.py`. Env vars override `.env`
(`Config.carregar`); DB is remote Postgres. Every file stays under 500 lines.

## Data flow

```
GLPI (REST, session-token auth)  <-->  sync/*.py  <-->  Tiflux (REST, bearer auth)
                                            v  Postgres (2 audit tables)
```

Three sync passes per run, all driven from `sync/main.py:main()`:

1. **Ticket creation, GLPI -> Tiflux.** `GlpiClient.buscar_chamados_desde()` probes
   `GET /Ticket/{id}` (`/search/Ticket` is unreliable here — don't use it).
   `processar_chamado()` links an existing Tiflux ticket titled `"<titulo> (<id_glpi>)"`
   instead of duplicating, refuses GLPI titles already prefixed `#<n> - `, else
   creates the Tiflux ticket, assigns a technician, uploads attachments.
2. **Ticket creation, Tiflux -> GLPI (spec 009, off unless `ABERTURA_TIFLUX_DESDE`).**
   `abrir_chamados_do_tiflux()` (sync/abertura_tiflux_para_glpi.py) picks candidates from
   the panorama's listed tickets (0 extra requests) + `erro` retries; per ticket: GET,
   intent row `pendente`, POST /Ticket via `GlpiAberturaClient`, `api_glpi_tiflux`
   `sucesso` at once, then rename Tiflux `(<id_glpi>)`, phone, files, Pendente.
   Idempotency/echo rules: decisions/LOG.md 2026-10-09.
3. **Followup sync, bidirectional, for already-synced open tickets.** `main()` reads a
   `PanoramaTiflux` (sync/panorama_tiflux.py, spec 008): open tickets + tickets updated
   since the checkpoint (2 listings); any failure -> `None`, creation and followups skipped. Then
   `sincronizar_followups()` takes state changes + safety sweep + the rotation (every
   GLPI open/Solucionado `sucesso` ticket, 50 GLPI-Fechado). Per ticket,
   `conferir_por_completo()` picks the full path (`GET /tickets/{n}`, all writes) or
   the light one (no Tiflux GET; `/answers` only if updated). Failures -> `prioritario`:
   - `sincronizar_followups_glpi_para_tiflux()` — GLPI `ITILFollowup` ->
     Tiflux `/client-answers`, always with the GLPI author's name (public only).
   - `sincronizar_followups_tiflux_para_glpi()` — Tiflux answers/internal
     communications -> GLPI `ITILFollowup`.
   Cascade is Tiflux -> GLPI, except: a cascade-closed chamado reopened in GLPI while
   Tiflux is closed -> `reabrir_tiflux_apos_recusa_glpi()` reopens Tiflux (retries each run, spec 004).
   Every GLPI ticket the integration creates, reopens or answers ends Pendente (4).

## Modules

| File | Responsibility |
|---|---|
| `sync/config.py` | `Config` (frozen dataclass, built once in `main()` — nothing does file I/O at import time), `carregar_credenciais`, `log()` |
| `sync/db_chamados.py` | Postgres — one row per GLPI ticket (`api_glpi_tiflux`) |
| `sync/db_followups.py` | Postgres — one row per followup (`api_glpi_tiflux_followups`) |
| `sync/glpi_client.py` | `GlpiClient` — thin wrapper over GLPI REST, owns the session headers |
| `sync/tiflux_client.py` | `TifluxClient` — thin wrapper over Tiflux REST, owns the header dicts and the mesa-validation cache |
| `sync/limite_requisicoes_tiflux.py` | `SessaoTifluxLimitada` — session used by `TifluxClient.conectar`; waits on `RateLimit-*` headers, retries 429 (spec 007) |
| `sync/html_texto.py` | `html_para_texto_plano()` — GLPI HTML description -> Tiflux plain text |
| `sync/regras_negocio.py` | category->desk mapping, technician/priority lookup, requester-is-author check |
| `sync/abertura_tiflux_para_glpi.py` | spec 009 orchestrator; rules in `regras_abertura_glpi`, intent rows in `db_abertura_tiflux`, files in `anexos_tiflux_para_glpi` |
| `sync/glpi_abertura_client.py` | `GlpiAberturaClient` (via `GlpiClient.cliente_abertura()`): user by e-mail, POST /Ticket, phone, /Document |
| `sync/processamento_chamado.py` | `processar_chamado()` — creates one ticket end to end |
| `sync/sincronizacao_followups.py` | orchestrator: picks tickets, runs publish + cascade per ticket, `PlacarFollowups` log line |
| `sync/publicacao_followups.py` | the two directional followup publishers (GLPI->Tiflux, Tiflux->GLPI) |
| `sync/cascata_status.py` | cascade close/reopen GLPI<->Tiflux and Tiflux reopen after GLPI refusal |
| `sync/mudancas_status_tiflux.py` | picks tickets recently closed/reopened in Tiflux so the cascade runs every cycle |
| `sync/panorama_tiflux.py` | `PanoramaTiflux`: the 2 listings per run, checkpoint window, safety-sweep pairs (spec 008) |
| `sync/main.py` | `main()` — wiring, candidate selection, top-level logging |
| `sync/forcar_sincronizacao.py` | `python -m sync.forcar_sincronizacao --id-glpi N` — manual backup for one ticket skipped by the cron; see below |
| `sync/abrir_ticket_tiflux_no_glpi.py` | `python -m sync.abrir_ticket_tiflux_no_glpi --numero-tiflux N [--aplicar]` — one ticket, dry run by default |
| `sync/pendente_retroativo.py` | one-off: synced Novo tickets -> Pendente (after deploy only) |
| `sync/encerrar_legado.py` | `python -m sync.encerrar_legado --id-glpi N --numero-tiflux M` — one-off GLPI close for tickets opened by hand in Tiflux pre-integration; never writes `api_glpi_tiflux` (spec 002) |

Clients built once per run in `main()`, passed as parameters; `TifluxClient` caches desks.

## Two audit tables (Postgres, schema from `DB_SCHEMA` cred, default `siap_custom`)

Full DDL and column reference: `docs/data/audit_tables.toon`. Summary:

- `api_glpi_tiflux` — one row per GLPI ticket (`id_glpi` unique), creation only (both directions).
- `api_glpi_tiflux_followups` — one row per followup/answer, conflict key
  `(direcao, id_origem)`. Tracks both sync directions and doubles as the
  echo-prevention mechanism (see decisions/LOG.md).

## External APIs

- GLPI: session-token auth (`initSession`/`killSession`), sub-item pattern
  (`GET /Ticket/{id}/<SubItem>`), creation via `{"input": {...}}`; no local spec, verified live.
- Tiflux: bearer auth, documented in `openapi-spec-tiflux.json` (local file,
  1.7MB — grep it, don't read it whole). Three header dicts (`_cabecalhos_tiflux`):
  GET never sends Content-Type; followup POSTs force multipart (see LOG.md).

## Manual force-sync entrypoint

`sync/forcar_sincronizacao.py` (README): `processar_chamado` + both followup functions, no
cascade; never creates when `numero_tiflux IS NOT NULL` (even `erro`, bug below). Its
advisory lock blocks two forced runs on one ticket, not the container loop.

## Known pre-existing bug (not fixed, tracked)

Technician-assignment failure in `processar_chamado` stores `status='erro'` *with*
`numero_tiflux` set; retrying re-creates (duplicates) the Tiflux ticket. So
`id_glpi -> numero_tiflux` is only reliable on `status='sucesso'` rows — keep every
read path filtering on that.
