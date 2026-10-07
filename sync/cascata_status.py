"""Encerramento/reabertura em cascata entre Tiflux e GLPI, e reabertura do Tiflux após recusa no GLPI."""

import html

from sync import db_followups
from sync.config import Config, log
from sync.glpi_client import GlpiClient
from sync.placar_followups import PlacarFollowups
from sync.publicacao_followups import prefixar_autor_tiflux, resposta_criada_pela_integracao
from sync.regras_negocio import definir_autor_glpi
from sync.tiflux_client import TifluxClient


# Status de chamado no GLPI considerados "aberto" (Novo/Processando/Pendente)
STATUS_GLPI_ABERTOS = (1, 2, 3, 4)


# Status pra onde o chamado GLPI vai quando o ticket correspondente é
# fechado ou cancelado no Tiflux (encerramento em cascata)
STATUS_GLPI_SOLUCIONADO = 5


# Status pra onde o chamado GLPI volta quando um encerramento em cascata
# anterior é desfeito porque o ticket foi reaberto no Tiflux
STATUS_GLPI_REABERTO = 2  # Processando (atribuído)


def recusa_glpi_pendente(conn, config, id_glpi, ticket_tiflux: dict | None) -> bool:
    """
    Chamado tinha sido encerrado em cascata (Tiflux fechado -> GLPI
    Solucionado) e voltou a ficar aberto no GLPI (recusa da solução pelo
    requerente, ou reabertura manual) sem que o Tiflux tenha sido reaberto —
    essa integração não escuta esse evento no GLPI, então o caller reabre o
    Tiflux pra equalizar. Sem isso, o followup da própria recusa nunca seria
    publicado no Tiflux (422 "Cannot add answer in a closed ticket") e o
    encerramento em cascata forçaria o GLPI de volta pra Solucionado.
    Ex.: recusa_glpi_pendente(conn, config, 34759, {"is_closed": True}) -> True
    """
    if not ticket_tiflux or not ticket_tiflux.get("is_closed"):
        return False
    return db_followups.obter_ultima_acao_cascata_sucesso(conn, config, id_glpi) == "encerramento"


def reabrir_tiflux_apos_recusa_glpi(conn, config, tiflux: TifluxClient, id_glpi, numero_tiflux, placar: PlacarFollowups) -> bool:
    """
    Reabre o ticket no Tiflux (ver TifluxClient.reabrir_ticket). Toda
    tentativa grava a linha própria (direcao='glpi_para_tiflux',
    tipo='reabertura_tiflux', id_origem=-id_glpi); só o sucesso grava a linha
    de cascata. Na falha a cascata segue 'encerramento'/'sucesso', então a
    próxima execução retenta — antes, a falha sobrescrevia essa linha e o
    erro sumia (GLPI #34018, #34187, #34759; spec 004). O followup da recusa
    é publicado pelo caller logo em seguida, como qualquer followup pendente.
    Ex.: reabrir_tiflux_apos_recusa_glpi(conn, config, tiflux, 34759, 364160, placar) -> False em 403
    """
    motivo = f"Solução recusada pelo requerente no GLPI (chamado #{id_glpi})"
    sucesso, erro = tiflux.reabrir_ticket(numero_tiflux, motivo)
    mensagem = (
        f"Chamado #{id_glpi} reaberto no GLPI (provável recusa da solução) — "
        f"ticket Tiflux #{numero_tiflux} reaberto para equalizar"
        if sucesso else erro
    )
    status = "sucesso" if sucesso else "erro"
    db_followups.registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, "glpi_para_tiflux", "reabertura_tiflux", -id_glpi, None, status, mensagem,
    )
    placar.contar_cascata(sucesso)
    if not sucesso:
        log(f"⚠️ Chamado #{id_glpi} reaberto no GLPI, mas o ticket Tiflux #{numero_tiflux} não reabriu "
            f"— reabra manualmente no Tiflux. {erro}")
        return False
    db_followups.registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, "tiflux_para_glpi", "reabertura_tiflux", -id_glpi, None, status, mensagem,
    )
    return True


def equalizar_reabertura_manual_do_tiflux(conn, config, id_glpi, numero_tiflux) -> None:
    """
    GLPI aberto + Tiflux aberto, mas a última cascata ainda diz
    'encerramento': o Tiflux foi reaberto fora da integração (ex.: à mão,
    depois de um 403 na reabertura automática — spec 004). Registra a
    reabertura pra que um fechamento posterior do técnico encerre o GLPI
    em cascata em vez de reabrir o Tiflux de novo.
    Ex.: equalizar_reabertura_manual_do_tiflux(conn, config, 34759, 364160)
    """
    if db_followups.obter_ultima_acao_cascata_sucesso(conn, config, id_glpi) != "encerramento":
        return
    db_followups.registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, "tiflux_para_glpi", "reabertura_tiflux", -id_glpi, None, "sucesso",
        f"Ticket Tiflux #{numero_tiflux} reaberto fora da integração com o chamado #{id_glpi} aberto no GLPI — estado equalizado",
    )


