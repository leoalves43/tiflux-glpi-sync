# Handoff

DONE (2026-10-19), spec/plano 014 completos na main e em produção (deploy 15:42), 486 testes verdes:
- Resposta pública do Tiflux com arquivos -> Documents ligados ao followup GLPI (itemtype ITILFollowup).
  GLPI -> Tiflux já levava anexos de followup desde 2026-09-21.
- GLPI #35249 recuperado: docs 17947-17953 no followup 78602; chamado seguiu Solucionado.
- GLPI grava `name` = "Documento: Acompanhamento - ..."; `filename` é o nome real (comportamento do GLPI).

NEXT:
1. Conferir a 1ª resposta real do Tiflux com anexo após o deploy (mensagem "| Anexos: N copiado(s)").
2. Conferir 1ª resposta de validação real (#365227/#365366); 1º ticket ARRECADAÇÃO; AC 9 spec 009.

RISKS:
- Respostas com anexo sincronizadas antes de 2026-10-19 15:42 seguem sem arquivos (sem backfill, decisão do usuário).
- Files > ~2 MB fail on GLPI's PHP upload limit (ex.: #35205, PDF 8 MB). `pendente` rows never retried.
- Validações 1475-1479 em chamados fora do escopo: se vinculados, pedido+resposta antigos são publicados.

CONTEXT: specs/014, plans/014, sync/anexos_tiflux_para_glpi.py, sync/publicacao_followups.py.
