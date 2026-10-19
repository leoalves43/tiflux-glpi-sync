# 014 — Anexos de resposta do Tiflux chegam no followup do GLPI

## Intent
Resposta pública do Tiflux com arquivos vira followup no GLPI só com o texto
(GLPI #35249: 7 planilhas perdidas). Todo anexo de followup deve cruzar nos
dois sentidos; GLPI -> Tiflux já faz isso desde 2026-09-21.

## User outcome
Quem responde no Tiflux com anexos vê os mesmos arquivos no followup
correspondente do GLPI, na timeline do chamado.

## Constraints
- O arquivo fica no followup (Document ligado ao ITILFollowup), não no chamado.
- Requisição extra ao Tiflux só para resposta com `files_count` > 0 (spec 007).
- Falha de anexo (tamanho, download, recusa do GLPI) vai na mensagem de
  auditoria; o followup segue 'sucesso' (refazê-lo duplicaria o texto).
- Não muda status do chamado no GLPI além do que o followup já faz.
- Fora do escopo: respostas já sincronizadas antes do deploy (só #35249 é
  recuperado, à mão); comunicações internas; arquivos pendurados direto no
  chamado depois da criação.

## Acceptance criteria
1. Resposta com N arquivos: N Documents ligados ao followup criado.
2. Resposta sem arquivos: nenhuma requisição extra ao Tiflux.
3. Arquivo acima do limite, sem download ou recusado: aparece no resumo da
   mensagem; registro 'sucesso'.
4. Falha ao criar o followup: nenhum anexo enviado.
5. GLPI #35249: os 7 arquivos da resposta 32082144 no followup 78602.
