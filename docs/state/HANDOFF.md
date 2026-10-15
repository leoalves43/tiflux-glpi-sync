# Handoff

DONE (2026-10-15), plano 013 completo na main e em produção, 474 testes verdes:
- Loop do container: 120 s alinhado ao relógio (12:00, 12:02...) + 1 ciclo ao subir, desde 2026-10-15 tarde.
- Spec 013: validação GLPI -> resposta pública no Tiflux, corte VALIDACAO_GLPI_DESDE_ID=1474 (.env).
  10:40: pedido 1474 -> Tiflux #365227 (id 32029054), 1480 -> #365366 (id 32029050).
- Specs 009-012 em produção desde 2026-10-09 (ver specs/plans).

NEXT:
1. Conferir a 1ª resposta real de validação (✅/❌) em #365227/#365366 — AC 2 só testado em unidade.
2. GLPI #35071 encerrado 11:30 após fecharem as tarefas. Followup 78438 (erro 422, Tiflux
   fechado) ignorado por decisão do usuário: linha 'erro' fica, sem retentativa.
3. Watch first ARRECADAÇÃO ticket (stage 233286?) and Tiflux-opened ("🆕"). Untested live: AC 9 spec 009.

RISKS:
- Validações 1475-1479 (#35107, #35111, #35121, #35126, #35130) estão em chamados fora do escopo;
  se a categoria mudar e o chamado for vinculado, pedido+resposta antigos são publicados.
- Files > ~2 MB fail on GLPI's PHP upload limit. `pendente` intent rows never auto-retried.

CONTEXT: specs/013, plans/013 (fatos verificados), data/audit_tables.toon (validacao_* rows).
