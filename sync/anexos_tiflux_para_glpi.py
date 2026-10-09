"""Anexos do ticket do Tiflux copiados para o chamado aberto no GLPI (spec 009).

Mesmo papel de processamento_chamado._sincronizar_anexos no sentido inverso:
nunca derruba a abertura — o chamado já existe; só devolve um resumo pro log.
"""

from sync.config import Config
from sync.glpi_abertura_client import GlpiAberturaClient
from sync.tiflux_client import TifluxClient


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
    falhas = [f for f in (_copiar(tiflux, glpi_abertura, config, a, id_glpi) for a in arquivos) if f]
    if not arquivos:
        return ""
    resumo = f" | Anexos: {len(arquivos) - len(falhas)} copiado(s)"
    return f"{resumo}, {len(falhas)} falhou(aram) [{'; '.join(falhas)}]" if falhas else resumo


def _copiar(
    tiflux: TifluxClient, glpi_abertura: GlpiAberturaClient, config: Config, arquivo: dict, id_glpi: int,
) -> str | None:
    """Erro de um arquivo, ou None se copiou."""
    nome = arquivo.get("file_name") or f"arquivo_{arquivo.get('id')}"
    if (arquivo.get("size") or 0) > config.tamanho_maximo_anexo_mb * 1024 * 1024:
        return f"'{nome}' acima de {config.tamanho_maximo_anexo_mb}MB"
    conteudo = tiflux.baixar_arquivo(arquivo.get("url") or "")
    if conteudo is None:
        return f"'{nome}': falha ao baixar do Tiflux"
    return glpi_abertura.anexar_documento(id_glpi, nome, conteudo, arquivo.get("content_type") or "application/octet-stream")
