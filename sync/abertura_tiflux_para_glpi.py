"""Abertura Tiflux -> GLPI (spec 009): ticket novo no Tiflux vira chamado no GLPI.

Ordem que evita duplicata e laço (ver docs/plans/009):
intenção 'pendente' -> POST /Ticket -> auditoria de chamados 'sucesso' na hora
(o caminho GLPI -> Tiflux passa a ignorar o chamado) -> intenção 'sucesso' ->
passos que só avisam se falharem (título no Tiflux, telefone, anexos, Pendente).
"""

from collections.abc import Collection

from sync import db_abertura_tiflux, db_chamados
from sync.anexos_tiflux_para_glpi import copiar_anexos_tiflux_para_glpi
from sync.config import Config, log
from sync.glpi_abertura_client import GlpiAberturaClient
from sync.glpi_client import GlpiClient
from sync.panorama_tiflux import PanoramaTiflux
from sync.regras_abertura_glpi import (
    campos_chamado_glpi,
    telefone_para_glpi,
    ticket_candidato_a_abertura,
    titulo_tiflux_com_id_glpi,
)
from sync.regras_negocio import definir_autor_glpi
from sync.tiflux_client import TifluxClient
from sync.tipos import ConexaoDb


def abrir_chamados_do_tiflux(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, panorama: PanoramaTiflux,
) -> None:
    """
    Abre no GLPI os tickets novos do panorama e retenta as aberturas com erro.
    Desligada sem ABERTURA_TIFLUX_DESDE.
    Ex.: abrir_chamados_do_tiflux(conn, config, glpi, tiflux, panorama)
    """
    if config.abertura_tiflux_desde is None:
        return
    estados = db_abertura_tiflux.obter_estados_abertura(conn, config)
    _avisar_resultados_desconhecidos(estados)
    vinculados = numeros_ja_vinculados(conn, config, estados)
    numeros = _numeros_para_abrir(config, panorama, estados, vinculados)
    if not numeros:
        return
    log(f"🆕 {len(numeros)} ticket(s) do Tiflux para abrir no GLPI: {numeros}")
    glpi_abertura = glpi.cliente_abertura()
    for numero in numeros:
        abrir_ticket_no_glpi(conn, config, glpi_abertura, glpi, tiflux, numero, vinculados)


def abrir_ticket_no_glpi(
    conn: ConexaoDb, config: Config, glpi_abertura: GlpiAberturaClient, glpi: GlpiClient, tiflux: TifluxClient,
    numero_tiflux: int, vinculados: Collection[int],
) -> int | None:
    """
    Abre um ticket no GLPI; devolve o id criado, ou None (já logado). Nunca
    levanta: um ticket com problema não para os demais nem a execução.
    Ex.: abrir_ticket_no_glpi(conn, config, glpi.cliente_abertura(), glpi, tiflux, 364990, set()) -> 35001
    """
    try:
        return _abrir(conn, config, glpi_abertura, glpi, tiflux, numero_tiflux, vinculados)
    except Exception as e:
        log(f"❌ Ticket Tiflux #{numero_tiflux}: erro inesperado ao abrir no GLPI ({e}) — "
            f"confira a linha 'abertura_tiflux' antes de retentar")
        return None


def _abrir(
    conn: ConexaoDb, config: Config, glpi_abertura: GlpiAberturaClient, glpi: GlpiClient, tiflux: TifluxClient,
    numero_tiflux: int, vinculados: Collection[int],
) -> int | None:
    # Leitura individual antes de escrever (spec 008): a listagem só aponta
    # candidatos e não traz a descrição.
    ticket, status_http = tiflux.obter_ticket(numero_tiflux)
    if ticket is None:
        log(f"⚠️ Ticket Tiflux #{numero_tiflux}: não foi possível ler (status {status_http}) — tenta na próxima execução")
        return None
    if not ticket_candidato_a_abertura(ticket, config.abertura_tiflux_desde, vinculados):
        log(f"ℹ️ Ticket Tiflux #{numero_tiflux}: não é mais candidato à abertura no GLPI — ignorado")
        return None
    id_glpi = _criar_no_glpi(conn, config, glpi_abertura, ticket, numero_tiflux)
    if id_glpi is not None:
        avisos = _completar_abertura(config, glpi_abertura, glpi, tiflux, ticket, id_glpi)
        log(f"✅ Ticket Tiflux #{numero_tiflux} aberto no GLPI como chamado #{id_glpi}{avisos}")
    return id_glpi


