# Plan 003 — latência de sincronização (spec: docs/specs/003-latencia-sincronizacao.md)

## Architecture delta
`db_followups.obter_chamados_para_varrer_followups` ganha um LEFT JOIN na linha
`direcao='verificacao_status'` do chamado (gravada a cada varredura por
`registrar_chamado_aberto_varrido` / `registrar_chamado_fechado_para_followups`)
e ordena por `COALESCE(v.status = 'fechado', FALSE)` antes de
`ultima_varredura ASC NULLS FIRST`. Sem linha (nunca varrido) e `aberto` = FALSE
-> vêm primeiro; `fechado` = TRUE -> ocupam só as vagas restantes. Mesmo LIMIT,
mesmos parâmetros, mesmo retorno. Loop: padrão 300 -> 120 s.

## Files touched
- `sync/db_followups.py` — query + docstring do rodízio.
- `tests/test_db_followups.py` — teste da nova ordem.
- `docker/loop_sincronizacao.sh`, `docker-compose.yml` — 300 -> 120.
- `README.md`, `docs/ARCHITECTURE.md` (menções a 300 s), `docs/decisions/LOG.md`,
  `docs/state/HANDOFF.md`.

## Risks
- Nada irreversível: só ordem de leitura e intervalo; reverter = revert do commit.
- Solução recusada no GLPI (chamado marcado `fechado`) passa a ser notada só
  nas vagas restantes: hoje 22 vagas / 176 fechados ≈ 8 execuções ≈ 18 min
  (antes ≈ 4 × 5 min = 20 min). Aceito pela spec (critério 4).
- Mais de 50 abertos -> rodízio volta a dividir entre abertos (critério 3);
  fechados deixam de ser revisitados até sobrar vaga. Alerta: logar quando o
  lote vier só de abertos? Fora do escopo; anotar no HANDOFF.
- 120 s ≈ 2,5× as requisições/hora ao GLPI da prefeitura. Monitorar timeouts
  no log nas primeiras horas; `INTERVALO_SEGUNDOS` volta a 300 sem rebuild.
- `FakeConnection` não executa SQL: o teste unitário só confere a cláusula;
  a ordem real é verificada contra o Postgres (task 2, só leitura).

## Tasks
- [ ] 1. Query nova + teste (cláusula de prioridade presente, parâmetros e
      retorno inalterados). Done: `python -m unittest` verde.
- [ ] 2. Verificação só leitura no container: rodar a função contra o banco e
      conferir que todos os chamados `aberto`/sem linha vêm antes do 1º
      `fechado`. Done: saída confere (critérios 1, 2, 4, 5).
- [ ] 3. Intervalo 300 -> 120 em `loop_sincronizacao.sh` e `docker-compose.yml`;
      README/ARCHITECTURE. Done: `grep -rn 300` sem menção ao intervalo antigo.
- [ ] 4. `docker compose up -d --build`; acompanhar 2 ciclos no log
      (intervalo ~2 min, sem erros). Done: log confere.
- [ ] 5. LOG.md, HANDOFF.md. Done: docs dentro dos limites de tamanho.
