"""Arquivos do Tiflux copiados para o GLPI: do ticket na abertura (spec 009) e
de cada resposta pública no followup que ela gerou (spec 014).

Mesmo papel de processamento_chamado._sincronizar_anexos no sentido inverso:
nunca derruba a abertura nem o followup — o item já existe; só devolve um
resumo pro log/auditoria.
"""

from requests import RequestException

from sync.config import Config
from sync.glpi_abertura_client import GlpiAberturaClient
from sync.tiflux_client import TifluxClient
from sync.tipos import NumeroTiflux


def copiar_anexos_tiflux_para_glpi(
    tiflux: TifluxClient, glpi_abertura: GlpiAberturaClient, config: Config, numero_tiflux: int, id_glpi: int,
) -> str:
    """
    Copia cada arquivo de /tickets/{n}/files; "" se não havia nenhum.
    Ex.: copiar_anexos_tiflux_para_glpi(tiflux, glpi_abertura, config, 364925, 35001) -> " | Anexos: 1 copiado(s)"
    """
    arquivos = tiflux.listar_arquivos_ticket(
        numero_tiflux, config.tamanho_pagina_respostas_tiflux, config.max_paginas_respostas_tiflux,
    )
    return _copiar_todos(tiflux, glpi_abertura, config, arquivos, "Ticket", id_glpi)


def copiar_anexos_resposta_tiflux_para_glpi(
    tiflux: TifluxClient, glpi_abertura: GlpiAberturaClient, config: Config, numero_tiflux: NumeroTiflux,
    resposta: dict, id_followup: int,
) -> str:
    """
    Copia os arquivos da resposta pública pro followup GLPI que ela gerou; "" sem
    arquivos. Só lê a resposta no Tiflux se a listagem disse files_count > 0 (spec 007).
    Ex.: copiar_anexos_resposta_tiflux_para_glpi(tiflux, ga, config, 365680, {"id": 32082144, "files_count": 7}, 78602)
    -> " | Anexos: 7 copiado(s)"
    """
    if not resposta.get("files_count"):
        return ""
    arquivos = tiflux.listar_arquivos_resposta(numero_tiflux, resposta.get("id"))
    if arquivos is None:
        return f" | Anexos: falha ao ler os {resposta.get('files_count')} arquivo(s) da resposta no Tiflux"
    return _copiar_todos(tiflux, glpi_abertura, config, arquivos, "ITILFollowup", id_followup)


def _copiar_todos(
    tiflux: TifluxClient, glpi_abertura: GlpiAberturaClient, config: Config, arquivos: list[dict],
    itemtype: str, items_id: int,
) -> str:
    falhas = [f for f in (_copiar(tiflux, glpi_abertura, config, a, itemtype, items_id) for a in arquivos) if f]
    if not arquivos:
        return ""
    resumo = f" | Anexos: {len(arquivos) - len(falhas)} copiado(s)"
    return f"{resumo}, {len(falhas)} falhou(aram) [{'; '.join(falhas)}]" if falhas else resumo


def _copiar(
    tiflux: TifluxClient, glpi_abertura: GlpiAberturaClient, config: Config, arquivo: dict,
    itemtype: str, items_id: int,
) -> str | None:
    """Erro de um arquivo, ou None se copiou."""
    nome = arquivo.get("file_name") or f"arquivo_{arquivo.get('id')}"
    if (arquivo.get("size") or 0) > config.tamanho_maximo_anexo_mb * 1024 * 1024:
        return f"'{nome}' acima de {config.tamanho_maximo_anexo_mb}MB"
    # Exceção de rede não pode escapar: o followup já foi criado e ainda não
    # tem linha na auditoria — escapar faria a próxima execução duplicá-lo.
    try:
        conteudo = tiflux.baixar_arquivo(arquivo.get("url") or "")
        if conteudo is None:
            return f"'{nome}': falha ao baixar do Tiflux"
        mime = arquivo.get("content_type") or "application/octet-stream"
        return glpi_abertura.anexar_documento(itemtype, items_id, nome, conteudo, mime)
    except RequestException as erro:
        return f"'{nome}': erro de rede ({type(erro).__name__})"