def tratar_chamado_fechado_no_glpi(conn, config, glpi, id_glpi, numero_tiflux, ticket_glpi, ticket_tiflux, placar: PlacarFollowups) -> None:
    """
    Chamado já não está mais "aberto" no GLPI. Normalmente é porque um
    encerramento em cascata anterior já rodou (status Solucionado) — nesse
    caso, se o ticket foi REABERTO no Tiflux nesse meio tempo, desfaz o
    encerramento (volta pra Processando) pra followups voltarem a sincronizar
    na próxima execução. Fechamentos manuais no GLPI (ex.: status Fechado,
    feito por um técnico direto lá) não são mexidos — só reabrimos o que a
    própria integração fechou.
    """
    reabrir = (
        ticket_glpi.get("status") == STATUS_GLPI_SOLUCIONADO
        and ticket_tiflux is not None
        and not ticket_tiflux.get("is_closed")
    )
    if reabrir:
        _mudar_status_em_cascata(
            conn, config, glpi, id_glpi, numero_tiflux, STATUS_GLPI_REABERTO, "reabertura",
            f"Chamado #{id_glpi} reaberto no GLPI (status Processando) — reaberto no Tiflux #{numero_tiflux}",
            placar,
        )
        return

    solucionado = ticket_glpi.get("status") == STATUS_GLPI_SOLUCIONADO
    db_followups.registrar_chamado_fechado_para_followups(conn, config, id_glpi, solucionado)


_SEM_RESPOSTA_TIFLUX = "Chamado encerrado no Tiflux, sem resposta pública registrada."


def encerrar_em_cascata(conn, config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi, numero_tiflux, ticket_tiflux: dict, placar: PlacarFollowups) -> None:
    """
    Essa instalação do GLPI recusa (com HTTP 200 mas message não-vazia, ver
    GlpiClient._atualizar_chamado) mudar o status pra Solucionado sem técnico
    atribuído E sem uma solução registrada — confirmado ao vivo. Garante os
    dois antes de tentar. Se qualquer um dos dois falhar aqui, a tentativa de
    status abaixo também vai falhar (GLPI recusa) e ser retentada na próxima
    execução, quando os dois são tentados de novo — idempotente via
    tecnico_atribuido()/solucao_registrada(), não duplica em retries.
    """
    if glpi.tecnico_atribuido(id_glpi) is None:
        glpi.atribuir_tecnico(id_glpi, definir_autor_glpi(config))

    if not glpi.solucao_registrada(id_glpi):
        conteudo_solucao = _ultima_resposta_publica_tiflux(tiflux, numero_tiflux, config, ticket_tiflux)
        glpi.registrar_solucao(id_glpi, conteudo_solucao)

    _mudar_status_em_cascata(
        conn, config, glpi, id_glpi, numero_tiflux, STATUS_GLPI_SOLUCIONADO, "encerramento",
        f"Chamado #{id_glpi} encerrado no GLPI (status Solucionado) — fechado/cancelado no Tiflux #{numero_tiflux}",
        placar,
    )


def _mensagem_encerramento_sem_resposta(ticket_tiflux: dict) -> str:
    """
    Ticket fechado no Tiflux sem nenhuma resposta pública própria — normalmente
    porque foi AGRUPADO em outro ticket (is_grouped=True), caso em que a
    resposta de verdade está no ticket "pai" (ticket_reference), não neste.
    Confirmado ao vivo no chamado GLPI #34294 / ticket Tiflux #362749: agrupado
    ao #362748, sem resposta própria, mas fechado igual — o texto genérico
    "sem resposta pública registrada" mascarava esse motivo e o fazia parecer
    um chamado abandonado sem retorno.
    """
    if not ticket_tiflux.get("is_grouped"):
        return _SEM_RESPOSTA_TIFLUX
    numero_pai = (ticket_tiflux.get("ticket_reference") or {}).get("ticket_number")
    if numero_pai:
        return f"Chamado encerrado no Tiflux por agrupamento ao ticket #{numero_pai}."
    return "Chamado encerrado no Tiflux por agrupamento a outro ticket."


def _ultima_resposta_publica_tiflux(tiflux: TifluxClient, numero_tiflux: str, config: Config, ticket_tiflux: dict) -> str:
    """
    A resposta pública (/answers) mais recente escrita por um técnico no
    Tiflux, por answer_time, vira o conteúdo da solução no GLPI (prefixada
    com autor+data, mesmo padrão dos followups). Respostas criadas pela
    própria integração (followups vindos do GLPI) ficam de fora — GLPI #34522
    fechou com o followup do Marcio como solução em vez da resposta do técnico.
    """
    todas = tiflux.listar_respostas(numero_tiflux, config.tamanho_pagina_respostas_tiflux, config.max_paginas_respostas_tiflux)
    respostas = [r for r in todas if not resposta_criada_pela_integracao(r)]
    if not respostas:
        return _mensagem_encerramento_sem_resposta(ticket_tiflux)
    mais_recente = max(respostas, key=lambda r: r.get("answer_time") or "")
    conteudo = html.unescape(mais_recente.get("name") or "") or _mensagem_encerramento_sem_resposta(ticket_tiflux)
    return prefixar_autor_tiflux(mais_recente.get("author"), mais_recente.get("answer_time"), conteudo)


def _mudar_status_em_cascata(conn, config, glpi: GlpiClient, id_glpi, numero_tiflux, novo_status: int, tipo: str, mensagem_sucesso: str, placar: PlacarFollowups) -> None:
    """
    Aplica uma mudança de status no GLPI espelhando o estado do ticket no
    Tiflux (encerramento ou reabertura). Sem bookkeeping de "já processado":
    se falhar, a condição que disparou a chamada (is_closed no Tiflux
    divergindo do status no GLPI) continua valendo e é retentada na próxima
    execução; se der certo, o status do GLPI muda e a condição deixa de valer.
    Uma única linha por chamado na tabela de auditoria (direcao=
    'tiflux_para_glpi', id_origem=-id_glpi) guarda a última ação de cascata,
    seja ela encerramento ou reabertura.
    """
    sucesso, erro = glpi.encerrar_chamado(id_glpi, novo_status)
    mensagem = mensagem_sucesso if sucesso else erro
    db_followups.registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, "tiflux_para_glpi", tipo, -id_glpi, None,
        "sucesso" if sucesso else "erro", mensagem,
    )
    placar.contar_cascata(sucesso)
