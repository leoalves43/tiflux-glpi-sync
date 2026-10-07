# 005 — Refatoração sem mudança de comportamento

## Intent
O código cresceu por correções pontuais: `sincronizacao_followups.py` está no
limite de 500 linhas com três responsabilidades, o teste correspondente passou
do limite, há funções de 25–35 linhas, parâmetros sem tipo e contadores em
dict com chave montada por string. Deixar o código mais fácil de manter sem
mudar nada do que a integração faz.

## User outcome
Nenhuma diferença observável: mesmos chamados criados, mesmos followups,
mesma cascata, mesmas linhas de auditoria, mesmo log.

## Constraints
- Mesma sequência de chamadas ao banco e às APIs (os fakes dependem da ordem).
- Literais de auditoria intocados: `direcao`, `tipo`, `status`, sentinela
  `-id_glpi`, chaves de conflito.
- Asserções dos testes não mudam; só imports e arquivo onde estão.
- Sintaxe compatível com Python 3.13 (imagem do container).
- Bug conhecido de `status='erro'` em `processar_chamado` fica como está.

## Acceptance criteria
1. Os 280 testes passam, sem asserção alterada.
2. Todo arquivo em `sync/` e `tests/` com menos de 500 linhas.
3. Nenhuma função nova ou alterada com mais de 20 linhas de código (SQL
   literal não conta).
4. Parâmetros e retornos com tipo em `sync/`.
5. Container reconstruído roda 2 ciclos sem Traceback, com o mesmo formato de
   log (o aviso 403 do #34759 continua, esperado).

## Out of scope
Qualquer mudança funcional, de schema, de configuração ou de intervalo.
