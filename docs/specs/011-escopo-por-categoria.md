# 011 — Escopo da sondagem pela categoria, não pelo grupo observador

## Intent
A triagem às vezes demora para pôr o grupo observador EMBRAS no chamado, e o
chamado só ia ao Tiflux depois disso. O escopo GLPI -> Tiflux passa a ser só a
categoria: as do de-para GLPI -> Tiflux (233, 267–286, 348).

## User outcome
Chamado do GLPI numa categoria do de-para vai ao Tiflux no ciclo seguinte, com
ou sem grupo observador. Ao atribuir o técnico Suporte Embras, a integração
também põe o grupo Embras - Atendimentos (22) como observador.

## Constraints
- Categoria fora do de-para (ou vazia) = fora do escopo ('ignorado', não
  gravado, reconferido enquanto estiver na faixa da sondagem) — antes era
  'erro' quando o chamado tinha o grupo.
- Grupo 22 já observador não é duplicado. Falha ao pôr o grupo só avisa (mesmo
  padrão do técnico): reprocessar duplicaria o ticket no Tiflux.
- Vale também para o comando manual forcar_sincronizacao.
- Na entrada em produção (09/10/2026) nenhum chamado da faixa da sondagem
  entra no escopo de uma vez: os 22 ainda não sincronizados (#34991–#35021)
  não têm categoria do de-para.

## Acceptance criteria
1. Chamado numa categoria do de-para e sem grupo observador é criado no Tiflux.
2. Chamado sem categoria do de-para é 'ignorado', mesmo com o grupo 21/22.
3. Após criar no Tiflux, o chamado no GLPI tem o grupo 22 como observador
   (uma vez só) e o técnico 4988.
4. Falha ao pôr o grupo aparece como aviso; o chamado fica 'sucesso'.

## Out of scope
Abertura Tiflux -> GLPI (já põe o grupo 22 no POST); mudar o de-para.
