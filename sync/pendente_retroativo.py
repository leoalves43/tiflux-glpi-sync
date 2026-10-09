"""
Uso único (spec 009, AC 13): chamados sincronizados que estão Novo no GLPI
passam para Pendente, a regra nova. Sem --aplicar só lista o que mudaria.

Uso: python -m sync.pendente_retroativo [--aplicar]
"""

import argparse

from sync import db_chamados
from sync.config import Config, log
from sync.glpi_client import GlpiClient

STATUS_GLPI_NOVO = 1


def chamados_novos_sincronizados(glpi: GlpiClient, ids_glpi: list[int]) -> list[int]:
    """
    Dos chamados dados, os que estão Novo no GLPI agora (ilegível = fora, com aviso).
    Ex.: chamados_novos_sincronizados(glpi, [34900, 34986]) -> [34986]
    """
    novos = []
    for id_glpi in ids_glpi:
        ticket, status_http = glpi.obter_ticket(id_glpi)
        if ticket is None:
            log(f"⚠️ Chamado #{id_glpi} ilegível no GLPI (status {status_http}) — fora do retroativo")
        elif ticket.get("status") == STATUS_GLPI_NOVO:
            novos.append(id_glpi)
    return novos


def deixar_pendentes(glpi: GlpiClient, ids_glpi: list[int]) -> int:
    """Põe cada chamado em Pendente; devolve quantos falharam (cada falha é logada)."""
    falhas = 0
    for id_glpi in ids_glpi:
        sucesso, erro = glpi.definir_status_pendente(id_glpi)
        if not sucesso:
            falhas += 1
            log(f"❌ Chamado #{id_glpi}: {erro}")
    return falhas


def main() -> None:
    aplicar = _ler_argumentos().aplicar
    config = Config.carregar()
    conn = db_chamados.conectar_db(config)
    glpi = GlpiClient.autenticar(config)
    try:
        ids = sorted(db_chamados.obter_ids_ja_processados(conn, config))
        novos = chamados_novos_sincronizados(glpi, ids)
        log(f"{len(novos)} de {len(ids)} chamado(s) sincronizado(s) estão Novo no GLPI: {novos}")
        if aplicar and novos:
            log(f"Pendente aplicado: {len(novos) - deixar_pendentes(glpi, novos)} de {len(novos)}")
    finally:
        glpi.encerrar_sessao()
        conn.close()


def _ler_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Passa para Pendente os chamados sincronizados que estão Novo.")
    parser.add_argument("--aplicar", action="store_true", help="sem isto, só lista")
    return parser.parse_args()


if __name__ == "__main__":
    main()
