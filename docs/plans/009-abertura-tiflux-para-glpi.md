# Plano 009 — Chamado aberto no Tiflux registrado no GLPI

Spec: `docs/specs/009-abertura-tiflux-para-glpi.md`.

## Fatos verificados (leitura, 2026-10-09)
- Entidade do chamado = STII (1), decisão do usuário (localização 1685 é da
  entidade 1, não recursiva). Perfil "Técnico" da API vê 0 recursiva.
- Categorias 267/272/277/282: entidade 0, recursivas, incidente e requisição.
- Grupo 22: entidade 0 recursivo. Origem 6 "STI" existe.
- Localização 1685 "Área Técnica" está na entidade 1 (STII), NÃO recursiva
  — por isso o chamado é criado na entidade 1.
- `UserEmail?searchText[email]=` acha usuário por e-mail (LIKE: comparar exato).
- Telefone (plugin): `PluginFieldsTickettelefonelinha`, container 3, campo
  `telefonefield`, dados existentes em dígitos (`12981345555`).
- Listagens do Tiflux já trazem `desk`, `created_at`, `title`, `requestor`
  (com `telephone` E.164) — descobrir candidatos custa 0 requisição extra.
  `description` só no `GET /tickets/{n}`; anexos em `GET /tickets/{n}/files`.
- Tickets da integração: `created_by_way_of='Tiflux API'`, id 1041344; existe
  outro usuário API (186822). Hoje: 2 abertos nas 4 mesas sem `(id)` no
  título (Email, Whatsapp) — anteriores ao corte, ficam de fora.

## Desenho
- Descoberta: `PanoramaTiflux` guarda os dicts das 2 listagens; candidatos =
  abertos ∪ atualizados, mesa nas 4, `created_at >= ABERTURA_TIFLUX_DESDE`
  (UTC fixo no `.env`; vazio = funcionalidade desligada), título sem
  `(\d+)` no fim, número ausente de `api_glpi_tiflux` (qualquer status) e
  sem linha de intenção.
- Idempotência: linha em `api_glpi_tiflux_followups`, `direcao='abertura_tiflux'`,
  `id_origem=numero_tiflux` (chave existente, sem schema novo):
  `pendente` antes do POST (falha ao gravar = não cria) -> `sucesso` com
  `id_destino=id_glpi`, ou `erro` em recusa clara do GLPI (retentável, com
  GET individual do ticket). `pendente` encontrado = resultado desconhecido
  -> não cria, loga para revisão manual.
- Ordem na criação: GET ticket Tiflux -> intenção -> POST /Ticket (entidade,
  categoria, origem, localização, prioridade 3, `_users_id_requester`,
  `_users_id_assign` 4988, `_groups_id_observer` 22; conteúdo com
  `Solicitante: nome <email>` + descrição) -> `api_glpi_tiflux` sucesso
  IMEDIATO -> intenção sucesso -> passos não fatais: título GLPI
  `#n - titulo`, título Tiflux `titulo (id_glpi)`, telefone, anexos, Pendente.
- Guarda extra no caminho GLPI -> Tiflux: chamado cujo título já começa com
  `#<n> - ` não cria ticket no Tiflux (cobre queda entre o POST e a auditoria).
- Status Pendente (4) nos dois sentidos e na reabertura em cascata.

## Arquivos
Novos: `sync/regras_abertura_glpi.py`, `sync/glpi_abertura_client.py`,
`sync/db_abertura_tiflux.py`, `sync/abertura_tiflux_para_glpi.py`,
`sync/anexos_tiflux_para_glpi.py`, `sync/pendente_retroativo.py`, testes
correspondentes. Alterados: `sync/config.py`, `sync/panorama_tiflux.py`,
`sync/main.py`, `sync/processamento_chamado.py`, `sync/glpi_client.py`
(renomear `voltar_status_para_novo`; acessor da sessão, se preciso),
`sync/cascata_status.py`, `sync/tiflux_client.py` (renomear ticket, listar
arquivos), `tests/fake_clients.py`, `.env.example`, `README.md`, docs.
`glpi_client.py` (490) e `tiflux_client.py` (455) não crescem além de 500:
chamadas novas vão para módulos novos.

## Riscos
- IRREVERSÍVEL: criação de chamados reais no GLPI, renomear tickets no
  Tiflux, backfill Novo -> Pendente. Cada escrita ao vivo pede OK antes.
- Requerente real recebe o e-mail de chamado novo do GLPI.
- Conferir no 1º chamado de teste que entidade 1 + localização 1685 gravaram.
- Container de produção roda `main`: testes ao vivo com o container parado
  ou só via entrypoint manual, nunca os dois juntos.

## Tarefas
- [x] 1. Status Pendente: criação GLPI -> Tiflux e reabertura em cascata
  usam 4. Files: glpi_client, processamento_chamado, cascata_status, testes.
  Done: testes verdes; nenhum `status: 1` restante.
- [x] 2. Guarda `#<n> - ` no caminho GLPI -> Tiflux. Files:
  processamento_chamado, forcar_sincronizacao (reuso), testes. Done: teste
  de regressão "título prefixado não cria ticket".
- [x] 3. Regras puras: de-para mesa -> categoria, constantes fixas, telefone
  E.164 -> dígitos (padrão `1238971100`), filtro de candidato, títulos.
  Files: regras_abertura_glpi, config, .env.example, testes. Done: testes.
- [x] 4. Auditoria da intenção (`abertura_tiflux`) e exclusão dessa direção
  nas consultas existentes. Files: db_abertura_tiflux, db_followups (se
  preciso), audit_tables.toon, testes. Done: testes; queries de rodízio não
  veem a direção nova.
- [ ] 5. Escrita no GLPI: achar usuário por e-mail, criar chamado com atores,
  gravar telefone. Files: glpi_abertura_client, glpi_client, testes. Done:
  testes com fake.
- [ ] 6. Tiflux: renomear ticket, listar/baixar arquivos; anexos -> GLPI
  Document. Files: tiflux_client, anexos_tiflux_para_glpi, testes. Done: testes.
- [ ] 7. Orquestração + panorama + main + entrypoint manual
  `python -m sync.abertura_tiflux_para_glpi --numero-tiflux N [--aplicar]`
  (sem `--aplicar` só imprime o payload). Files: abertura_tiflux_para_glpi,
  panorama_tiflux, main, testes. Done: testes de AC 1-6, 8-11, 14.
- [ ] 8. Backfill `python -m sync.pendente_retroativo [--aplicar]`. Done:
  dry run lista chamados; teste.
- [ ] 9. Verificação ao vivo (com OK do usuário): dry run num ticket real;
  ticket de teste no Tiflux -> GLPI; resposta nos 2 sentidos; encerrar;
  reabrir; backfill. Done: AC 1-14 conferidos.
- [ ] 10. Docs: ARCHITECTURE, README, LOG, HANDOFF.
