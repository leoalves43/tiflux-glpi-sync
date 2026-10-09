# Plano 012 — Estágio inicial da ARRECADAÇÃO

Spec: `docs/specs/012-estagio-arrecadacao.md`. Fato lido em 2026-10-09:
`GET /desks/37964/stages` -> "Em Atendimento - Residentes" = 233286.

## Arquivos
`sync/regras_negocio.py` (estágio por mesa), `sync/tiflux_client.py`
(`mover_para_estagio`), `sync/processamento_chamado.py`, testes, README, LOG.

## Tarefas
- [x] 1. Regra + cliente + passo pós-técnico. Done: testes AC 1-3.
- [ ] 2. Deploy; conferir no primeiro chamado real da ARRECADAÇÃO.
