# Plano 010 — INFRAESTRUTURA e só o cliente da prefeitura

Spec: `docs/specs/010-infraestrutura-e-cliente.md`. Fatos lidos em 2026-10-09:
mesa 38853 ativa e do cliente 762707; prioridades 123345/123346/123347;
categoria 348 entidade 0 recursiva; #364799 e #364496 são do cliente 762707,
abertos, 0 e 2 respostas, sem arquivos.

## Arquivos
`sync/regras_negocio.py`, `sync/regras_abertura_glpi.py`,
`sync/abertura_tiflux_para_glpi.py`, `sync/abrir_ticket_tiflux_no_glpi.py`,
testes correspondentes, `README.md`, `docs/decisions/LOG.md`, HANDOFF.

## Riscos
- IRREVERSÍVEL: criar #364799/#364496 no GLPI (requerentes recebem e-mail).
- Eco: respostas Tiflux -> GLPI são gravadas como 4988, que o caminho
  GLPI -> Tiflux ignora (verificado ao vivo no GLPI #35009).

## Tarefas
- [x] 1. De-para nos dois sentidos + prioridade da mesa 38853. Done: testes.
- [x] 2. Filtro de cliente no candidato à abertura. Done: teste AC 3.
- [x] 3. `--ignorar-corte` no CLI. Done: teste AC 4.
- [ ] 4. Deploy, importar os 2 tickets, conferir respostas e eco. Done: AC 5.
- [ ] 5. README, LOG, HANDOFF.
