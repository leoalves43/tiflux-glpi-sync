# tiflux-glpi-sync

Sincronização automática de chamados entre **GLPI** e **Tiflux**, com
auditoria em Postgres. Antes de mexer na lógica, leia `docs/ARCHITECTURE.md`.

## O que a sincronização faz

A cada execução (no Docker, a cada 5 minutos):

1. **Criação de chamados, GLPI -> Tiflux.** Sonda os chamados novos do GLPI
   (só os que têm um dos grupos observadores EMBRAS) e cria o equivalente no
   Tiflux: mesa pela categoria, prioridade, técnico, solicitante, anexos e
   campos obrigatórios. O título no GLPI ganha o prefixo `#<numero_tiflux> - `.
2. **Vínculo com ticket já aberto à mão.** Se já existe no Tiflux um ticket com
   `(<id_glpi>)` no título, ele é vinculado em vez de criar um duplicado.
3. **Telefone do solicitante.** O telefone do campo "Telefone / Linhas" do
   chamado GLPI é gravado no solicitante do Tiflux (exigido por algumas mesas).
4. **Followups nos dois sentidos**, para chamados vinculados e abertos: os
   followups públicos do GLPI viram respostas no Tiflux, e as respostas públicas
   do Tiflux viram followups no GLPI, com o nome de quem respondeu. Comentários
   privados e comunicações internas não cruzam.
5. **Encerramento e reabertura em cascata.** Ticket fechado no Tiflux -> chamado
   Solucionado no GLPI, com a última resposta pública do técnico como solução.
   Ticket reaberto no Tiflux -> chamado reaberto no GLPI. Solução recusada no
   GLPI -> ticket reaberto no Tiflux.

O estado fica em duas tabelas Postgres (uma por chamado, uma por followup),
que também evitam o eco entre as duas direções.

## Configuração

Copie `exemplo.env` para `.env` na raiz do projeto e preencha:

```
URL_GLPI=https://.../apirest.php
APP_TOKEN=
USER_TOKEN=

URL_TIFLUX=https://api.tiflux.com/api/v2
TOKEN_TIFLUX=

DB_HOST=
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_SCHEMA=
DB_TABLE=api_glpi_tiflux
```

O `.env` nunca é commitado nem entra na imagem Docker. Variáveis de ambiente
sobrescrevem o `.env`, então o mesmo arquivo serve com e sem Docker.

Parâmetros de negócio (ID mínimo da sondagem, grupos observadores, IDs de
técnico/campo/mesa, tamanho do lote de followups) ficam em
`sync/config.py:Config`.

## Banco de dados

Crie as tabelas de auditoria antes da primeira execução:

```bash
psql -f criar_tabela_auditoria.sql
```

Ao migrar um banco existente, use `pg_dump` (estrutura + dados). A gravação
depende das constraints únicas `id_glpi` e `(direcao, id_origem)`; se elas se
perderam, rode `scripts/restaurar_constraints_auditoria.sql` (ajuste o schema
se não for `tiflux_glpi_sync`).

Nunca rode a sincronização com as tabelas **vazias** em um ambiente que já
sincronizava: a sondagem recomeçaria do início e duplicaria chamados.

## Rodando com Docker

Requisitos: Docker com Compose (Docker Desktop no Windows), Postgres acessível
a partir do container e acesso de rede ao GLPI e ao Tiflux.

```bash
docker compose up -d --build     # builda e sobe; reinicia sozinho
docker compose logs -f           # acompanha os logs (horário de America/Sao_Paulo)
docker compose stop              # para, esperando a execução em andamento terminar
docker compose down              # para e remove o container
```

O container roda a sincronização, espera `INTERVALO_SEGUNDOS` (padrão 300,
no `docker-compose.yml`) e repete. Uma execução nunca começa antes da anterior
terminar, e um `stop` espera até 10 minutos para a execução em andamento
acabar. Depois de alterar o código, rode `up -d --build` de novo.

O container usa o `DB_HOST` do `.env` (Postgres em servidor remoto). Não use
`localhost` ali: dentro do container, `localhost` é o próprio container. Para
um Postgres na própria máquina, use `DB_HOST=host.docker.internal`.

Para o container voltar sozinho após reiniciar a máquina, ative *Start Docker
Desktop when you sign in* no Docker Desktop.

Antecipar a próxima execução sem reiniciar o container (Windows/PowerShell;
não faz nada se já houver uma execução em andamento):

```powershell
.\scripts\forcar_sincronizacao.ps1
```

## Comandos manuais

Com Docker, prefixe com `docker compose run --rm sync`. Sem Docker, rode direto.

**Forçar um chamado que ficou fora da sondagem.** Cria no Tiflux (ou vincula,
se já houver ticket com `(<id_glpi>)` no título) e sincroniza os followups.
Nunca recria um chamado que já tem ticket no Tiflux:

```bash
python -m sync.forcar_sincronizacao --id-glpi 33769
```

**Encerrar no GLPI um chamado atendido por ticket aberto à mão no Tiflux**
antes da integração. O ticket precisa estar fechado no Tiflux e o chamado
aberto no GLPI; senão o comando recusa sem mudar nada. Atribui técnico,
registra a última resposta pública do técnico como solução e marca
Solucionado. Não copia histórico e não vincula o chamado, que não volta a ser
acompanhado. Irreversível pela API: confira os títulos impressos no resultado.

```bash
python -m sync.encerrar_legado --id-glpi 33545 --numero-tiflux 361210
```

**Vincular um ticket aberto à mão para continuar sincronizando.**

- Chamado novo (dentro da sondagem): coloque `(<id_glpi>)` no fim do título do
  ticket no Tiflux. A próxima execução vincula e sincroniza tudo, inclusive o
  histórico.
- Chamado antigo (abaixo de `id_minimo_glpi`): insira o vínculo na auditoria.
  O histórico inteiro é sincronizado na sequência:

  ```sql
  INSERT INTO <schema>.api_glpi_tiflux (id_glpi, numero_tiflux, status, mensagem)
  VALUES (29197, 350369, 'sucesso', 'Vínculo manual: ticket aberto à mão no Tiflux')
  ON CONFLICT (id_glpi) DO NOTHING;
  ```

  Para sincronizar só daqui para frente, antes do vínculo grave em
  `api_glpi_tiflux_followups` uma linha `status='sucesso'` por followup público
  já existente: `direcao='glpi_para_tiflux'` com o id do followup GLPI, e
  `direcao='tiflux_para_glpi'` com o id da resposta Tiflux, ambas com
  `tipo='publica'` e `id_destino` nulo.

## Testes

```bash
python -m unittest discover -s tests -t .
docker compose run --rm --no-deps sync python -m unittest discover -s tests -t .   # no ambiente de produção
```

## Rodando sem Docker

Requisitos: Python 3.10+, Postgres e acesso de rede ao GLPI e ao Tiflux. No
`.env`, use o host real do banco.

```bash
pip install -r requirements.txt
python glpi_tiflux.py            # uma execução
```

`glpi_tiflux.py` roda uma vez e termina. Para repetir, agende-o (Agendador de
Tarefas do Windows, cron) sem permitir execuções sobrepostas.

**Não rode sem Docker enquanto o container estiver ligado contra o mesmo
banco.** Duas sincronizações simultâneas duplicam chamados e followups no
Tiflux. `encerrar_legado` pode rodar com o container ligado;
`forcar_sincronizacao` também, mas evite usá-lo num chamado que o container
esteja processando no mesmo minuto (o lock dele não bloqueia o container).
