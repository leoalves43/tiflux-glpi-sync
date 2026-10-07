# Plan 008 — consultar no Tiflux só o que mudou (spec: docs/specs/008-sincronizacao-por-mudancas-tiflux.md)

## Architecture delta
- Novo `sync/panorama_tiflux.py`: `ler_panorama_tiflux()` faz as 2 listagens por
  execução — `GET /tickets?filter_by=open` (conjunto de abertos) e a de
  atualizados desde o checkpoint (já existe em `mudancas_status_tiflux`) — e
  devolve `PanoramaTiflux(abertos, atualizados, mudancas)` ou `None` se alguma
  falhou ou veio cortada pelo teto de páginas. O panorama também traz os pares da
  varredura de segurança. `main()` lê o panorama e o passa para
  `sincronizar_followups(..., panorama)`; com `None`, pula os followups. Ler fora do
  orquestrador mantém intactas as filas de respostas do `FakeConnection` dos testes
  de cascata/recusa (cada `execute` consome uma).
- `TifluxClient._paginar` passa a levantar `ListagemTifluxIncompleta` (HTTP ≠ 200,
  corpo não-lista, teto de páginas atingido) em vez de devolver lista parcial.
  `listar_respostas`/`listar_comunicacoes_internas` mantêm o retorno `[]` atual,
  mas somam em `tiflux.listagens_com_falha`. Novo `listar_tickets_abertos()`.
- `sincronizacao_followups`, por chamado:
  - **completo** (caminho atual, com `GET /tickets/{n}`): chamados em `mudancas`,
    os N da varredura de segurança, e os que divergem do panorama — GLPI aberto e
    fora de `abertos` no Tiflux; GLPI Solucionado e dentro de `abertos`.
  - **leve** (sem GET individual): GLPI aberto + Tiflux aberto -> GLPI->Tiflux como
    hoje; `/answers` só se o ticket está em `atualizados`; marca varrido;
    `equalizar_reabertura_manual_do_tiflux`. GLPI fechado + Tiflux fora de
    `abertos` -> só a marca de varredura (`registrar_chamado_fechado_para_followups`).
  - Toda escrita continua no caminho completo, após a leitura individual (crit. 6).
- Checkpoint: linha marcadora em `api_glpi_tiflux_followups`
  (`direcao='checkpoint_tiflux'`, `id_glpi=0`, `id_origem=0`, ISO UTC em `mensagem`).
  Janela = checkpoint − `MARGEM_CHECKPOINT_TIFLUX_MINUTOS` (padrão 5); sem
  checkpoint, os 60 min atuais. Avança para o início da execução só se o panorama
  leu e `listagens_com_falha == 0` no fim.
- Varredura de segurança: `VARREDURA_COMPLETA_POR_EXECUCAO` (padrão 1) chamados por
  execução, o mais antigo pela marca `direcao='varredura_completa'`, `id_origem=-id_glpi`.
  206 chamados × ~3 min ≈ 10 h por volta (crit. 7).
- `SessaoTifluxLimitada` conta requisições; linha do placar ganha "Tiflux: N req".
- Sem mudança de schema (`direcao` VARCHAR(20) comporta os dois valores novos).

## Files touched
- `sync/tiflux_client.py`, `sync/limite_requisicoes_tiflux.py`, `sync/panorama_tiflux.py` (novo),
  `sync/mudancas_status_tiflux.py`, `sync/sincronizacao_followups.py`,
  `sync/placar_followups.py`, `sync/db_followups.py`, `sync/config.py`, `sync/main.py`.
- `tests/fake_clients.py`, `tests/test_tiflux_client.py`, `tests/test_db_followups.py`,
  `tests/test_panorama_tiflux.py` (novo), `tests/test_mudancas_status_tiflux.py`,
  `tests/test_sincronizacao_followups.py`, `tests/test_limite_requisicoes_tiflux.py`,
  `tests/test_placar_followups.py`, `tests/test_cascata_status.py`,
  `tests/test_recusa_glpi_sem_reabrir_tiflux.py` (passam um panorama de teste).
- `tests/test_main.py` (novo: ligação panorama -> followups -> checkpoint).
- `exemplo.env`, `docs/ARCHITECTURE.md`, `docs/data/audit_tables.toon`,
  `docs/decisions/LOG.md`, `docs/state/HANDOFF.md`.

## Risks
- Regressão na cascata/recusa (specs 004/006): mitigada por manter essas ações
  só no caminho completo, que não muda; testes por critério.
- Checkpoint preso: listagem cortada (> 2000 tickets atualizados na janela, ~meses
  de parada) falha sempre. Aviso no log aponta o teto `MAX_PAGINAS_TICKETS_TIFLUX`.
- Rollback: `git revert` + rebuild. As linhas marcadoras novas ficam inertes
  (nenhuma query antiga lê `checkpoint_tiflux`/`varredura_completa`; `id_glpi=0` não
  casa com `api_glpi_tiflux`). Nada irreversível.

## Tasks
- [x] 1. `ListagemTifluxIncompleta`, `listar_tickets_abertos`, `listagens_com_falha` + fake e testes. Done: suíte verde.
- [x] 2. Config (2 chaves + `exemplo.env`) e `db_followups`: checkpoint e marca de varredura completa + testes + `audit_tables.toon`. Done: verde.
- [x] 3. `panorama_tiflux.py` + `mudancas_status_tiflux` recebendo a listagem + `main` passa o panorama ao orquestrador + checkpoint + testes (crit. 5). Done: verde.
- [x] 4. Caminhos completo/leve em `sincronizacao_followups` + avanço do checkpoint + testes dos crit. 1–4, 6–8. Done: verde, crit. 1 medido no fake (≤ 5 chamadas).
- [ ] 5. Contador de requisições na sessão + placar + testes. Done: verde.
- [ ] 6. Rebuild do container; ARCHITECTURE, LOG, HANDOFF. Done: 3 execuções seguidas sem "⏳" com "Tiflux: ≤ 5 req"; resposta por e-mail no #364678 chega ao GLPI; encerrar #364678 no Tiflux encerra o GLPI #34900 em cascata.
