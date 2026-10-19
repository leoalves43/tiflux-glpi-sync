# Handoff

DONE (2026-10-19), diagnóstico GLPI #35249 / Tiflux #365680 (sem código alterado):
- Resposta Tiflux 32082144 (files_count=7) virou followup GLPI 78602 só com texto.
- Causa: `_publicar_respostas_publicas` (sync/publicacao_followups.py:196) não tem caminho de anexos.
  Arquivos ficam só em `GET /tickets/{n}/answers/{id}` (campo `files`, URL S3 72 h); `/tickets/{n}/files` vazio.
- Sistêmico: toda resposta Tiflux com anexo perdeu os arquivos (LOG 2026-10-07: "não testado").
- Plano 013 completo em produção desde 2026-10-15 (loop 60 s, validação GLPI no Tiflux).

NEXT:
1. Spec 014: anexos de resposta Tiflux -> GLPI (gatilho files_count>0, reusar `_copiar` de
   anexos_tiflux_para_glpi.py, falha de anexo não marca 'erro'). Aguardando aprovação do usuário.
2. Backfill dos 7 arquivos no #35249 (já Solucionado): escrita ao vivo, pedir aprovação antes.
3. Conferir 1ª resposta de validação real (#365227/#365366); 1º ticket ARRECADAÇÃO; AC 9 spec 009.

RISKS:
- Vincular Document a ITILFollowup via API não verificado ao vivo.
- Files > ~2 MB fail on GLPI's PHP upload limit (ex.: #35205, PDF 8 MB). `pendente` rows never retried.
- Validações 1475-1479 em chamados fora do escopo: se vinculados, pedido+resposta antigos são publicados.

CONTEXT: sync/publicacao_followups.py, sync/anexos_tiflux_para_glpi.py, glpi_abertura_client.py:101.
