"""
CLI manual: encerra no GLPI (status Solucionado) um chamado atendido por um
ticket aberto à mão no Tiflux antes da integração existir. Ver
docs/specs/002-encerrar-legado.md.

Uso: python -m sync.encerrar_legado --id-glpi 33500 --numero-tiflux 360123

Reaproveita o encerramento em cascata do ciclo normal (técnico, solução = última
resposta pública do técnico no Tiflux, status Solucionado), mas de propósito
NÃO grava o vínculo em api_glpi_tiflux: o ciclo automático (rodízio de
followups, mudancas_status_tiflux) só enxerga chamados dessa tabela, então o
histórico antigo nunca é sincronizado e o chamado não volta a ser acompanhado.
Última linha do stdout: JSON {"status", "numero_tiflux", "mensagem"}.
"""

import argparse
import json

from sync import db_chamados
from sync.config import Config, log
from sync.glpi_client import GlpiClient
from sync.sincronizacao_followups import STATUS_GLPI_ABERTOS, encerrar_em_cascata
from sync.tiflux_client import TifluxClient

ResultadoEncerramento = tuple[str, str]  # (status, mensagem)


def motivo_recusa(ticket_glpi: dict, ticket_tiflux: dict, id_glpi: int, numero_tiflux: str) -> str | None:
    """
    Por que não encerrar, ou None se pode. Só encerra o que já foi resolvido
    no Tiflux e ainda está aberto no GLPI.
    Ex.: motivo_recusa({"status": 2}, {"is_closed": False}, 33500, "360123") -> "Ticket Tiflux #360123 ainda está aberto ..."
    """
    if not ticket_tiflux.get("is_closed"):
        return f"Ticket Tiflux #{numero_tiflux} ainda está aberto — feche no Tiflux antes de encerrar no GLPI."
    if ticket_glpi.get("status") not in STATUS_GLPI_ABERTOS:
        return (f"Chamado GLPI #{id_glpi} já não está aberto (status {ticket_glpi.get('status')}, "
                f"esperado um de {STATUS_GLPI_ABERTOS}) — nada a encerrar.")
    return None


def encerrar_legado(
    conn, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_glpi: int, numero_tiflux: str,
) -> ResultadoEncerramento:
    """
    Confere os dois lados e, se elegível, encerra o chamado no GLPI.
    Ex.: encerrar_legado(conn, config, glpi, tiflux, 33500, "360123") -> ("sucesso", "Chamado GLPI #33500 ...")
    """
    ticket_glpi, status_glpi = glpi.obter_ticket(id_glpi)
    if ticket_glpi is None:
        return "erro", f"Chamado GLPI #{id_glpi} não encontrado (status HTTP {status_glpi})."
    ticket_tiflux, status_tiflux = tiflux.obter_ticket(numero_tiflux)
    if ticket_tiflux is None:
        return "erro", f"Ticket Tiflux #{numero_tiflux} não encontrado (status HTTP {status_tiflux})."

    recusa = motivo_recusa(ticket_glpi, ticket_tiflux, id_glpi, numero_tiflux)
    if recusa:
        return "recusado", recusa

    totais = {"status_sucesso": 0, "status_erro": 0}
    encerrar_em_cascata(conn, config, glpi, tiflux, id_glpi, numero_tiflux, ticket_tiflux, totais)
    return _resultado_encerramento(totais, id_glpi, numero_tiflux, ticket_glpi, ticket_tiflux)


def _resultado_encerramento(
    totais: dict[str, int], id_glpi: int, numero_tiflux: str, ticket_glpi: dict, ticket_tiflux: dict,
) -> ResultadoEncerramento:
    # Os dois títulos vão na mensagem pra o operador conferir que o par digitado é o certo.
    par = (f"GLPI #{id_glpi} \"{ticket_glpi.get('name')}\" / "
           f"Tiflux #{numero_tiflux} \"{ticket_tiflux.get('title')}\"")
    if totais["status_sucesso"]:
        return "sucesso", f"Encerrado no GLPI (Solucionado): {par}"
    return "erro", (f"GLPI recusou o encerramento de {par} — detalhe em "
                    f"api_glpi_tiflux_followups (id_origem = -{id_glpi}).")


def main() -> None:
    id_glpi, numero_tiflux = _ler_argumentos()
    config = Config.carregar()
    conn = db_chamados.conectar_db(config)
    try:
        glpi = GlpiClient.autenticar(config)
        try:
            status, mensagem = encerrar_legado(conn, config, glpi, TifluxClient.conectar(config), id_glpi, numero_tiflux)
        finally:
            glpi.encerrar_sessao()
    finally:
        conn.close()
    log(f"[encerrar legado #{id_glpi}] {status}: {mensagem}")
    print(json.dumps({"status": status, "numero_tiflux": numero_tiflux, "mensagem": mensagem}, ensure_ascii=False))


def _ler_argumentos() -> tuple[int, str]:
    parser = argparse.ArgumentParser(description="Encerra no GLPI um chamado atendido por ticket Tiflux aberto manualmente.")
    parser.add_argument("--id-glpi", type=int, required=True)
    parser.add_argument("--numero-tiflux", type=int, required=True)
    args = parser.parse_args()
    return args.id_glpi, str(args.numero_tiflux)


if __name__ == "__main__":
    main()
