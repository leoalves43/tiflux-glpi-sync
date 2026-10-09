# tiflux-glpi-sync

Integração entre o **GLPI** da Prefeitura de Caraguatatuba e o **Tiflux** da
EMBRAS: chamados, respostas e status são espelhados nos dois sistemas, com
auditoria em Postgres. Antes de mexer no código, leia `docs/INDEX.md` e
`docs/ARCHITECTURE.md`.

## Sumário

- [O que a integração faz](#o-que-a-integração-faz)
- [Configuração](#configuração)
- [Banco de dados](#banco-de-dados)
- [Rodando com Docker](#rodando-com-docker)
- [Rodando sem Docker](#rodando-sem-docker)
- [Comandos manuais](#comandos-manuais)
- [Operação: como resolver situações comuns](#operação-como-resolver-situações-comuns)
- [Testes](#testes)
- [Documentação](#documentação)

## O que a integração faz

Cada execução (no Docker, 2 minutos depois do fim da anterior) tem três etapas.

### 1. Chamado aberto no GLPI vira ticket no Tiflux

- Sonda os IDs novos do GLPI e só considera chamados com um dos grupos
  observadores EMBRAS (EMBRAS - Backlog ou EMBRAS - Atendimentos).
- **Mesa** pela categoria do GLPI:

  | Categorias GLPI | Mesa Tiflux |
  |---|---|
  | 233, 267–271 | ADMINISTRATIVO/RH |
  | 272–276 | ARRECADAÇÃO |
  | 277–281 | FINANÇAS |
  | 282–286 | SUPRIMENTOS |

  Categoria fora da tabela fica como erro para revisão manual.
- **Prioridade** fixa por mesa ("Solicitar um Atendimento"). A prioridade do
  GLPI e o texto de SLA correspondente vão no topo da descrição.
- **Solicitante** achado (ou cadastrado) no Tiflux pelo e-mail do requerente,
  com o telefone do campo "Telefone / Linhas" do chamado.
- **Técnico** no Tiflux: Léo Alves só na mesa ARRECADAÇÃO; nas demais, sem técnico.
- Campo obrigatório "Módulo utilizado" sempre "Padrão". Anexos do chamado vão junto.
- Título no Tiflux: `<titulo> (<id_glpi>)`. Título no GLPI ganha `#<numero_tiflux> - `.
- No GLPI, o técnico atribuído passa a ser Suporte Embras (exigência do GLPI
  para encerrar depois) e o chamado fica **Pendente**.
- Proteções contra duplicata: se já existe no Tiflux um ticket com
  `(<id_glpi>)` no título, ele é vinculado em vez de criar outro; e chamado
  cujo título já começa com `#<numero> - ` nunca gera ticket novo.

### 2. Ticket aberto no Tiflux vira chamado no GLPI

Ligado só com `ABERTURA_TIFLUX_DESDE` preenchido; considera apenas tickets
abertos a partir dessa data, numa das 4 mesas do contrato. Tickets de outras
mesas (INFRAESTRUTURA etc.) e tickets que já têm par não são abertos.

| Campo no GLPI | Valor |
|---|---|
| Título | `#<numero_tiflux> - <titulo>` |
| Entidade | STII |
| Categoria | ADMINISTRATIVO/RH 267 · ARRECADAÇÃO 272 · FINANÇAS 277 · SUPRIMENTOS 282 |
| Origem da requisição | STI |
| Localização | STI Área Técnica |
| Prioridade | Média |
| Requerente | usuário do GLPI com o e-mail do solicitante; se não houver, Suporte Embras |
| Observador | grupo Embras - Atendimentos |
| Técnico | Suporte Embras |
| Telefone (plugin) | telefone do solicitante no Tiflux; se vazio, `1238971100` |
| Descrição | `Solicitante: nome <e-mail>` + descrição do Tiflux |
| Anexos | arquivos do ticket (o servidor do GLPI recusa arquivos acima de ~2 MB) |
| Status | Pendente |

Depois de criado, o ticket no Tiflux ganha ` (<id_glpi>)` no título e passa a
ser sincronizado como qualquer outro (etapa 3). O requerente recebe o e-mail
de chamado novo do GLPI.

### 3. Respostas e status dos chamados já vinculados

- **Respostas nos dois sentidos**, só as públicas:
  - acompanhamento público do GLPI vira resposta no Tiflux, com o nome do
    autor; anexos vão junto (até 10 por resposta; o excedente vai para o ticket);
  - resposta pública do Tiflux vira acompanhamento no GLPI, com o nome de quem
    respondeu e a data, e o chamado fica Pendente.
  - Comentários privados e comunicações internas não cruzam.
  Acompanhamentos escritos no GLPI pela conta Suporte Embras não vão para o
  Tiflux: é a conta da própria integração (evita eco).
- **Encerramento em cascata:** ticket fechado ou cancelado no Tiflux deixa o
  chamado **Solucionado** no GLPI, com a última resposta pública do técnico
  como solução.
- **Reabertura em cascata:** ticket reaberto no Tiflux reabre o chamado no
  GLPI como **Pendente**.
- **Solução recusada no GLPI:** se o requerente recusa a solução de um chamado
  que a integração encerrou, o ticket é reaberto no Tiflux com o mesmo
  responsável de antes.
- **Economia de requisições:** o Tiflux limita 120 requisições por minuto. Cada
  execução lê duas listagens (tickets abertos e tickets alterados desde a
  última execução) e só consulta individualmente os tickets que mudaram; uma
  execução sem novidades faz cerca de 5 requisições. Uma varredura completa
  lenta confere todos os chamados ao longo do dia como rede de segurança. Se a
  cota do minuto acaba, a integração espera a virada em vez de falhar.

O estado fica em duas tabelas Postgres (uma linha por chamado, uma por
resposta/evento), que também evitam o eco entre as direções.

## Configuração

Copie `exemplo.env` para `.env` na raiz e preencha:

| Chave | Obrigatória | Descrição |
|---|---|---|
| `URL_GLPI` | sim | URL da API REST do GLPI (`.../apirest.php`) |
| `APP_TOKEN`, `USER_TOKEN` | sim | tokens da API do GLPI |
| `URL_TIFLUX` | sim | `https://api.tiflux.com/api/v2` |
| `TOKEN_TIFLUX` | sim | token da API do Tiflux |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | sim | Postgres da auditoria |
| `DB_SCHEMA` | não | schema das tabelas (padrão `public`) |
| `DB_TABLE`, `DB_TABLE_FOLLOWUPS` | não | nomes das tabelas (padrão `api_glpi_tiflux` e `api_glpi_tiflux_followups`) |
| `ABERTURA_TIFLUX_DESDE` | não | data/hora UTC ISO 8601 (ex.: `2026-10-09T17:25:00Z`); vazio desliga a abertura Tiflux -> GLPI |
| `RESERVA_REQUISICOES_TIFLUX` | não | com a cota do minuto nesse valor ou abaixo, espera a virada (padrão 5) |
| `MARGEM_CHECKPOINT_TIFLUX_MINUTOS` | não | minutos que a listagem de alterados volta antes da última execução (padrão 5) |
| `VARREDURA_COMPLETA_POR_EXECUCAO` | não | chamados conferidos por completo por execução (padrão 1) |

O `.env` nunca é commitado nem entra na imagem Docker. Variáveis de ambiente
sobrescrevem o `.env`, então o mesmo arquivo serve com e sem Docker.

IDs fixos de negócio (ID mínimo da sondagem, grupos observadores, técnicos,
mesas, prioridades, campos do Tiflux) ficam em `sync/config.py`,
`sync/regras_negocio.py` e `sync/regras_abertura_glpi.py`.

## Banco de dados

Crie as tabelas antes da primeira execução (ajuste o schema no arquivo):

```bash
psql -f criar_tabela_auditoria.sql
```

- `api_glpi_tiflux`: uma linha por chamado do GLPI vinculado, nas duas
  direções de criação. Só `status='sucesso'` é vínculo confiável.
- `api_glpi_tiflux_followups`: uma linha por resposta sincronizada e por
  evento (cascata, varredura, checkpoint, abertura Tiflux -> GLPI), chave
  única `(direcao, id_origem)`. Referência das colunas e valores:
  `docs/data/audit_tables.toon`.

Ao migrar um banco existente, use `pg_dump` (estrutura + dados). A gravação
depende das constraints únicas `id_glpi` e `(direcao, id_origem)`; se elas se
perderam, rode `scripts/restaurar_constraints_auditoria.sql`.

**Nunca rode a sincronização com as tabelas vazias num ambiente que já
sincronizava:** a sondagem recomeçaria do início e duplicaria chamados.

## Rodando com Docker

Requisitos: Docker com Compose (Docker Desktop no Windows), acesso de rede ao
Postgres, ao GLPI e ao Tiflux.

```bash
docker compose up -d --build     # builda e sobe; reinicia sozinho
docker compose logs -f           # acompanha os logs (horário de Brasília)
docker compose stop              # para, esperando a execução em andamento terminar
docker compose down              # para e remove o container
```

- O container roda uma sincronização, espera `INTERVALO_SEGUNDOS` (padrão 120,
  no `docker-compose.yml`) e repete. Execuções nunca se sobrepõem, e um `stop`
  espera até 10 minutos a execução em andamento acabar.
- Depois de alterar o código, rode `docker compose up -d --build` de novo.
- O `.env` é montado no container. Em `DB_HOST` não use `localhost` (dentro do
  container é o próprio container); para um Postgres na própria máquina, use
  `host.docker.internal`.
- Para voltar sozinho após reiniciar a máquina, ative *Start Docker Desktop
  when you sign in* no Docker Desktop.

**Antecipar a próxima execução** sem reiniciar o container (PowerShell; não faz
nada se já houver uma execução em andamento):

```powershell
.\scripts\forcar_sincronizacao.ps1
```

### O que aparece no log

| Linha | Significado |
|---|---|
| `✅ Chamado #N: Ticket #M criado no Tiflux ...` | chamado do GLPI criado no Tiflux |
| `🆕 N ticket(s) do Tiflux para abrir no GLPI` / `✅ Ticket Tiflux #M aberto no GLPI como chamado #N` | abertura Tiflux -> GLPI |
| `🔁 N chamado(s) com encerramento/reabertura recente no Tiflux` | cascata desta execução |
| `Followups. GLPI->Tiflux: ... \| Tiflux->GLPI: ... \| Encerramento/reabertura ...` | placar de respostas e cascatas |
| `📡 Requisições ao Tiflux: N (criação X + followups Y)` | uso da cota do Tiflux |
| `⏳ ...` | cota do Tiflux esgotada, esperando a virada do minuto |
| `↩️ Chamado #N ... reconferido por completo na próxima execução` | falha pontual, retentada sozinha |
| `⚠️ Abertura no GLPI com resultado desconhecido` | precisa de revisão manual (ver Operação) |

## Rodando sem Docker

Requisitos: Python 3.10+ e acesso de rede ao Postgres, ao GLPI e ao Tiflux.

```bash
pip install -r requirements.txt
python glpi_tiflux.py            # uma execução, depois termina
```

Para repetir, agende `glpi_tiflux.py` (Agendador de Tarefas, cron) sem permitir
execuções sobrepostas. `run_glpi_tiflux.bat` roda uma execução e acrescenta a
saída em `logs\glpi_tiflux.log`.

**Não rode sem Docker enquanto o container estiver ligado contra o mesmo
banco:** duas sincronizações simultâneas duplicam chamados e respostas. Para
uma execução manual, pare o container antes (`docker compose stop`).

## Comandos manuais

Com Docker, prefixe com `docker compose run --rm sync`. Sem Docker, rode direto
na raiz do projeto.

### Forçar um chamado do GLPI que ficou fora da sondagem

Cria no Tiflux (ou vincula, se já houver ticket com `(<id_glpi>)` no título) e
sincroniza as respostas. Nunca recria um chamado que já tem ticket no Tiflux.
A interface web lê a última linha da saída como JSON
(`{"status", "numero_tiflux", "mensagem"}`).

```bash
python -m sync.forcar_sincronizacao --id-glpi 33769
```

Pode rodar com o container ligado, mas evite usar num chamado que o container
esteja processando no mesmo minuto.

### Abrir no GLPI um ticket do Tiflux

Mesmo caminho e mesmas proteções da etapa 2. Sem `--aplicar` só lê e mostra se
o ticket é candidato e o que seria enviado ao GLPI; com `--aplicar`, abre.
Exige `ABERTURA_TIFLUX_DESDE` preenchido.

```bash
python -m sync.abrir_ticket_tiflux_no_glpi --numero-tiflux 364990
python -m sync.abrir_ticket_tiflux_no_glpi --numero-tiflux 364990 --aplicar
```

### Encerrar no GLPI um chamado atendido por ticket aberto à mão no Tiflux

Para chamados anteriores à integração. O ticket precisa estar fechado no
Tiflux e o chamado aberto no GLPI; senão o comando recusa sem mudar nada.
Atribui técnico, registra a última resposta pública do técnico como solução e
marca Solucionado. Não copia histórico nem vincula o chamado. Irreversível pela
API: confira os títulos impressos no resultado. Pode rodar com o container ligado.

```bash
python -m sync.encerrar_legado --id-glpi 33545 --numero-tiflux 361210
```

### Passar para Pendente os chamados que ficaram Novo

Uso único, já aplicado em 09/10/2026. Sem `--aplicar` só lista.

```bash
python -m sync.pendente_retroativo
python -m sync.pendente_retroativo --aplicar
```

## Operação: como resolver situações comuns

**Vincular um ticket aberto à mão no Tiflux a um chamado do GLPI.**

- Chamado recente (dentro da sondagem): coloque `(<id_glpi>)` no fim do título
  do ticket no Tiflux. A próxima execução vincula e sincroniza tudo, inclusive
  o histórico.
- Chamado antigo (abaixo de `id_minimo_glpi`): insira o vínculo na auditoria; o
  histórico inteiro é sincronizado na sequência:

  ```sql
  INSERT INTO <schema>.api_glpi_tiflux (id_glpi, numero_tiflux, status, mensagem)
  VALUES (29197, 350369, 'sucesso', 'Vínculo manual: ticket aberto à mão no Tiflux')
  ON CONFLICT (id_glpi) DO NOTHING;
  ```

  Para sincronizar só daqui para frente, antes do vínculo grave em
  `api_glpi_tiflux_followups` uma linha `status='sucesso'` por resposta pública
  já existente: `direcao='glpi_para_tiflux'` com o id do acompanhamento do
  GLPI, e `direcao='tiflux_para_glpi'` com o id da resposta do Tiflux, ambas com
  `tipo='publica'` e `id_destino` nulo.

**Abertura Tiflux -> GLPI com resultado desconhecido.** Se a criação no GLPI
cai no meio (timeout, erro 5xx), a linha
`direcao='abertura_tiflux', id_origem=<numero_tiflux>` em
`api_glpi_tiflux_followups` fica `pendente` e a integração não tenta de novo,
para não duplicar. Procure no GLPI um chamado `#<numero_tiflux> - ...`:

- existe: grave o vínculo em `api_glpi_tiflux` (como acima) e mude a linha
  para `status='sucesso'` com `id_destino=<id_glpi>`;
- não existe: apague a linha; a próxima execução tenta de novo.

Linhas `erro` são retentadas sozinhas; `ignorado` é definitivo.

**Chamado com título `#<numero> - ` sem ticket no Tiflux** aparece como erro
na criação GLPI -> Tiflux: é um par provável sem auditoria. Confira no Tiflux e
vincule à mão.

**Anexo que não chegou ao GLPI.** O log mostra o arquivo e o motivo. Acima de
~2 MB o servidor do GLPI recusa (`Arquivo ... não encontrado`); a correção é
aumentar `upload_max_filesize` e `post_max_size` no PHP do GLPI.

## Testes

```bash
python -m unittest discover -s tests -t .
docker compose run --rm --no-deps sync python -m unittest discover -s tests -t .   # no Python do container
```

Os testes usam fakes para GLPI, Tiflux e Postgres; nenhum acessa a rede.

## Documentação

`docs/INDEX.md` lista o que existe e quando ler: arquitetura, decisões
(`docs/decisions/LOG.md`), estado atual (`docs/state/HANDOFF.md`) e as specs e
planos de cada mudança (`docs/specs/`, `docs/plans/`).
