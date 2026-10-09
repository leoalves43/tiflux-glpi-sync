"""
CLI manual da abertura Tiflux -> GLPI (spec 009) para UM ticket.

Sem --aplicar só lê (Tiflux, GLPI e auditoria) e imprime o que seria enviado
ao GLPI. Com --aplicar abre de verdade, pelo mesmo caminho do cron
(abertura_tiflux_para_glpi.abrir_ticket_no_glpi), com as mesmas proteções.

Uso: python -m sync.abrir_ticket_tiflux_no_glpi --numero-tiflux 364990 [--aplicar]
"""

import argparse
import json

from sync import db_abertura_tiflux, db_chamados
from sync.abertura_tiflux_para_glpi import abrir_ticket_no_glpi, numeros_ja_vinculados
from sync.config import Config
from sync.glpi_abertura_client import GlpiAberturaClient
from sync.glpi_client import GlpiClient
from sync.regras_abertura_glpi import campos_chamado_glpi, telefone_para_glpi, ticket_candidato_a_abertura
from sync.regras_negocio import definir_autor_glpi
from sync.tiflux_client import TifluxClient
from sync.tipos import ConexaoDb


def main() -> None:
    argumentos = _ler_argumentos()
    config = Config.carregar()
    if config.abertura_tiflux_desde is None:
        print("ABERTURA_TIFLUX_DESDE vazio no .env: a abertura Tiflux -> GLPI está desligada.")
        return
    conn = db_chamados.conectar_db(config)
    glpi = GlpiClient.autenticar(config)
    try:
        _executar(conn, config, glpi, TifluxClient.conectar(config), argumentos)
    finally:
        glpi.encerrar_sessao()
        conn.close()


def _executar(conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient, argumentos: argparse.Namespace) -> None:
    vinculados = numeros_ja_vinculados(conn, config, db_abertura_tiflux.obter_estados_abertura(conn, config))
    if argumentos.aplicar:
        id_glpi = abrir_ticket_no_glpi(conn, config, glpi.cliente_abertura(), glpi, tiflux, argumentos.numero_tiflux, vinculados)
        print(f"Chamado GLPI: #{id_glpi}" if id_glpi else "Nada aberto — veja o log acima.")
        return
    print(simular_abertura(config, glpi.cliente_abertura(), tiflux, argumentos.numero_tiflux, vinculados))


def simular_abertura(
    config: Config, glpi_abertura: GlpiAberturaClient, tiflux: TifluxClient, numero_tiflux: int,
    vinculados: set[int],
) -> str:
    """
    Texto com o que a abertura enviaria ao GLPI, sem escrever nada.
    Ex.: simular_abertura(config, glpi.cliente_abertura(), tiflux, 364990, set()) -> "Candidato: sim\\n..."
    """
    ticket, status_http = tiflux.obter_ticket(numero_tiflux)
    if ticket is None:
        return f"Ticket Tiflux #{numero_tiflux} não lido (status {status_http})."
    candidato = ticket_candidato_a_abertura(ticket, config.abertura_tiflux_desde, vinculados)
    requestor = ticket.get("requestor") or {}
    id_requerente = glpi_abertura.buscar_usuario_por_email(requestor.get("email")) or definir_autor_glpi(config)
    campos = campos_chamado_glpi(ticket, id_requerente, definir_autor_glpi(config))
    return (f"Candidato: {'sim' if candidato else 'NÃO (seria ignorado)'}\n"
            f"Telefone no plugin: {telefone_para_glpi(requestor.get('telephone'))}\n"
            f"POST /Ticket input:\n{json.dumps(campos, ensure_ascii=False, indent=2)}")


def _ler_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Abre no GLPI um ticket do Tiflux (spec 009).")
    parser.add_argument("--numero-tiflux", type=int, required=True)
    parser.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o que seria enviado")
    return parser.parse_args()


if __name__ == "__main__":
    main()
