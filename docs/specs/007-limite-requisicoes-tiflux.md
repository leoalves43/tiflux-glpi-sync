# 007 — Respeitar o limite de requisições da API do Tiflux

## Intent
A API do Tiflux aceita 120 requisições por minuto por usuário e responde
429 (`error_code 42901`) quando esse limite é passado. Em 07/10, às 12:48,
um restart do container gerou 17 respostas 429 em 4 s, e essas leituras de
respostas se perderam naquela execução. A integração não olha esse limite.

## User outcome
A sincronização não perde chamadas por excesso de requisições: quando a cota
do minuto está acabando, ela espera a virada do minuto e segue; se ainda
assim receber 429, espera e tenta de novo, em vez de registrar falha.

## Constraints
- A cota é compartilhada com qualquer outro uso do mesmo token, então vale o
  que a API informa (`RateLimit-Remaining`, `RateLimit-Reset`), não uma
  contagem só do nosso lado.
- Vale para toda chamada ao Tiflux (leitura e escrita).
- A espera nunca passa de 65 s por vez (um minuto da janela mais folga).
- Sem mudança de schema; nada muda no GLPI.

## Acceptance criteria
1. Resposta com `RateLimit-Remaining` igual ou abaixo de uma reserva
   (padrão 5) -> a próxima chamada espera até `RateLimit-Reset`.
2. Resposta 429 -> espera até `RateLimit-Reset` (ou 60 s, se o cabeçalho
   faltar ou vier inválido) e repete a mesma chamada, até 2 vezes.
3. Depois de 2 repetições ainda em 429 -> devolve a resposta 429 para o
   código que chamou, que trata como trata hoje (log + nova tentativa na
   próxima execução).
4. Cada espera é logada uma vez, com o motivo e quantos segundos.
5. Respostas sem os cabeçalhos de limite não geram espera.
6. Reserva configurável por variável de ambiente.

## Out of scope
Limite do GLPI; diminuir o número de chamadas por execução.
