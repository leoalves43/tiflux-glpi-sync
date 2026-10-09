# Plano 011 — Escopo pela categoria

Spec: `docs/specs/011-escopo-por-categoria.md`. Fato lido em 2026-10-09: faixa
da sondagem #34991–#35021, 22 não sincronizados, nenhum com categoria do de-para.

## Arquivos
`sync/processamento_chamado.py`, `sync/glpi_client.py` (sai
`chamado_tem_grupo_observador`, entra `adicionar_grupo_observador`),
`sync/regras_negocio.py` + `sync/regras_abertura_glpi.py` (constante do grupo
22 num lugar só), `sync/config.py` (sai `ids_grupo_observador`),
`sync/db_chamados.py` (docstrings), testes, README, ARCHITECTURE, LOG, HANDOFF.

## Riscos
- Mais chamados vão ao Tiflux (os da categoria sem grupo); conferido que nada
  da faixa atual entra de uma vez.

## Tarefas
- [x] 1. Escopo pela categoria em processar_chamado. Done: testes AC 1-2.
- [x] 2. Grupo 22 observador junto do técnico. Done: testes AC 3-4.
- [x] 3. Deploy (16:48, 1º ciclo: 22 ignorados, 0 criados) e docs. Conferir o
  grupo 22 no primeiro chamado real criado depois disso.
