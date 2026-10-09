"""Ponto de entrada da sincronização GLPI -> Tiflux. Ver docs/ARCHITECTURE.md."""

import sys
from collections import Counter
from datetime import datetime, timezone

from sync import db_chamados
from sync.abertura_tiflux_para_glpi import abrir_chamados_do_tiflux
from sync.config import Config, log
from sync.glpi_client import GlpiClient
from sync.panorama_tiflux import concluir_panorama_tiflux, ler_panorama_tiflux
from sync.processamento_chamado import processar_chamado
from sync.sincronizacao_followups import sincronizar_followups
from sync.tiflux_client import TifluxClient
from sync.tipos import ConexaoDb


def main() -> None:
    log("Iniciando sincronização GLPI -> Tiflux")
    config = Config.carregar()
    conn = _conectar_db_ou_sair(config)
    glpi = _autenticar_glpi_ou_sair(config, conn)
    tiflux = TifluxClient.conectar(config)

    try:
        _processar_chamados_pendentes(conn, config, glpi, tiflux)
        requisicoes_na_criacao = tiflux.requisicoes_enviadas

        # Followups (GLPI <-> Tiflux) dos chamados já sincronizados — roda sempre,
        # mesmo sem chamados novos acima, e já pega chamados criados nesta mesma
        # execução em vez de esperar o próximo ciclo do cron.
        _sincronizar_followups_com_panorama(conn, config, glpi, tiflux)
        log(resumo_requisicoes_tiflux(requisicoes_na_criacao, tiflux.requisicoes_enviadas))
    finally:
        glpi.encerrar_sessao()
        conn.close()


def resumo_requisicoes_tiflux(na_criacao: int, total: int) -> str:
    """
    Linha de log com o uso da cota do Tiflux (120/min) na execução, separando a
    criação de chamados — só a parte dos followups é fixa por execução (spec 008).
    Ex.: resumo_requisicoes_tiflux(4, 7) -> "📡 Requisições ao Tiflux: 7 (criação 4 + followups 3)"
    """
    return f"📡 Requisições ao Tiflux: {total} (criação {na_criacao} + followups {total - na_criacao})"


def _sincronizar_followups_com_panorama(
    conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient,
) -> None:
    # Panorama incompleto (None) = nada a concluir dele; a próxima execução
    # cobre o mesmo período, já que o checkpoint não avança (spec 008).
    panorama = ler_panorama_tiflux(conn, config, tiflux, datetime.now(timezone.utc))
    if panorama is None:
        return
    # Antes dos followups: o chamado recém-aberto já entra no rodízio desta
    # execução (ticket fechado entre duas execuções vai a Solucionado já).
    abrir_chamados_do_tiflux(conn, config, glpi, tiflux, panorama)
    sincronizar_followups(conn, config, glpi, tiflux, panorama)
    concluir_panorama_tiflux(conn, config, panorama)


def _conectar_db_ou_sair(config: Config) -> ConexaoDb:
    try:
        return db_chamados.conectar_db(config)
    except Exception as e:
        log(f"❌ Não foi possível conectar ao Postgres: {e}")
        sys.exit(1)


def _autenticar_glpi_ou_sair(config: Config, conn: ConexaoDb) -> GlpiClient:
    try:
        return GlpiClient.autenticar(config)
    except Exception as e:
        log(f"❌ Não foi possível autenticar no GLPI: {e}")
        conn.close()
        sys.exit(1)


def _processar_chamados_pendentes(conn: ConexaoDb, config: Config, glpi: GlpiClient, tiflux: TifluxClient) -> None:
    candidatos = _levantar_candidatos(conn, config, glpi)
    if not candidatos:
        log("Nenhum chamado novo ou pendente de retry.")
        return

    log(f"{len(candidatos)} chamado(s) para processar: {candidatos}")
    totais: Counter[str] = Counter()
    for id_chamado in candidatos:
        status, numero_tiflux, mensagem = processar_chamado(glpi, tiflux, config, id_chamado)
        totais[_registrar_processamento(conn, config, id_chamado, status, numero_tiflux, mensagem)] += 1

    log(f"Finalizado. Sucesso: {totais['sucesso']} | Ignorado: {totais['ignorado']} | Erro: {totais['erro']}")


def _registrar_processamento(
    conn: ConexaoDb, config: Config, id_chamado: int, status: str, numero_tiflux: str | None, mensagem: str,
) -> str:
    """
    Grava/loga o resultado de um chamado e devolve a categoria da contagem
    final ('sucesso', 'ignorado' ou 'erro' — qualquer outro status conta como erro).
    Ex.: _registrar_processamento(conn, config, 34865, "sucesso", "364569", "Ticket ...") -> "sucesso"
    """
    if status == "ignorado":
        # Não interessa: nem grava na auditoria, nem loga por chamado —
        # só entra na contagem final.
        return "ignorado"
    db_chamados.registrar_resultado(conn, config, id_chamado, numero_tiflux, status, mensagem)
    if status == "sucesso":
        log(f"✅ Chamado #{id_chamado}: {mensagem}")
        return "sucesso"
    log(f"❌ Chamado #{id_chamado}: {mensagem}")
    return "erro"


def _levantar_candidatos(conn: ConexaoDb, config: Config, glpi: GlpiClient) -> list[int]:
    ids_processados = db_chamados.obter_ids_ja_processados(conn, config)
    ids_retry = db_chamados.obter_ids_para_retry(conn, config)
    # Só reprocessa erros de chamados que ainda estão dentro da faixa válida
    # (se ID_MINIMO_GLPI mudar pra cima no futuro, erros antigos abaixo dele
    # não devem ficar sendo retentados pra sempre)
    ids_retry = {i for i in ids_retry if i >= config.id_minimo_glpi}

    id_inicial_sondagem = db_chamados.obter_proximo_id_para_sondar(conn, config)
    ids_glpi_encontrados = glpi.buscar_chamados_desde(
        id_inicial_sondagem, config.tamanho_pagina_busca, config.max_furos_seguidos
    )
    ids_novos = [i for i in ids_glpi_encontrados if i not in ids_processados]

    return sorted(set(ids_novos) | ids_retry)


if __name__ == "__main__":
    main()
