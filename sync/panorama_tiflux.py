"""O que olhar no Tiflux nesta execução, lido em poucas listagens (spec 008).

Antes, cada chamado do rodízio custava um GET /tickets/{n} (+ /answers) por
execução (~145 requisições, limite de 120/min). O panorama troca isso por
duas listagens: tickets abertos e tickets atualizados desde o checkpoint.
Ele só aponta candidatos — toda escrita continua precedida da leitura
individual do ticket (sincronizacao_followups).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sync import db_followups
from sync.config import Config, log
from sync.mudancas_status_tiflux import cruzar_mudancas_de_status
from sync.tiflux_client import ListagemTifluxIncompleta, TifluxClient
from sync.tipos import ConexaoDb, NumeroTiflux


@dataclass(frozen=True)
class PanoramaTiflux:
    """
    `abertos`/`atualizados`: números de ticket no Tiflux. `mudancas`: pares
    (id_glpi, numero_tiflux) com status divergente da última cascata.
    `varredura_completa`: pares da rede de segurança desta execução.
    Ex.: PanoramaTiflux(agora, frozenset({364678}), frozenset(), (), ((34759, 364160),))
    """

    inicio_execucao_utc: datetime
    abertos: frozenset[NumeroTiflux]
    atualizados: frozenset[NumeroTiflux]
    mudancas: tuple[tuple[int, NumeroTiflux], ...]
    varredura_completa: tuple[tuple[int, NumeroTiflux], ...]


def ler_panorama_tiflux(
    conn: ConexaoDb, config: Config, tiflux: TifluxClient, agora_utc: datetime,
) -> PanoramaTiflux | None:
    """
    None se alguma listagem não veio inteira: nada pode ser concluído dela, e
    o checkpoint não avança, então a próxima execução cobre o mesmo período.
    Ex.: ler_panorama_tiflux(conn, config, tiflux, datetime.now(timezone.utc))
    """
    try:
        atualizados = tiflux.listar_tickets_atualizados_desde(
            _inicio_da_janela(conn, config, agora_utc),
            config.tamanho_pagina_tickets_tiflux, config.max_paginas_tickets_tiflux,
        )
        abertos = tiflux.listar_tickets_abertos(config.tamanho_pagina_tickets_tiflux, config.max_paginas_tickets_tiflux)
    except ListagemTifluxIncompleta as e:
        log(f"⚠️ Panorama do Tiflux incompleto — followups pulados nesta execução, checkpoint mantido. {e}")
        return None
    return PanoramaTiflux(
        inicio_execucao_utc=agora_utc,
        abertos=_numeros(abertos),
        atualizados=_numeros(atualizados),
        mudancas=tuple(cruzar_mudancas_de_status(conn, config, atualizados)),
        varredura_completa=tuple(
            db_followups.obter_chamados_para_varredura_completa(conn, config, config.varredura_completa_por_execucao),
        ),
    )


def concluir_panorama_tiflux(conn: ConexaoDb, config: Config, panorama: PanoramaTiflux) -> None:
    """
    Avança o checkpoint pro início desta execução. Falhas de um chamado não o
    seguram — um ticket que sempre falha travaria a janela até o teto de
    páginas; esses chamados vão pra varredura completa da próxima execução
    (sincronizacao_followups._motivo_para_retentar).
    Ex.: concluir_panorama_tiflux(conn, config, panorama)
    """
    db_followups.registrar_checkpoint_tiflux(conn, config, panorama.inicio_execucao_utc)


def _inicio_da_janela(conn: ConexaoDb, config: Config, agora_utc: datetime) -> datetime:
    checkpoint = db_followups.obter_checkpoint_tiflux(conn, config)
    if checkpoint is None:
        return agora_utc - timedelta(minutes=config.janela_mudancas_status_tiflux_minutos)
    return checkpoint - timedelta(minutes=config.margem_checkpoint_tiflux_minutos)


def _numeros(tickets: list[dict]) -> frozenset[NumeroTiflux]:
    return frozenset(t["ticket_number"] for t in tickets if t.get("ticket_number") is not None)
