# Plano 014 — Anexos de resposta Tiflux -> followup GLPI

Spec: `docs/specs/014-anexos-resposta-tiflux-para-glpi.md`. Fatos lidos em 2026-10-19:
- `GET /tickets/{n}/answers` traz `files_count`; `GET /tickets/{n}/answers/{id}` traz
  `files` [{id, file_name, content_type, size, url S3 72 h}]. `/answers/{id}/files` não existe (404).
- `POST /Document` com `itemtype: ITILFollowup, items_id: <followup>` cria o vínculo
  (doc 17947 -> followup 78602, chamado Solucionado sem mudar status nem date_mod).

## Arquivos
`sync/tiflux_client.py` (`listar_arquivos_resposta`), `sync/glpi_abertura_client.py`
(`anexar_documento` com itemtype), `sync/anexos_tiflux_para_glpi.py` (cópia da
resposta), `sync/publicacao_followups.py`, `tests/fake_clients.py`, testes, LOG, HANDOFF.

## Tarefas
- [x] 1. Cliente Tiflux lista arquivos da resposta; `anexar_documento` recebe itemtype. Done: testes.
- [ ] 2. Cópia dos arquivos da resposta no followup recém-criado. Done: testes AC 1-4.
- [ ] 3. Deploy + recuperar #35249 (6 arquivos restantes; 1 já enviado no probe). Done: AC 5.
