"""Validações do GLPI (TicketValidation) publicadas como resposta pública no Tiflux (spec 013)."""

import html
from dataclasses import dataclass

import requests

from sync import db_followups
from sync.config import Config
from sync.glpi_client import GlpiClient
from sync.tiflux_client import TifluxClient
from sync.tipos import ConexaoDb, NumeroTiflux

# TicketValidation.status no GLPI 10 (2 = aguardando, sem evento de resposta).
_STATUS_APROVADA = 3
_STATUS_RECUSADA = 4

# Duas direções na auditoria: a chave única (direcao, id_origem) com
# id_origem = id da validação dá um registro por evento, não por validação.
DIRECAO_PEDIDO = "validacao_pedido"
DIRECAO_RESPOSTA = "validacao_resposta"


@dataclass(frozen=True)
class EventoValidacao:
    """Uma resposta a publicar no Tiflux: pedido ou resposta de uma validação."""

    direcao: str
    id_validacao: int
    id_autor_glpi: int | None
    conteudo_html: str


def publicar_validacoes_no_tiflux(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_chamado: int,
    numero_tiflux: NumeroTiflux,
) -> tuple[int, int]:
    """
    Publica no Tiflux os pedidos/respostas de validação ainda não publicados
    com sucesso, a partir de config.validacao_glpi_desde_id. Devolve
    (sucessos, erros) pro placar; erro é retentado no ciclo seguinte.
    Ex.: publicar_validacoes_no_tiflux(conn, config, glpi, tiflux, 35092, 365227) -> (1, 0)
    """
    validacoes = _validacoes_a_partir_do_corte(glpi, config, id_chamado)
    if not validacoes:
        return 0, 0
    publicados = {
        direcao: db_followups.obter_ids_origem_com_sucesso(conn, config, id_chamado, direcao)
        for direcao in (DIRECAO_PEDIDO, DIRECAO_RESPOSTA)
    }
    sucessos = erros = 0
    for validacao in validacoes:
        eventos = eventos_pendentes(validacao, publicados, glpi)
        publicou, falhou = _publicar_em_ordem(conn, config, tiflux, glpi, id_chamado, numero_tiflux, eventos)
        sucessos, erros = sucessos + publicou, erros + falhou
    return sucessos, erros


def _publicar_em_ordem(
    conn: ConexaoDb, config: Config, tiflux: TifluxClient, glpi: GlpiClient, id_chamado: int,
    numero_tiflux: NumeroTiflux, eventos: list[EventoValidacao],
) -> tuple[int, int]:
    """Para no primeiro erro: a resposta não sai antes do pedido (spec 013, crit. 6)."""
    for publicados, evento in enumerate(eventos):
        if not _publicar_evento(conn, config, tiflux, glpi, id_chamado, numero_tiflux, evento):
            return publicados, 1
    return len(eventos), 0


def _validacoes_a_partir_do_corte(glpi: GlpiClient, config: Config, id_chamado: int) -> list[dict]:
    if not config.validacao_glpi_desde_id:
        return []
    validacoes = [
        v for v in glpi.obter_validacoes(id_chamado)
        if int(v.get("id") or 0) >= config.validacao_glpi_desde_id
    ]
    return sorted(validacoes, key=lambda v: int(v["id"]))


def eventos_pendentes(validacao: dict, publicados: dict[str, set[int]], glpi: GlpiClient) -> list[EventoValidacao]:
    """
    Pedido (sempre) e resposta (se aprovada/recusada) desta validação que
    ainda não constam como publicados, pedido primeiro.
    Ex.: eventos_pendentes({"id": 1474, "status": 2, ...}, {"validacao_pedido": set(), ...}, glpi) -> [pedido 1474]
    """
    id_validacao = int(validacao["id"])
    falta_pedido = id_validacao not in publicados[DIRECAO_PEDIDO]
    respondida = validacao.get("status") in (_STATUS_APROVADA, _STATUS_RECUSADA)
    falta_resposta = respondida and id_validacao not in publicados[DIRECAO_RESPOSTA]
    if not (falta_pedido or falta_resposta):
        return []  # sem GET do nome: o caso comum a cada ciclo
    validador = glpi.obter_nome_usuario(validacao.get("users_id_validate"))
    eventos = [_evento_pedido(validacao, id_validacao, validador)] if falta_pedido else []
    if falta_resposta:
        eventos.append(_evento_resposta(validacao, id_validacao, validador))
    return eventos


def _evento_pedido(validacao: dict, id_validacao: int, validador: str) -> EventoValidacao:
    titulo = f"🔐 Validação solicitada a {html.escape(validador)}"
    conteudo = _paragrafo_com_comentario(titulo, validacao.get("comment_submission"))
    return EventoValidacao(DIRECAO_PEDIDO, id_validacao, validacao.get("users_id"), conteudo)


def _evento_resposta(validacao: dict, id_validacao: int, validador: str) -> EventoValidacao:
    aprovada = validacao.get("status") == _STATUS_APROVADA
    decisao = "✅ Validação aprovada" if aprovada else "❌ Validação recusada"
    titulo = f"{decisao} por {html.escape(validador)}"
    conteudo = _paragrafo_com_comentario(titulo, validacao.get("comment_validation"))
    return EventoValidacao(DIRECAO_RESPOSTA, id_validacao, validacao.get("users_id_validate"), conteudo)


def _paragrafo_com_comentario(titulo: str, comentario: str | None) -> str:
    # Comentário vem HTML-entity-encoded como os followups ("&#60;p&#62;...").
    return f"<p><strong>{titulo}</strong></p>{html.unescape(comentario or '')}"


def _publicar_evento(
    conn: ConexaoDb, config: Config, tiflux: TifluxClient, glpi: GlpiClient, id_chamado: int,
    numero_tiflux: NumeroTiflux, evento: EventoValidacao,
) -> bool:
    nome_autor = glpi.obter_nome_usuario(evento.id_autor_glpi)
    resp = tiflux.publicar_resposta_cliente(numero_tiflux, evento.conteudo_html, nome_autor)
    id_destino, mensagem = _interpretar_publicacao(resp, evento)
    status = "sucesso" if id_destino else "erro"
    db_followups.registrar_resultado_followup(
        conn, config, id_chamado, numero_tiflux, evento.direcao, "publica", evento.id_validacao,
        id_destino, status, mensagem,
    )
    return status == "sucesso"


def _interpretar_publicacao(resp: requests.Response, evento: EventoValidacao) -> tuple[int | None, str]:
    """(id da resposta no Tiflux ou None, mensagem da auditoria)."""
    rotulo = f"Validação GLPI #{evento.id_validacao} ({evento.direcao})"
    if resp.status_code not in (200, 201):
        return None, f"Falha ao publicar {rotulo} no Tiflux ({resp.status_code}): {resp.text}"
    id_destino = resp.json().get("id")
    if not id_destino:
        return None, f"{rotulo} publicada no Tiflux, mas sem id na resposta: {resp.text}"
    return id_destino, f"{rotulo} publicada no Tiflux (id {id_destino})"
