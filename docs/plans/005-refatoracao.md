# Plan 005 — refatoração (spec: docs/specs/005-refatoracao.md)

## Architecture delta
`sync/sincronizacao_followups.py` vira três módulos, sem shims de reexportação:
- `sincronizacao_followups.py` — orquestrador (`sincronizar_followups`,
  `_sincronizar_chamado_aberto`) e o placar.
- `cascata_status.py` — encerramento/reabertura em cascata e reabertura do
  Tiflux após recusa (+ constantes `STATUS_GLPI_*`).
- `publicacao_followups.py` — os dois sentidos de publicação de followups.
Placar `totais: dict` -> dataclass `PlacarFollowups` (mesmos números no log).

## Files touched
`sync/*.py` (exceto config/html_texto só tipos), `tests/*` (imports + divisão
de `test_sincronizacao_followups.py`), `docs/ARCHITECTURE.md`,
`docs/decisions/LOG.md`, `docs/state/HANDOFF.md`.

## Risks
- Reordenar uma chamada muda o comportamento e desalinha a fila do
  `FakeConnection`; teste quebrado por ordem = corrigir o código, não o teste.
- Import circular entre os módulos novos: cascata não importa o orquestrador.
- Nada irreversível; cada task é um commit revertível.

## Tasks
- [x] 1. Extrair `cascata_status.py` e `publicacao_followups.py`; atualizar
      importadores (`main`, `encerrar_legado`, `forcar_sincronizacao`, testes).
      Done: testes verdes, arquivos < 500.
- [x] 2. Dividir `tests/test_sincronizacao_followups.py` por módulo (classes
      movidas sem alteração). Done: mesma contagem de testes, verdes.
- [x] 3. `PlacarFollowups` no lugar do dict `totais`. Done: verdes; log igual.
- [x] 4. Tipos: alias `ConexaoDb`, `NumeroTiflux = int | str`, `-> None` em
      `__init__`/handlers. Done: verdes; script AST sem parâmetro sem tipo.
- [x] 5. Funções > 20 linhas: `processamento_chamado._processar`,
      `_montar_form_data`, `forcar_sincronizacao` (`main`, `_forcar_*`),
      `main.main`/`_processar_chamados_pendentes`, `glpi_client`
      (`buscar_chamados_desde`, `_baixar_documento`), `tiflux_client`
      (`__init__`, `enviar_anexos`, `_paginar`). Done: verdes; script AST.
- [x] 6. Docstrings/docs desatualizados (rodízio, Solucionado na ARCHITECTURE,
      tabela de módulos). Done: ARCHITECTURE ≤ 100 linhas.
- [x] 7. Rebuild + 2 ciclos; LOG e HANDOFF. Done: log sem Traceback.
