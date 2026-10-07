"""Orquestra a sincronização de followups: escolhe os chamados e aplica cascata + publicação em cada um."""

from sync import db_followups
from sync.cascata_status import (
    STATUS_GLPI_ABERTOS,
    STATUS_GLPI_SOLUCIONADO,
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
    prioritarios = mudancas + list(panorama.varredura_completa)
    chamados = _juntar_sem_repetir(prioritarios, db_followups.obter_chamados_para_varrer_followups(conn, config))
    if not chamados:
        return

    placar = PlacarFollowups()
    for id_glpi, numero_tiflux in chamados:
        if numero_tiflux:
            _sincronizar_chamado(conn, config, glpi, tiflux, id_glpi, numero_tiflux, placar, panorama)

    log(placar.resumo())


def _juntar_sem_repetir(primeiros: list[tuple[int, int]], demais: list[tuple[int, int]]) -> list[tuple[int, int]]:
    # Um chamado em mais de uma lista rodaria duas vezes na mesma execução.
    ja_incluidos: set[int] = set()
    juntos = []
    for par in primeiros + demais:
        if par[0] not in ja_incluidos:
            ja_incluidos.add(par[0])
            juntos.append(par)
    return juntos


def _sincronizar_chamado(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, placar: PlacarFollowups, panorama: PanoramaTiflux,
) -> None:
    falhas_antes = _falhas_tiflux_para_glpi(placar, tiflux)
    conferido = _conferir_chamado(conn, config, glpi, tiflux, id_glpi, numero_tiflux, placar, panorama)
    if id_glpi in _ids_glpi(panorama.varredura_completa):
        # Marca mesmo se o GLPI falhou: um chamado com 404 permanente
        # ficaria pra sempre no topo da fila e travaria a varredura.
        db_followups.registrar_varredura_completa(conn, config, id_glpi, numero_tiflux)
    falhas_depois = _falhas_tiflux_para_glpi(placar, tiflux)
    motivo = _motivo_para_retentar(id_glpi, numero_tiflux, panorama, conferido, falhas_antes, falhas_depois)
    if motivo:
        log(f"↩️ Chamado #{id_glpi} (Tiflux #{numero_tiflux}): {motivo} — reconferido por completo na próxima execução")
        db_followups.priorizar_varredura_completa(conn, config, id_glpi, numero_tiflux, motivo)


def _conferir_chamado(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, placar: PlacarFollowups, panorama: PanoramaTiflux,
) -> bool:
    """False se o chamado não pôde ser lido no GLPI (pulado nesta execução)."""
    ticket_glpi, status_code = glpi.obter_ticket(id_glpi)
    if ticket_glpi is None:
        log(f"⚠️ Não foi possível conferir status do chamado #{id_glpi} no GLPI "
            f"(status {status_code}) — pulado nesta execução")
        return False
    if conferir_por_completo(id_glpi, numero_tiflux, ticket_glpi, panorama):
        _sincronizar_chamado_completo(conn, config, glpi, tiflux, id_glpi, numero_tiflux, ticket_glpi, placar)
    else:
        _sincronizar_chamado_pelo_panorama(conn, config, glpi, tiflux, id_glpi, numero_tiflux, ticket_glpi, placar, panorama)
    return True


def _falhas_tiflux_para_glpi(placar: PlacarFollowups, tiflux: TifluxClient) -> tuple[int, int]:
    return placar.tiflux_para_glpi_erro, tiflux.listagens_com_falha


def _motivo_para_retentar(
    id_glpi: int, numero_tiflux: NumeroTiflux, panorama: PanoramaTiflux, conferido: bool,
    falhas_antes: tuple[int, int], falhas_depois: tuple[int, int],
) -> str | None:
    """
    Por que o chamado precisa ser reconferido na próxima execução, ou None.
    O checkpoint avança mesmo assim; sem isso, uma resposta do Tiflux que
    falhou só voltaria na varredura de segurança, horas depois (spec 008).
    """
    if falhas_depois != falhas_antes:
        return "falha ao trazer respostas do Tiflux para o GLPI"
    mudou_no_tiflux = numero_tiflux in panorama.atualizados or id_glpi in _ids_glpi(panorama.mudancas)
    if not conferido and mudou_no_tiflux:
        return "atualizado no Tiflux, mas ilegível no GLPI"
    return None


def conferir_por_completo(
    id_glpi: int, numero_tiflux: NumeroTiflux, ticket_glpi: dict, panorama: PanoramaTiflux,
) -> bool:
    """
    True quando o chamado precisa da leitura individual no Tiflux (spec 008):
    mudança de status recente, varredura de segurança, ou GLPI e lista de
    abertos do Tiflux em desacordo — aberto no GLPI e fora da lista (fechado,
    cancelado ou recusa pendente) ou Solucionado no GLPI e aberto no Tiflux
    (reabertura). Nenhuma escrita sai do panorama sem essa leitura (crit. 6).
    Ex.: conferir_por_completo(34759, 364160, {"status": 2}, panorama_sem_o_364160) -> True
    """
    if id_glpi in _ids_glpi(panorama.mudancas) or id_glpi in _ids_glpi(panorama.varredura_completa):
        return True
    status = ticket_glpi.get("status")
    if status in STATUS_GLPI_ABERTOS:
        return numero_tiflux not in panorama.abertos
    return status == STATUS_GLPI_SOLUCIONADO and numero_tiflux in panorama.abertos


def _ids_glpi(pares: tuple[tuple[int, NumeroTiflux], ...]) -> set[int]:
    return {id_glpi for id_glpi, _ in pares}


def _sincronizar_chamado_pelo_panorama(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, ticket_glpi: dict, placar: PlacarFollowups, panorama: PanoramaTiflux,
) -> None:
    """
    Mesmo efeito do caminho completo quando GLPI e Tiflux concordam, sem o
    GET individual: fechado nos dois só ganha a marca de varredura; aberto nos
    dois sincroniza followups — os do Tiflux só se o ticket foi atualizado
    desde o checkpoint (uma resposta nova muda o updated_at).
    """
    status = ticket_glpi.get("status")
    if status not in STATUS_GLPI_ABERTOS:
        db_followups.registrar_chamado_fechado_para_followups(conn, config, id_glpi, status == STATUS_GLPI_SOLUCIONADO)
        return
    placar.somar_glpi_para_tiflux(*sincronizar_followups_glpi_para_tiflux(conn, config, glpi, tiflux, id_glpi, numero_tiflux))
    if numero_tiflux in panorama.atualizados:
        placar.somar_tiflux_para_glpi(*sincronizar_followups_tiflux_para_glpi(conn, config, glpi, tiflux, id_glpi, numero_tiflux))
    db_followups.registrar_chamado_aberto_varrido(conn, config, id_glpi, numero_tiflux)
    equalizar_reabertura_manual_do_tiflux(conn, config, id_glpi, numero_tiflux)


def _sincronizar_chamado_completo(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int,
    numero_tiflux: NumeroTiflux, ticket_glpi: dict, placar: PlacarFollowups,
) -> None:
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