def _criar_no_glpi(
    conn: ConexaoDb, config: Config, glpi_abertura: GlpiAberturaClient, ticket: dict, numero_tiflux: int,
) -> int | None:
    email = (ticket.get("requestor") or {}).get("email")
    id_requerente = glpi_abertura.buscar_usuario_por_email(email) or definir_autor_glpi(config)
    campos = campos_chamado_glpi(ticket, id_requerente, definir_autor_glpi(config))
    db_abertura_tiflux.registrar_intencao_abertura(conn, config, numero_tiflux)
    resultado = glpi_abertura.criar_chamado(campos)
    if resultado.id_glpi is None:
        _registrar_falha_criacao(conn, config, numero_tiflux, resultado.erro, resultado.incerto)
        return None
    db_chamados.registrar_resultado(
        conn, config, resultado.id_glpi, numero_tiflux, "sucesso",
        f"Chamado aberto no GLPI a partir do ticket Tiflux #{numero_tiflux} (spec 009)",
    )
    db_abertura_tiflux.registrar_abertura_sucesso(conn, config, numero_tiflux, resultado.id_glpi)
    return resultado.id_glpi


def _registrar_falha_criacao(conn: ConexaoDb, config: Config, numero_tiflux: int, erro: str, incerto: bool) -> None:
    if incerto:
        # Fica 'pendente': o chamado pode existir no GLPI; recriar duplicaria.
        log(f"⚠️ Ticket Tiflux #{numero_tiflux}: resultado desconhecido ao abrir no GLPI ({erro}) — revisar manualmente")
        return
    db_abertura_tiflux.registrar_abertura_erro(conn, config, numero_tiflux, erro)
    log(f"❌ Ticket Tiflux #{numero_tiflux}: {erro} — tenta de novo na próxima execução")


def _completar_abertura(
    config: Config, glpi_abertura: GlpiAberturaClient, glpi: GlpiClient, tiflux: TifluxClient, ticket: dict,
    id_glpi: int,
) -> str:
    """Passos que não desfazem a abertura; devolve os avisos pro log ("" se tudo deu certo)."""
    numero_tiflux = int(ticket["ticket_number"])
    erros = [
        tiflux.renomear_ticket(numero_tiflux, titulo_tiflux_com_id_glpi(ticket.get("title") or "", id_glpi)),
        glpi_abertura.gravar_telefone(id_glpi, telefone_para_glpi((ticket.get("requestor") or {}).get("telephone"))),
        glpi.definir_status_pendente(id_glpi)[1],
    ]
    anexos = copiar_anexos_tiflux_para_glpi(tiflux, glpi_abertura, config, numero_tiflux, id_glpi)
    return anexos + "".join(f" | Aviso: {erro}" for erro in erros if erro)


def _avisar_resultados_desconhecidos(estados: dict[int, str]) -> None:
    pendentes = sorted(n for n, s in estados.items() if s == db_abertura_tiflux.STATUS_ABERTURA_PENDENTE)
    if pendentes:
        log(f"⚠️ Abertura no GLPI com resultado desconhecido (revisar manualmente): tickets Tiflux {pendentes}")


def numeros_ja_vinculados(conn: ConexaoDb, config: Config, estados: dict[int, str]) -> set[int]:
    """
    Na auditoria (qualquer status) ou com abertura pendente/concluída: nunca abrir de novo.
    Ex.: numeros_ja_vinculados(conn, config, {364990: 'erro'}) -> {364569, 364678}
    """
    ja_abertos = {n for n, s in estados.items() if s != db_abertura_tiflux.STATUS_ABERTURA_ERRO}
    return db_abertura_tiflux.obter_numeros_tiflux_na_auditoria(conn, config) | ja_abertos


def _numeros_para_abrir(
    config: Config, panorama: PanoramaTiflux, estados: dict[int, str], vinculados: set[int],
) -> list[int]:
    """Novos do panorama + aberturas com erro (fora da listagem se o ticket já fechou)."""
    novos = {
        int(t["ticket_number"]) for t in panorama.tickets_listados
        if ticket_candidato_a_abertura(t, config.abertura_tiflux_desde, vinculados)
    }
    retentativas = {n for n, s in estados.items() if s == db_abertura_tiflux.STATUS_ABERTURA_ERRO} - vinculados
    return sorted(novos | retentativas)
