"""Regras de negócio de tradução Tiflux -> GLPI na abertura de chamado (spec 009)."""

import html
import re
from collections.abc import Collection
from datetime import datetime

# De-para inverso de regras_negocio.depara_categoria: cada mesa recebe várias
# categorias no GLPI, então o usuário escolheu uma por mesa.
CATEGORIA_GLPI_POR_MESA: dict[int, int] = {
    37963: 267,  # ADMINISTRATIVO/RH
    37964: 272,  # ARRECADAÇÃO
    37965: 277,  # FINANÇAS
    37966: 282,  # SUPRIMENTOS
    38853: 348,  # INFRAESTRUTURA (spec 010)
}

# Campos fixos do chamado no GLPI, definidos pelo usuário na spec 009.
# Entidade STII (1) e não PMC (0): a localização 1685 é da entidade 1 e não
# é recursiva, então só vale num chamado dessa entidade.
ENTIDADE_GLPI_STII = 1
ORIGEM_GLPI_STI = 6
LOCALIZACAO_GLPI_AREA_TECNICA = 1685
GRUPO_GLPI_EMBRAS_ATENDIMENTOS = 22
PRIORIDADE_GLPI_MEDIA = 3
# Mesmo tipo dos chamados já sincronizados (ex.: GLPI #34900); as 4
# categorias aceitam incidente e requisição.
TIPO_GLPI_INCIDENTE = 1
# Só dígitos, mesmo formato dos telefones já gravados no plugin do GLPI.
TELEFONE_GLPI_PADRAO = "1238971100"

# Título de ticket já vinculado a um chamado do GLPI: "<titulo> (<id_glpi>)".
_REGEX_TITULO_COM_ID_GLPI = re.compile(r"\(\d+\)\s*$")


def ticket_candidato_a_abertura(
    ticket_tiflux: dict, abertura_desde: datetime, id_cliente: int, numeros_ja_vinculados: Collection[int],
) -> bool:
    """
    True se o ticket listado no Tiflux deve virar chamado no GLPI: do cliente
    da prefeitura (spec 010), mesa do contrato, aberto a partir do corte, sem
    par conhecido (auditoria ou "(<id_glpi>)" no título — tickets criados pela
    integração têm os dois).
    Ex.: ticket_candidato_a_abertura({"ticket_number": 364990, "client": {"id": 762707}, "desk": {"id": 37964},
         "created_at": "2026-10-10T13:00:00Z", "title": "Erro"}, corte, 762707, set()) -> True
    """
    if (ticket_tiflux.get("client") or {}).get("id") != id_cliente:
        return False
    if (ticket_tiflux.get("desk") or {}).get("id") not in CATEGORIA_GLPI_POR_MESA:
        return False
    if int(ticket_tiflux["ticket_number"]) in numeros_ja_vinculados:
        return False
    if _REGEX_TITULO_COM_ID_GLPI.search(ticket_tiflux.get("title") or ""):
        return False
    criado_em = ticket_tiflux.get("created_at")
    return bool(criado_em) and datetime.fromisoformat(criado_em) >= abertura_desde


def telefone_para_glpi(telefone_tiflux: str | None) -> str:
    """
    Telefone E.164 do solicitante no Tiflux -> só dígitos com DDD, como o
    plugin do GLPI guarda; vazio ou irreconhecível -> TELEFONE_GLPI_PADRAO.
    Ex.: telefone_para_glpi("+551238971108") -> "1238971108"
    """
    digitos = re.sub(r"\D", "", telefone_tiflux or "")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return TELEFONE_GLPI_PADRAO
    return digitos


def titulo_glpi_aberto_pelo_tiflux(numero_tiflux: int, titulo_tiflux: str) -> str:
    """Ex.: titulo_glpi_aberto_pelo_tiflux(364990, "Erro no boleto") -> "#364990 - Erro no boleto" """
    return f"#{numero_tiflux} - {titulo_tiflux.strip()}"


def titulo_tiflux_com_id_glpi(titulo_tiflux: str, id_glpi: int) -> str:
    """Mesmo formato do caminho GLPI -> Tiflux. Ex.: titulo_tiflux_com_id_glpi("Erro", 35001) -> "Erro (35001)" """
    return f"{titulo_tiflux.strip()} ({id_glpi})"


def conteudo_glpi_aberto_pelo_tiflux(requestor: dict | None, descricao_html: str | None) -> str:
    """
    Descrição do chamado no GLPI: quem pediu no Tiflux + a descrição (já
    HTML). A linha do solicitante é o único registro de quem pediu quando o
    e-mail não acha usuário no GLPI e o requerente cai no padrão.
    Ex.: conteudo_glpi_aberto_pelo_tiflux({"name": "Ana", "email": "a@x"}, "<p>Erro</p>")
         -> "<p>Solicitante: Ana &lt;a@x&gt;</p><p>Erro</p>"
    """
    nome = (requestor or {}).get("name") or "Desconhecido"
    email = (requestor or {}).get("email") or "Sem e-mail"
    solicitante = html.escape(f"Solicitante: {nome} <{email}>", quote=False)
    return f"<p>{solicitante}</p>{descricao_html or ''}"


def campos_chamado_glpi(ticket_tiflux: dict, id_requerente: int, id_tecnico: int) -> dict:
    """
    Input do POST /Ticket no GLPI para um ticket lido do Tiflux (GET individual,
    que traz `description`). Atores vão no próprio POST; urgência e impacto 3
    fazem a matriz do GLPI dar prioridade 3, a mesma enviada.
    Ex.: campos_chamado_glpi(ticket, 173, 4988)["itilcategories_id"] -> 272
    """
    return {
        "name": titulo_glpi_aberto_pelo_tiflux(int(ticket_tiflux["ticket_number"]), ticket_tiflux.get("title") or ""),
        "content": conteudo_glpi_aberto_pelo_tiflux(ticket_tiflux.get("requestor"), ticket_tiflux.get("description")),
        "entities_id": ENTIDADE_GLPI_STII,
        "itilcategories_id": CATEGORIA_GLPI_POR_MESA[ticket_tiflux["desk"]["id"]],
        "requesttypes_id": ORIGEM_GLPI_STI,
        "locations_id": LOCALIZACAO_GLPI_AREA_TECNICA,
        "type": TIPO_GLPI_INCIDENTE,
        "urgency": PRIORIDADE_GLPI_MEDIA,
        "impact": PRIORIDADE_GLPI_MEDIA,
        "priority": PRIORIDADE_GLPI_MEDIA,
        "_users_id_requester": id_requerente,
        "_users_id_assign": id_tecnico,
        "_groups_id_observer": GRUPO_GLPI_EMBRAS_ATENDIMENTOS,
    }
