"""Postgres — idempotência da abertura Tiflux -> GLPI (spec 009).

Uma linha por ticket do Tiflux na tabela de followups (direcao='abertura_tiflux',
id_origem=numero_tiflux; a chave (direcao, id_origem) já existente impede
duplicata). Ciclo: 'pendente' antes do POST no GLPI -> 'sucesso' (id_destino =
id_glpi), 'erro' (recusa clara do GLPI ou ticket ilegível, retentável) ou
'ignorado' (deixou de ser candidato; encerra as retentativas). 'pendente'
que sobra de uma execução anterior = resultado desconhecido: não recria, pede revisão manual.
Toda consulta da tabela filtra por direcao, então essas linhas não interferem
no rodízio nem na cascata.
"""

from sync import db_followups
from sync.config import Config
from sync.tipos import ConexaoDb

DIRECAO_ABERTURA_TIFLUX = "abertura_tiflux"
STATUS_ABERTURA_PENDENTE = "pendente"
STATUS_ABERTURA_SUCESSO = "sucesso"
STATUS_ABERTURA_ERRO = "erro"
STATUS_ABERTURA_IGNORADO = "ignorado"


def obter_estados_abertura(conn: ConexaoDb, config: Config) -> dict[int, str]:
    """
    numero_tiflux -> status ('pendente', 'sucesso', 'erro' ou 'ignorado') de cada abertura já tentada.
    Ex.: obter_estados_abertura(conn, config) -> {364990: 'sucesso', 364991: 'erro'}
    """
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id_origem, status FROM {config.tabela_followups} WHERE direcao = %s",
            (DIRECAO_ABERTURA_TIFLUX,),
        )
        return {numero: status for numero, status in cur.fetchall()}


def obter_numeros_tiflux_na_auditoria(conn: ConexaoDb, config: Config) -> set[int]:
    """
    Todo numero_tiflux da auditoria de chamados, com QUALQUER status: linhas
    'erro' do bug de duplicação também têm número e o ticket existe (ARCHITECTURE).
    Ex.: obter_numeros_tiflux_na_auditoria(conn, config) -> {364569, 364678}
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT numero_tiflux FROM {config.tabela_auditoria} WHERE numero_tiflux IS NOT NULL")
        return {int(row[0]) for row in cur.fetchall()}


def registrar_intencao_abertura(conn: ConexaoDb, config: Config, numero_tiflux: int) -> None:
    """Grava 'pendente' ANTES do POST no GLPI. Ex.: registrar_intencao_abertura(conn, config, 364990)"""
    _registrar(conn, config, numero_tiflux, 0, None, STATUS_ABERTURA_PENDENTE,
               "Abrindo chamado no GLPI — se ficar assim, o resultado é desconhecido: revisar manualmente")


def registrar_abertura_sucesso(conn: ConexaoDb, config: Config, numero_tiflux: int, id_glpi: int) -> None:
    """Ex.: registrar_abertura_sucesso(conn, config, 364990, 35001)"""
    _registrar(conn, config, numero_tiflux, id_glpi, id_glpi, STATUS_ABERTURA_SUCESSO,
               f"Ticket Tiflux #{numero_tiflux} aberto no GLPI como chamado #{id_glpi}")


def registrar_abertura_erro(conn: ConexaoDb, config: Config, numero_tiflux: int, mensagem: str) -> None:
    """Só quando nada foi criado (recusa clara do GLPI, ticket ilegível): a próxima execução tenta de novo."""
    _registrar(conn, config, numero_tiflux, 0, None, STATUS_ABERTURA_ERRO, mensagem)


def registrar_abertura_ignorada(conn: ConexaoDb, config: Config, numero_tiflux: int) -> None:
    """Terminal: sem isso um 'erro' que deixou de ser candidato custaria um GET por execução para sempre."""
    _registrar(conn, config, numero_tiflux, 0, None, STATUS_ABERTURA_IGNORADO,
               "Deixou de ser candidato à abertura no GLPI (mesa, título ou data) — não será retentado")


def _registrar(
    conn: ConexaoDb, config: Config, numero_tiflux: int, id_glpi: int, id_destino: int | None, status: str,
    mensagem: str,
) -> None:
    db_followups.registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, DIRECAO_ABERTURA_TIFLUX, "abertura", numero_tiflux, id_destino,
        status, mensagem,
    )
