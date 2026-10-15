# 013 — Validação do GLPI aparece no Tiflux

## Intent
No GLPI, o pedido de validação de um chamado e a resposta (aprovado/recusado)
não são acompanhamentos, então hoje não chegam ao Tiflux (ex.: GLPI #35092 ->
Tiflux #365227, GLPI #35140 -> Tiflux #365366). O técnico no Tiflux não sabe
que o chamado aguarda aprovação nem o que foi decidido.

## User outcome
Em chamado GLPI já vinculado a um ticket do Tiflux:
- Quando alguém pede validação, o ticket recebe no ciclo seguinte uma resposta
  "🔐 Validação solicitada a <validador>" + comentário do pedido, se houver.
- Quando o validador responde, o ticket recebe "✅ Validação aprovada por
  <validador>" ou "❌ Validação recusada por <validador>" + comentário da
  resposta, se houver.

## Constraints
- Cada evento (pedido, resposta) é publicado uma única vez por validação,
  inclusive se o chamado for reconferido várias vezes ou a sincronização
  reiniciar. Falha ao publicar é retentada no ciclo seguinte (mesmo padrão dos
  acompanhamentos).
- Várias validações no mesmo chamado (vários validadores ou pedidos
  sucessivos) = um evento por validação.
- Validação pedida e respondida entre dois ciclos: publica os dois eventos,
  pedido primeiro.
- Autor da resposta no Tiflux: quem pediu (no pedido) e o validador (na
  resposta), com o nome real do GLPI, como os acompanhamentos.
- Só no sentido GLPI -> Tiflux. Não muda status, estágio nem responsável em
  nenhum dos dois sistemas.
- Retroativo: validações já existentes em chamados vinculados e ainda abertos
  (ex.: #35092, #35140) são publicadas no primeiro ciclo após o deploy.

## Decisões pendentes (responder antes do plano)
1. Canal no Tiflux: resposta visível como as do GLPI (recomendado, mesmo canal
   dos acompanhamentos) ou comunicação interna (só a equipe Embras vê)?
2. Retroativo: publicar também validações já respondidas antes do deploy, ou
   só as que ainda aguardam resposta?

## Acceptance criteria
1. Pedido de validação num chamado vinculado gera uma resposta 🔐 no ticket do
   Tiflux, com validador e comentário.
2. Aprovação gera uma resposta ✅; recusa gera uma resposta ❌; ambas com
   validador e comentário.
3. Reconferir o chamado sem mudança na validação não publica nada de novo.
4. Duas validações no mesmo chamado geram eventos separados.
5. Falha na publicação fica como erro e é publicada no ciclo seguinte, uma vez.
6. Pedido e resposta no mesmo intervalo: os dois aparecem, pedido antes.
7. Chamado não vinculado ao Tiflux ou fora do escopo: nada publicado.

## Out of scope
- Responder/aprovar a validação pelo Tiflux (Tiflux -> GLPI).
- Validação no momento da criação do ticket: só entra pelo ciclo de
  acompanhamentos, depois de o chamado estar vinculado.
- Anexos da validação.
- Cancelamento ou exclusão de um pedido de validação no GLPI.
