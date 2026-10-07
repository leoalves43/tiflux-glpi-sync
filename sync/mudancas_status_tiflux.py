"""Encerramentos/reaberturas recentes no Tiflux ainda não espelhados no GLPI.

O rodízio de followups (db_followups.obter_chamados_para_varrer_followups)
confere só uma leva de chamados por execução, então um encerramento no Tiflux
levava várias execuções pra chegar no GLPI. Aqui a listagem dos tickets
atualizados (panorama_tiflux) aponta quais chamados mudaram de status, pra
entrarem já na execução atual.
"""

from sync import db_followups
from sync.config import Config
from sync.tipos import ConexaoDb

_ACAO_ENCERRAMENTO = "encerramento"


def cruzar_mudancas_de_status(conn: ConexaoDb, config: Config, tickets: list[dict]) -> list[tuple[int, int]]:
    """
    Pares (id_glpi, numero_tiflux) cujo status no Tiflux (`tickets`, da
    listagem de atualizados do panorama_tiflux) diverge da última ação de
    cascata registrada. Só lê — quem encerra/reabre é o fluxo normal de
    sincronizacao_followups + cascata_status.
    Ex.: cruzar_mudancas_de_status(conn, config, [{"ticket_number": 9, "is_closed": True}]) -> [(1, 9)]
    """
    if not tickets:
        return []
    numeros = [t["ticket_number"] for t in tickets if t.get("ticket_number") is not None]
    chamados = db_followups.obter_chamados_por_numero_tiflux(conn, config, numeros)
    return selecionar_mudancas_de_status(tickets, chamados)


def selecionar_mudancas_de_status(
    tickets: list[dict], chamados: dict[int, tuple[int, str | None]],
) -> list[tuple[int, int]]:
    """
    Fechado no Tiflux sem encerramento em cascata registrado -> encerrar no GLPI.
    Aberto no Tiflux com encerramento registrado -> reabrir no GLPI.
    Tickets sem chamado sincronizado (abertos direto no Tiflux) ficam de fora.
    Ex.: selecionar_mudancas_de_status([{"ticket_number": 9, "is_closed": True}], {9: (1, None)}) -> [(1, 9)]
    """
    selecionados = []
    for ticket in tickets:
        chamado = chamados.get(ticket.get("ticket_number"))
        if chamado is None:
            continue
        id_glpi, ultima_acao = chamado
        if _status_divergente(bool(ticket.get("is_closed")), ultima_acao):
            selecionados.append((id_glpi, ticket["ticket_number"]))
    return selecionados


def _status_divergente(fechado_no_tiflux: bool, ultima_acao: str | None) -> bool:
    # Fechado de novo depois de uma reabertura também diverge: última ação
    # 'reabertura'/'reabertura_tiflux' != 'encerramento'.
    if fechado_no_tiflux:
        return ultima_acao != _ACAO_ENCERRAMENTO
    return ultima_acao == _ACAO_ENCERRAMENTO
