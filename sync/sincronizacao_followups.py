"""Orquestra a sincronização de followups: escolhe os chamados e aplica cascata + publicação em cada um."""

from sync import db_followups
from sync.cascata_status import (
    STATUS_GLPI_ABERTOS,
    encerrar_em_cascata,
    equalizar_reabertura_manual_do_tiflux,
    id_responsavel_tiflux,
    reabrir_tiflux_apos_recusa_glpi,
    recusa_glpi_pendente,
    restaurar_responsavel_apos_reabertura,
    tratar_chamado_fechado_no_glpi,
)
from sync.config import Config, log
from sync.glpi_client import GlpiClient
from sync.panorama_tiflux import PanoramaTiflux
from sync.placar_followups import PlacarFollowups
from sync.publicacao_followups import sincronizar_followups_glpi_para_tiflux, sincronizar_followups_tiflux_para_glpi
from sync.tiflux_client import TifluxClient
from sync.tipos import ConexaoDb, NumeroTiflux


def sincronizar_followups(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, panorama: PanoramaTiflux,
) -> None:
    """
    Percorre os chamados com encerramento/reabertura recente no Tiflux
    (panorama.mudancas) mais os do rodízio (obter_chamados_para_varrer_followups:
    todos os abertos/solucionados no GLPI + um lote de fechados). Fechados no
    GLPI só passam pela cascata (cascata_status); os abertos sincronizam
    followups nos dois sentidos (publicacao_followups) e depois a cascata.
    Ex.: sincronizar_followups(conn, config, glpi, tiflux, ler_panorama_tiflux(conn, config, tiflux, agora))
    """
    mudancas = list(panorama.mudancas)
    if mudancas:
        log(f"🔁 {len(mudancas)} chamado(s) com encerramento/reabertura recente no Tiflux: {[m[0] for m in mudancas]}")
    chamados = _juntar_sem_repetir(mudancas, db_followups.obter_chamados_para_varrer_followups(conn, config))
    if not chamados:
        return

    placar = PlacarFollowups()
    for id_glpi, numero_tiflux in chamados:
        if numero_tiflux:
            _sincronizar_chamado(conn, config, glpi, tiflux, id_glpi, numero_tiflux, placar)

    log(placar.resumo())


def _juntar_sem_repetir(primeiros: list[tuple[int, int]], demais: list[tuple[int, int]]) -> list[tuple[int, int]]:
    # Um chamado nas duas listas rodaria duas vezes na mesma execução.
    ja_incluidos = {id_glpi for id_glpi, _ in primeiros}
    return primeiros + [par for par in demais if par[0] not in ja_incluidos]


def _sincronizar_chamado(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, placar: PlacarFollowups,
) -> None:
    ticket_glpi, status_code = glpi.obter_ticket(id_glpi)
    if ticket_glpi is None:
        log(f"⚠️ Não foi possível conferir status do chamado #{id_glpi} no GLPI "
            f"(status {status_code}) — pulado nesta execução")
        return

    ticket_tiflux, _ = tiflux.obter_ticket(numero_tiflux)

    if ticket_glpi.get("status") not in STATUS_GLPI_ABERTOS:
        tratar_chamado_fechado_no_glpi(conn, config, glpi, id_glpi, numero_tiflux, ticket_glpi, ticket_tiflux, placar)
        return
    _sincronizar_chamado_aberto_no_glpi(conn, config, glpi, tiflux, id_glpi, numero_tiflux, ticket_tiflux, placar)


def _sincronizar_chamado_aberto_no_glpi(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, ticket_tiflux: dict | None, placar: PlacarFollowups,
) -> None:
    if recusa_glpi_pendente(conn, config, id_glpi, ticket_tiflux):
        reabriu, ticket_tiflux = _reabrir_tiflux_mantendo_responsavel(
            conn, config, tiflux, id_glpi, numero_tiflux, ticket_tiflux, placar,
        )
        if not reabriu:
            # Tiflux segue fechado: publicar followups daria 422 e o
            # encerramento em cascata desfaria a recusa (GLPI #34759, spec
            # 004). Deixa o GLPI aberto e retenta na próxima execução.
            db_followups.registrar_chamado_aberto_varrido(conn, config, id_glpi, numero_tiflux)
            return

    _sincronizar_followups_nos_dois_sentidos(conn, config, glpi, tiflux, id_glpi, numero_tiflux, placar)
    db_followups.registrar_chamado_aberto_varrido(conn, config, id_glpi, numero_tiflux)

    if ticket_tiflux and ticket_tiflux.get("is_closed"):
        encerrar_em_cascata(conn, config, glpi, tiflux, id_glpi, numero_tiflux, ticket_tiflux, placar)
    elif ticket_tiflux:
        equalizar_reabertura_manual_do_tiflux(conn, config, id_glpi, numero_tiflux)


def _reabrir_tiflux_mantendo_responsavel(
    conn: ConexaoDb, config: Config, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, ticket_fechado: dict | None, placar: PlacarFollowups,
) -> tuple[bool, dict | None]:
    """(reabriu, ticket_atualizado). O responsável é lido do ticket ainda fechado (spec 006)."""
    if not reabrir_tiflux_apos_recusa_glpi(conn, config, tiflux, id_glpi, numero_tiflux, placar):
        return False, ticket_fechado
    ticket_reaberto, _ = tiflux.obter_ticket(numero_tiflux)
    restaurar_responsavel_apos_reabertura(
        tiflux, id_glpi, numero_tiflux, id_responsavel_tiflux(ticket_fechado), ticket_reaberto,
    )
    return True, ticket_reaberto


def _sincronizar_followups_nos_dois_sentidos(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, placar: PlacarFollowups,
) -> None:
    placar.somar_glpi_para_tiflux(*sincronizar_followups_glpi_para_tiflux(conn, config, glpi, tiflux, id_glpi, numero_tiflux))
    placar.somar_tiflux_para_glpi(*sincronizar_followups_tiflux_para_glpi(conn, config, glpi, tiflux, id_glpi, numero_tiflux))
