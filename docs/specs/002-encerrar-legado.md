# 002 — Encerrar no GLPI chamados abertos manualmente no Tiflux antes da integração

## Intent
Chamados GLPI atendidos por tickets abertos à mão no Tiflux (antes da API) ficam
abertos no GLPI para sempre: a integração não conhece o vínculo. Encerrar esses
chamados no GLPI, uma vez, sem trazer o histórico de comunicação.

## User outcome
Operador informa o par (id GLPI, número Tiflux) e o chamado GLPI fica
Solucionado, com a última resposta pública do técnico no Tiflux como solução.

## Constraints
- Nenhum followup/resposta é sincronizado, em nenhum sentido.
- O chamado não passa a fazer parte do ciclo automático (sem rodízio, sem
  cascata futura, sem reabertura do Tiflux em caso de recusa da solução).
- Execução manual, um par por vez.

## Acceptance criteria
1. Tiflux fechado + GLPI aberto (Novo/Processando/Pendente) -> GLPI recebe
   técnico (se não tinha), solução = última resposta pública de técnico no
   Tiflux (autor + data), status Solucionado.
2. Ticket Tiflux ainda aberto -> recusa, nada muda no GLPI.
3. Chamado GLPI já fechado/solucionado -> recusa, nada muda.
4. Chamado ou ticket não encontrado -> erro com o id informado, nada muda.
5. Nenhuma linha é gravada em `api_glpi_tiflux`; nenhum followup é criado em
   nenhum dos dois sistemas.
6. Resultado impresso como JSON na última linha (mesmo formato do force-sync).

## Out of scope
Descobrir os pares automaticamente; lote/CSV; reabertura posterior.
