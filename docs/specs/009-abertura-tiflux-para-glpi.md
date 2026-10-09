# 009 — Chamado aberto no Tiflux é registrado no GLPI

## Intent
Hoje só o GLPI abre chamado no Tiflux. Chamado aberto direto no Tiflux (pela
equipe ou por e-mail) não existe no GLPI, então a prefeitura não o vê. A
integração deve criar o chamado correspondente no GLPI e, a partir daí,
tratá-lo como qualquer chamado sincronizado.

## User outcome
Chamado novo no Tiflux, numa das 4 mesas do contrato, aparece no GLPI na
execução seguinte, já vinculado: respostas, encerramento e reabertura passam a
ser sincronizados como nos chamados abertos pelo GLPI.

## Regras de preenchimento no GLPI
- Entidade: sempre PMC.
- Categoria pela mesa do Tiflux (de-para inverso):
  | Mesa Tiflux | Categoria GLPI |
  |---|---|
  | 37963 ADMINISTRATIVO/RH | 267 |
  | 37964 ARRECADAÇÃO | 272 |
  | 37965 FINANÇAS | 277 |
  | 37966 SUPRIMENTOS | 282 |
- Origem da requisição: sempre STI (6).
- Localização: sempre STI Área Técnica (1685).
- Telefone (plugin Fields "Telefone / Linhas"): o telefone do solicitante no
  Tiflux; vazio no Tiflux -> `1238971100` (só dígitos, como os dados existentes).
- Requerente: usuário do GLPI com o mesmo e-mail do solicitante do Tiflux; sem
  correspondência -> SUPORTE EMBRAS (4988).
- Observador: sempre o grupo Embras - Atendimentos (22).
- Técnico atribuído: sempre 4988.
- Prioridade: sempre Média (3).
- Status: não reflete o estágio do Tiflux. Após criar, o chamado no GLPI fica
  sempre Pendente (4) — vale também para o caminho GLPI -> Tiflux, que hoje
  volta para Novo (1). Reabertura em cascata (Tiflux reaberto) também deixa o
  GLPI Pendente, em vez de "Processando (atribuído)" (2).
- Chamados já sincronizados e abertos que hoje estão Novo no GLPI passam para
  Pendente, uma vez, na entrada em produção.
- Título no GLPI: sempre `#<numero_tiflux> - <titulo_tiflux>`.
- Título no Tiflux: depois de criar no GLPI, recebe o número do chamado como
  no caminho atual: `<titulo> (<id_glpi>)`.
- Ticket já encerrado no Tiflux quando a integração o encontra: cria no GLPI
  mesmo assim; a cascata existente o leva a Solucionado.
- Demais campos e passos seguem a mesma regra do caminho GLPI -> Tiflux:
  descrição, anexos, auditoria.

## Constraints
- Chamado de qualquer outra mesa (ex.: INFRAESTRUTURA) não é sincronizado.
- Nunca criar no GLPI um chamado que já tem par: ticket criado pela própria
  integração a partir do GLPI, ou aberto à mão para um chamado GLPI existente
  (título `"<titulo> (<id_glpi>)"`), não gera chamado novo — senão vira laço.
- Só tickets abertos no Tiflux depois que a funcionalidade entrar em produção;
  os antigos abertos à mão (spec 002) ficam de fora.
- Mesma proteção contra duplicata do caminho atual: na dúvida se o par já
  existe, registra erro em vez de criar.
- Respeita o limite de requisições do Tiflux (specs 007/008): descobrir
  tickets novos não pode voltar a consultar ticket por ticket a cada execução.

## Acceptance criteria
1. Ticket novo no Tiflux na mesa ARRECADAÇÃO -> na execução seguinte existe
   um chamado no GLPI com entidade PMC, categoria 272, origem 6, localização
   1685, observador grupo 22, técnico 4988, título `#<numero_tiflux> -
   <titulo>`, prioridade 3, status Pendente, e o vínculo registrado na auditoria.
2. Solicitante com e-mail cadastrado no GLPI vira o requerente; e-mail sem
   correspondência -> requerente 4988.
3. Telefone preenchido no Tiflux vai para o campo do plugin; vazio -> valor
   padrão.
4. Ticket numa mesa fora das 4 não gera chamado no GLPI.
5. Ticket criado pela integração a partir do GLPI nunca gera um segundo
   chamado no GLPI (sem laço), mesmo após várias execuções.
6. Ticket aberto no Tiflux antes da entrada em produção não gera chamado.
7. Depois de criado, resposta no Tiflux chega ao GLPI e acompanhamento no
   GLPI chega ao Tiflux; encerrar no Tiflux deixa o GLPI Solucionado.
8. Falha ao criar no GLPI é registrada como erro e tentada de novo sem gerar
   duplicata.
9. Ticket aberto e encerrado no Tiflux entre duas execuções -> chamado
   criado no GLPI e levado a Solucionado pela cascata.
10. Título do ticket no Tiflux termina com ` (<id_glpi>)` após a criação.
11. Chamado aberto no GLPI e criado no Tiflux pela integração fica Pendente
   no GLPI (antes ficava Novo).
12. Ticket reaberto no Tiflux -> chamado no GLPI reaberto como Pendente.
13. Após a entrada em produção, nenhum chamado sincronizado e aberto fica
   Novo no GLPI; os que estavam em outro status aberto não são alterados.
14. Execução sem ticket novo continua dentro da meta da spec 008 (≤ 5
   requisições ao Tiflux).

## Out of scope
Mesas além das 4 do contrato; importar tickets antigos; mudar o caminho
GLPI -> Tiflux além do status pós-criação e pós-reabertura; mudar o de-para GLPI -> Tiflux
existente.
