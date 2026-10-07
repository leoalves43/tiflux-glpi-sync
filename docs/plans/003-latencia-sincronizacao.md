# Plan 003 — latência de sincronização (spec: docs/specs/003-latencia-sincronizacao.md)

## Architecture delta
`db_followups.obter_chamados_para_varrer_followups` passa a ler a linha
`direcao='verificacao_status'` do chamado (gravada a cada varredura por
`registrar_chamado_aberto_varrido` / `registrar_chamado_fechado_para_followups`)
e devolve duas partes, nesta ordem:
1. todos os `status='sucesso'` cuja verificação é `aberto` ou inexistente
   (nunca varrido), sem LIMIT, por `ultima_varredura ASC NULLS FIRST`;
2. os de verificação `fechado`, `LIMIT config.tamanho_lote_fechados_followups`,
   mesma ordem.
Uma query (`UNION ALL` de dois SELECTs com ORDER BY/LIMIT próprios) ou duas;
decidir na task 1 pelo que ficar mais legível. Retorno inalterado
(`list[(id_glpi, numero_tiflux)]`). Config `tamanho_pagina_followups` ->
`tamanho_lote_fechados_followups` (padrão 50; o nome antigo deixa de descrever
o que limita). Loop: padrão 300 -> 120 s.

## Files touched
- `sync/db_followups.py` — query + docstring do rodízio.
- `sync/config.py` — renomear o campo e o comentário.
- `tests/test_db_followups.py` — testes da nova seleção.
- `docker/loop_sincronizacao.sh`, `docker-compose.yml` — 300 -> 120.
- `README.md`, `docs/ARCHITECTURE.md` (menções a 300 s e ao rodízio),
  `docs/decisions/LOG.md`, `docs/state/HANDOFF.md`.

## Risks
- Nada irreversível: só seleção de leitura e intervalo; reverter = revert do commit.
- Abertos sem teto: muitos abertos (centenas) alongam a execução (~0,26 s por
  chamado na varredura atual) e atrasam o ciclo inteiro, inclusive a criação de
  chamados. Hoje 28. Visível no log; paralelizar fica fora do escopo.
- Solução recusada no GLPI (chamado marcado `fechado`) é notada pelo lote de
  fechados: 50 / 176 ≈ 4 execuções ≈ 9 min (antes ≈ 20 min).
- 120 s + abertos sempre varridos ≈ 2,5× as requisições/hora ao GLPI da
  prefeitura. Monitorar timeouts no log nas primeiras horas;
  `INTERVALO_SEGUNDOS` volta a 300 sem rebuild.
- `FakeConnection` não executa SQL: o teste unitário só confere a forma da
  query e os parâmetros; a seleção real é verificada contra o Postgres (task 2,
  só leitura).

## Tasks
- [ ] 1. Rename do config + nova seleção + testes (sem LIMIT nos abertos,
      LIMIT do lote de fechados como parâmetro, retorno inalterado).
      Done: `python -m unittest` verde.
- [ ] 2. Verificação só leitura no container: rodar a função contra o banco e
      conferir que vêm todos os `aberto`/sem linha (contagem igual à do banco),
      depois no máximo 50 `fechado`. Done: saída confere (critérios 1–5).
- [ ] 3. Intervalo 300 -> 120 em `loop_sincronizacao.sh` e `docker-compose.yml`;
      README/ARCHITECTURE. Done: `grep -rn 300` sem menção ao intervalo antigo.
- [ ] 4. `docker compose up -d --build`; acompanhar 2 ciclos no log
      (intervalo ~2 min, sem erros). Done: log confere.
- [ ] 5. LOG.md, HANDOFF.md. Done: docs dentro dos limites de tamanho.
