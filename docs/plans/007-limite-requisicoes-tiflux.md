# Plan 007 — limite de requisições do Tiflux (spec: docs/specs/007-limite-requisicoes-tiflux.md)

## Architecture delta
Novo módulo `sync/limite_requisicoes_tiflux.py` com `SessaoTifluxLimitada`:
a mesma interface `get/post/put` de `requests.Session`, envolvendo uma
sessão real. Antes de cada chamada, espera se a última resposta deixou a cota
na reserva; ao receber 429, espera até o reset e repete (até 2 vezes).
Relógio e `sleep` entram pelo construtor, para os testes. `TifluxClient.conectar`
monta essa sessão; o `TifluxClient` em si não muda (já recebe `session`).
Nova config `reserva_requisicoes_tiflux` (env `RESERVA_REQUISICOES_TIFLUX`, padrão 5).

## Files touched
- `sync/limite_requisicoes_tiflux.py` (novo), `sync/tiflux_client.py` (`conectar`),
  `sync/config.py`.
- `tests/test_limite_requisicoes_tiflux.py` (novo, com relógio e sessão fakes nomeados).
- `exemplo.env`, `docs/ARCHITECTURE.md` (tabela de módulos), `docs/decisions/LOG.md`,
  `docs/state/HANDOFF.md`.

## Risks
- Uma execução pode ficar até cerca de 1 min mais lenta quando a cota acaba;
  é o efeito pretendido.
- Repetir um POST que recebeu 429 é seguro: um 429 quer dizer que a API não
  processou a chamada. Os anexos são `bytes` em memória, então dá para
  reenviar.
- Nada irreversível.

## Tasks
- [x] 1. `SessaoTifluxLimitada` + testes dos critérios 1–5. Done: `python -m unittest` verde.
- [x] 2. Config + `conectar` + `exemplo.env` (critério 6) + teste. Done: verde.
- [ ] 3. Rebuild do container; ARCHITECTURE, LOG, HANDOFF. Done: execução completa sem 429 no log.
