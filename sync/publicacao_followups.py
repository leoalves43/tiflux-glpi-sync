"""Publicação de followups/respostas entre GLPI e Tiflux, um sentido por função pública."""

import html
from datetime import datetime, timedelta

from sync import db_followups
from sync.config import Config, log
from sync.glpi_client import GlpiClient
from sync.regras_negocio import definir_autor_glpi
from sync.tiflux_client import TifluxClient


def prefixar_autor_tiflux(nome: str | None, timestamp_utc: str | None, conteudo: str) -> str:
    """
    Prefixa o conteúdo com o nome de quem respondeu de fato no Tiflux (em
    negrito) e a data/hora do assentamento — a autoria real no GLPI
    (users_id) é sempre Léo (ver definir_autor_glpi), não o técnico do
    Tiflux, então esse prefixo é a única forma de identificar quem
    respondeu de verdade dentro do texto.
    """
    cabecalho = f"<strong>{nome or 'Desconhecido'}</strong>"
    data_hora = formatar_data_hora_brasilia(timestamp_utc)
    if data_hora:
        cabecalho += f" ({data_hora})"
    return f"{cabecalho}<br><br>{conteudo}"


def formatar_data_hora_brasilia(timestamp_utc: str | None) -> str | None:
    """Converte um timestamp UTC do Tiflux (ex.: "2026-09-09T14:10:26Z") pra "dd/mm/aaaa hh:mm" em horário de Brasília (UTC-3)."""
    if not timestamp_utc:
        return None
    try:
        dt_utc = datetime.strptime(timestamp_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return (dt_utc - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")


def resposta_criada_pela_integracao(resposta: dict) -> bool:
    """Resposta do Tiflux criada via API (followup vindo do GLPI), não por um técnico — o Tiflux marca answer_origin='api' e prefixa o autor com "[API]"."""
    return resposta.get("answer_origin") == "api" or str(resposta.get("author", "")).startswith("[API]")


def _acumular(sucesso: bool, qtd_sucesso: int, qtd_erro: int) -> tuple[int, int]:
    return (qtd_sucesso + 1, qtd_erro) if sucesso else (qtd_sucesso, qtd_erro + 1)


def sincronizar_followups_glpi_para_tiflux(
    conn, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_chamado: int, numero_tiflux: str,
) -> tuple[int, int]:
    """
    Busca followups do chamado no GLPI, filtra os que ainda não foram
    publicados no Tiflux, e cria cada um lá. Retorna (qtd_sucesso, qtd_erro).
    """
    pendentes = _followups_glpi_pendentes(conn, config, glpi, id_chamado)
    if not pendentes:
        return 0, 0

    qtd_sucesso = qtd_erro = 0
    for followup in pendentes:
        sucesso = _publicar_followup_no_tiflux(conn, config, glpi, tiflux, id_chamado, numero_tiflux, followup)
        qtd_sucesso, qtd_erro = _acumular(sucesso, qtd_sucesso, qtd_erro)

    return qtd_sucesso, qtd_erro


def _followups_glpi_pendentes(conn, config: Config, glpi: GlpiClient, id_chamado: int) -> list[dict]:
    """
    Followups do GLPI ainda não publicados no Tiflux, excluindo os que a
    própria integração criou lá (Tiflux -> GLPI): esses sempre têm users_id
    Léo ou Sania (ver definir_autor_glpi), nunca de quem respondeu de fato no
    Tiflux — sem esse filtro, cada um viraria eco: publicado de volta no
    Tiflux como se fosse uma resposta nova, duplicando a mensagem original.
    Um followup escrito de verdade por Léo ou Sania direto no GLPI (não via
    esta integração) também é filtrado — mesma authoria, sem como distinguir.
    Followups privados não são sincronizados: só comunicação pública cruza
    pro Tiflux.
    """
    followups = glpi.obter_followups(id_chamado)
    if not followups:
        return []
    ja_processados = db_followups.obter_followups_glpi_ja_processados(conn, config, id_chamado)
    ids_proprios = {config.id_glpi_leo, config.id_glpi_sania}
    return [
        f for f in followups
        if f.get("id") not in ja_processados
        and f.get("users_id") not in ids_proprios
        and not f.get("is_private")
    ]


# Limite de arquivos por requisição de resposta no Tiflux (POST .../answers e
# .../client-answers) — ver openapi-spec-tiflux.json. Followup do GLPI com
# mais anexos que isso manda o excedente pro nível do chamado (ver
# _enviar_anexos_excedentes) em vez de descartar.
_MAX_ANEXOS_POR_RESPOSTA_TIFLUX = 10


def _publicar_followup_no_tiflux(conn, config, glpi: GlpiClient, tiflux: TifluxClient, id_chamado, numero_tiflux, followup) -> bool:
    id_origem = followup.get("id")
    # Alguns followups do GLPI vêm com o conteúdo HTML-entity-encoded
    # (ex.: "&#60;p&#62;texto&#60;/p&#62;" em vez de "<p>texto</p>"),
    # dependendo de como foram criados; html.unescape() normaliza pros
    # dois casos (é um no-op se o conteúdo já vier como HTML literal).
    conteudo = html.unescape(followup.get("content") or "")
    anexos, avisos_anexos = glpi.obter_anexos_do_followup(id_origem, config.tamanho_maximo_anexo_mb)
    anexos_na_resposta = anexos[:_MAX_ANEXOS_POR_RESPOSTA_TIFLUX]
    anexos_excedentes = anexos[_MAX_ANEXOS_POR_RESPOSTA_TIFLUX:]

    # Sempre client-answers com o nome real do autor no GLPI (requerente ou
    # não): /answers não aceita autor e aparece como o dono do token da API
    # ("API Embras") — pedido do usuário após o followup de terceiro do
    # GLPI #34522 chegar assim no Tiflux.
    nome_autor = glpi.obter_nome_usuario(followup.get("users_id"))
    resp = tiflux.publicar_resposta_cliente(numero_tiflux, conteudo, nome_autor, anexos_na_resposta)
    sucesso = _registrar_publicacao_no_tiflux(conn, config, id_chamado, numero_tiflux, "publica", id_origem, resp, avisos_anexos)
    if sucesso and anexos_excedentes:
        _enviar_anexos_excedentes(tiflux, numero_tiflux, id_origem, anexos_excedentes)
    return sucesso


def _enviar_anexos_excedentes(tiflux: TifluxClient, numero_tiflux, id_origem, anexos_excedentes: list) -> None:
    """Followup com mais de 10 anexos — o excedente vai pro chamado (nível ticket) no Tiflux, perdendo o vínculo visual com o followup, mas sem ser descartado."""
    _, falhados, motivos = tiflux.enviar_anexos(numero_tiflux, anexos_excedentes)
    if falhados:
        log(f"⚠️ Followup GLPI #{id_origem}: {falhados} anexo(s) excedente(s) (>10) falharam ao enviar pro "
            f"Tiflux #{numero_tiflux}: {'; '.join(motivos)}")


def _registrar_publicacao_no_tiflux(conn, config, id_chamado, numero_tiflux, tipo, id_origem, resp, avisos_anexos: list) -> bool:
    if resp.status_code not in (200, 201):
        db_followups.registrar_resultado_followup(
            conn, config, id_chamado, numero_tiflux, "glpi_para_tiflux", tipo, id_origem, None,
            "erro", f"Falha ao publicar followup no Tiflux ({resp.status_code}): {resp.text}",
        )
        return False

    id_destino = resp.json().get("id")
    if not id_destino:
        db_followups.registrar_resultado_followup(
            conn, config, id_chamado, numero_tiflux, "glpi_para_tiflux", tipo, id_origem, None,
            "erro", "Followup publicado no Tiflux, mas não foi possível identificar o id na resposta",
        )
        return False

    mensagem = f"Followup GLPI #{id_origem} publicado no Tiflux (id {id_destino})"
    if avisos_anexos:
        mensagem += f" | Avisos anexos: {'; '.join(avisos_anexos)}"
    db_followups.registrar_resultado_followup(
        conn, config, id_chamado, numero_tiflux, "glpi_para_tiflux", tipo, id_origem, id_destino, "sucesso", mensagem,
    )
    return True


def sincronizar_followups_tiflux_para_glpi(
    conn, config: Config, glpi: GlpiClient, tiflux: TifluxClient, id_chamado: int, numero_tiflux: str,
) -> tuple[int, int]:
    """
    Busca respostas públicas (/answers) do ticket no Tiflux, filtra as que
    ainda não foram sincronizadas ou que a própria integração criou (eco), e
    cria um followup correspondente no GLPI pra cada uma. Comunicações
    internas (/internal_communications) não são sincronizadas: só comunicação
    pública cruza pro GLPI.

    A autoria do followup no GLPI é sempre Léo (ver definir_autor_glpi) — sem
    isso, o GLPI atribui tudo ao usuário autenticado da API, independente de
    quem respondeu de fato no Tiflux.

    Defesa contra eco: a tabela de auditoria (id já processado) mais o campo
    answer_origin/author.
    Retorna (qtd_sucesso, qtd_erro).
    """
    id_autor_glpi = definir_autor_glpi(config)

    ja_processados_ou_proprios = db_followups.obter_respostas_tiflux_ja_processadas_ou_proprias(conn, config, numero_tiflux)
    respostas = tiflux.listar_respostas(numero_tiflux, config.tamanho_pagina_respostas_tiflux, config.max_paginas_respostas_tiflux)

    return _publicar_respostas_publicas(conn, config, glpi, id_chamado, numero_tiflux, respostas, ja_processados_ou_proprios, id_autor_glpi)


def _publicar_respostas_publicas(conn, config, glpi: GlpiClient, id_chamado, numero_tiflux, respostas, ja_processados_ou_proprios, id_autor_glpi: int) -> tuple[int, int]:
    qtd_sucesso = qtd_erro = 0
    # O Tiflux lista da mais nova pra mais antiga; publicar nessa ordem deixava a
    # timeline do GLPI invertida quando várias entram de uma vez (GLPI #34848).
    for resposta in sorted(respostas, key=lambda r: r.get("answer_time") or ""):
        if _deve_ignorar_resposta_publica(resposta, ja_processados_ou_proprios):
            continue
        id_origem = resposta.get("id")
        conteudo = html.unescape(resposta.get("name") or "")
        conteudo = prefixar_autor_tiflux(resposta.get("author"), resposta.get("answer_time"), conteudo)
        id_criado, erro = glpi.criar_followup(id_chamado, conteudo, is_private=0, users_id=id_autor_glpi)
        if id_criado is not None:
            _restaurar_status_novo_glpi(glpi, id_chamado)
        sucesso = _registrar_followup_tiflux_para_glpi(
            conn, config, id_chamado, numero_tiflux, "publica", id_origem, id_criado, erro,
            mensagem_sucesso=f"Resposta Tiflux #{id_origem} publicada como followup no GLPI (id {id_criado})",
        )
        qtd_sucesso, qtd_erro = _acumular(sucesso, qtd_sucesso, qtd_erro)
    return qtd_sucesso, qtd_erro


def _deve_ignorar_resposta_publica(resposta: dict, ja_processados_ou_proprios: set[int]) -> bool:
    if resposta.get("id") in ja_processados_ou_proprios:
        return True
    return resposta_criada_pela_integracao(resposta)


def _restaurar_status_novo_glpi(glpi: GlpiClient, id_glpi: int) -> None:
    """
    Criar o followup (acima) faz o GLPI mudar o status pra "Processando
    (atribuído)" automaticamente. Volta pra Novo; só loga se falhar — não
    afeta o registro do followup em si, que já foi criado com sucesso.
    """
    sucesso, erro = glpi.voltar_status_para_novo(id_glpi)
    if not sucesso:
        log(f"⚠️ Followup criado no chamado #{id_glpi}, mas falhou ao voltar status para Novo no GLPI: {erro}")


def _registrar_followup_tiflux_para_glpi(
    conn, config, id_chamado, numero_tiflux, tipo, id_origem, id_criado, erro, mensagem_sucesso: str,
) -> bool:
    if erro:
        db_followups.registrar_resultado_followup(
            conn, config, id_chamado, numero_tiflux, "tiflux_para_glpi", tipo, id_origem, None, "erro", erro,
        )
        return False

    db_followups.registrar_resultado_followup(
        conn, config, id_chamado, numero_tiflux, "tiflux_para_glpi", tipo, id_origem, id_criado,
        "sucesso", mensagem_sucesso,
    )
    return True
