"""Postgres — tabela de auditoria de followups (várias linhas por chamado)."""

from datetime import datetime

from sync.config import Config, log
from sync.tipos import ConexaoDb, NumeroTiflux


def obter_chamados_para_varrer_followups(conn: ConexaoDb, config: Config) -> list[tuple[int, int]]:
    """
    Pares (id_glpi, numero_tiflux) de chamados status='sucesso' a varrer
    nesta execução: TODOS os abertos, solucionados (recusáveis) ou nunca
    varridos no GLPI, depois até
    `tamanho_lote_fechados_followups` fechados. Antes era um lote único de 50
    dividido entre abertos e fechados — com 176 fechados, um chamado aberto
    esperava ~4 execuções (Tiflux #364569: 16 min; spec 003). Os fechados
    seguem revisitados pra detectar recusa da solução no GLPI.
    Aberto/fechado vem da marca de varredura (direcao='verificacao_status');
    dentro de cada grupo, varredura mais antiga primeiro (rodízio justo).
    Só status='sucesso': linhas 'erro' podem ter numero_tiflux inconsistente
    (bug conhecido de duplicação em processar_chamado()).
    Ex.: obter_chamados_para_varrer_followups(conn, config) -> [(34865, 364569), ...]
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH chamados AS (
                SELECT t.id_glpi, t.numero_tiflux,
                       COALESCE(v.status = 'fechado', FALSE) AS fechado,
                       f.ultima_varredura
                FROM {config.tabela_auditoria} t
                LEFT JOIN (
                    SELECT id_glpi, MAX(atualizado_em) AS ultima_varredura
                    FROM {config.tabela_followups}
                    GROUP BY id_glpi
                ) f ON f.id_glpi = t.id_glpi
                LEFT JOIN {config.tabela_followups} v
                  ON v.direcao = 'verificacao_status' AND v.id_origem = -t.id_glpi
                WHERE t.status = 'sucesso'
            ),
            abertos AS (
                SELECT id_glpi, numero_tiflux, ultima_varredura FROM chamados
                WHERE NOT fechado
            ),
            fechados AS (
                SELECT id_glpi, numero_tiflux, ultima_varredura FROM chamados
                WHERE fechado
                ORDER BY ultima_varredura ASC NULLS FIRST
                LIMIT %s
            )
            SELECT id_glpi, numero_tiflux FROM (
                SELECT *, 0 AS grupo FROM abertos
                UNION ALL
                SELECT *, 1 AS grupo FROM fechados
            ) selecionados
            ORDER BY grupo, ultima_varredura ASC NULLS FIRST
            """,
            (config.tamanho_lote_fechados_followups,),
        )
        return cur.fetchall()


def obter_followups_glpi_ja_processados(conn: ConexaoDb, config: Config, id_glpi: int) -> set[int]:
    """
    IDs de ITILFollowup do GLPI já publicados com sucesso no Tiflux para este
    chamado. Só considera status='sucesso' (mesmo critério de
    obter_ids_ja_processados p/ chamados) — um followup que falhou fica de
    fora daqui de propósito, pra ser retentado na próxima execução.
    """
    tabela = config.tabela_followups
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id_origem FROM {tabela} "
            f"WHERE direcao = 'glpi_para_tiflux' AND status = 'sucesso' AND id_glpi = %s",
            (id_glpi,),
        )
        return {row[0] for row in cur.fetchall()}


def obter_respostas_tiflux_ja_processadas_ou_proprias(
    conn: ConexaoDb, config: Config, numero_tiflux: NumeroTiflux,
) -> set[int]:
    """
    IDs de resposta/comunicação interna do Tiflux a IGNORAR na varredura
    Tiflux -> GLPI: os que já processamos com sucesso nesse sentido (direcao=
    'tiflux_para_glpi', status='sucesso' — followups com erro ficam de fora
    de propósito, pra serem retentados) UNION os que a própria integração
    criou no sentido glpi_para_tiflux (id_destino, só existe em linhas de
    sucesso) — evita reimportar o próprio eco.
    """
    tabela = config.tabela_followups
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id_origem FROM {tabela}
            WHERE numero_tiflux = %s AND direcao = 'tiflux_para_glpi' AND status = 'sucesso'
            UNION
            SELECT id_destino FROM {tabela}
            WHERE numero_tiflux = %s AND direcao = 'glpi_para_tiflux' AND id_destino IS NOT NULL
            """,
            (numero_tiflux, numero_tiflux),
        )
        return {row[0] for row in cur.fetchall()}


def registrar_resultado_followup(
    conn: ConexaoDb, config: Config, id_glpi: int, numero_tiflux: NumeroTiflux | None, direcao: str, tipo: str,
    id_origem: int, id_destino: int | None, status: str, mensagem: str,
) -> None:
    """Grava (ou atualiza, em caso de retry) o resultado da sincronização de um followup."""
    tabela = config.tabela_followups
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {tabela}
                (id_glpi, numero_tiflux, direcao, tipo, id_origem, id_destino, status, mensagem, tentativas, criado_em, atualizado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, now(), now())
            ON CONFLICT (direcao, id_origem) DO UPDATE SET
                numero_tiflux = EXCLUDED.numero_tiflux,
                tipo          = EXCLUDED.tipo,
                id_destino    = EXCLUDED.id_destino,
                status        = EXCLUDED.status,
                mensagem      = EXCLUDED.mensagem,
                tentativas    = {tabela}.tentativas + 1,
                atualizado_em = now()
            """,
            (id_glpi, numero_tiflux, direcao, tipo, id_origem, id_destino, status, mensagem),
        )
    conn.commit()


def obter_ultima_acao_cascata_sucesso(conn: ConexaoDb, config: Config, id_glpi: int) -> str | None:
    """
    `tipo` ('encerramento', 'reabertura' ou 'reabertura_tiflux') da última
    ação de encerramento/reabertura em cascata BEM-SUCEDIDA registrada pra
    este chamado — linha única por chamado (direcao='tiflux_para_glpi',
    id_origem=-id_glpi, ver _mudar_status_em_cascata e
    reabrir_tiflux_apos_recusa_glpi em cascata_status.py). None se
    nunca houve uma ação de cascata bem-sucedida, ou se a última tentativa
    registrada falhou (status='erro') — só o último estado confirmado conta,
    pra não confundir com uma tentativa que não mudou nada de fato.
    """
    tabela = config.tabela_followups
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT tipo FROM {tabela} "
            f"WHERE direcao = 'tiflux_para_glpi' AND id_origem = %s AND status = 'sucesso'",
            (-id_glpi,),
        )
        linha = cur.fetchone()
        return linha[0] if linha else None


def obter_chamados_por_numero_tiflux(
    conn: ConexaoDb, config: Config, numeros_tiflux: list[int],
) -> dict[int, tuple[int, str | None]]:
    """
    numero_tiflux -> (id_glpi, última ação de cascata bem-sucedida) dos
    chamados sincronizados com sucesso entre `numeros_tiflux`. A ação segue o
    mesmo critério de obter_ultima_acao_cascata_sucesso (None se não houve).
    Ex.: obter_chamados_por_numero_tiflux(conn, config, [364212]) -> {364212: (34769, 'encerramento')}
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.numero_tiflux, t.id_glpi, f.tipo
            FROM {config.tabela_auditoria} t
            LEFT JOIN {config.tabela_followups} f
              ON f.direcao = 'tiflux_para_glpi' AND f.id_origem = -t.id_glpi AND f.status = 'sucesso'
            WHERE t.status = 'sucesso' AND t.numero_tiflux = ANY(%s)
            """,
            (numeros_tiflux,),
        )
        return {numero: (id_glpi, tipo) for numero, id_glpi, tipo in cur.fetchall()}


def registrar_chamado_fechado_para_followups(conn: ConexaoDb, config: Config, id_glpi: int, solucionado: bool) -> None:
    """
    Marca (sem sincronizar nenhum followup) que este chamado foi conferido e
    está fechado no GLPI. Sem isso, um chamado fechado nunca ganharia uma
    linha na tabela de followups e ficaria pra sempre em primeiro lugar no
    rodízio de obter_chamados_para_varrer_followups (que ordena por última
    varredura), monopolizando o limite de chamados verificados por execução.
    Solucionado (GLPI 5) ganha marca própria: o requerente ainda pode recusar,
    então entra em toda execução junto com os abertos (GLPI #34759, spec 004);
    só 'fechado' (GLPI 6, definitivo) fica no lote limitado.
    Ex.: registrar_chamado_fechado_para_followups(conn, config, 34759, solucionado=True)
    """
    if solucionado:
        _registrar_verificacao_status(
            conn, config, id_glpi, None, "solucionado", "Chamado solucionado no GLPI — conferido a cada execução (recusa)",
        )
        return
    _registrar_verificacao_status(
        conn, config, id_glpi, None, "fechado", "Chamado fechado no GLPI — fora do escopo da varredura de followups",
    )


def registrar_chamado_aberto_varrido(
    conn: ConexaoDb, config: Config, id_glpi: int, numero_tiflux: NumeroTiflux | None,
) -> None:
    """
    Marca que os followups deste chamado aberto acabaram de ser varridos,
    mesmo sem nenhum followup novo. O rodízio de
    obter_chamados_para_varrer_followups ordena por MAX(atualizado_em) — sem
    essa marca, um chamado sem atividade nova ficava com timestamp velho e
    sempre na frente da fila, e um chamado recém-sincronizado ia pro fim e
    nunca mais era varrido (GLPI #34522: followup de terceiro nunca chegou
    ao Tiflux porque o chamado saiu do limite de 50 por execução).
    Ex.: registrar_chamado_aberto_varrido(conn, config, 34522, 363403)
    """
    _registrar_verificacao_status(
        conn, config, id_glpi, numero_tiflux, "aberto", "Chamado aberto no GLPI — followups varridos",
    )


def _registrar_verificacao_status(
    conn: ConexaoDb, config: Config, id_glpi: int, numero_tiflux: NumeroTiflux | None, status: str, mensagem: str,
) -> None:
    """Linha única por chamado (direcao='verificacao_status', id_origem=-id_glpi); o upsert atualiza atualizado_em a cada varredura."""
    registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, "verificacao_status", "status", -id_glpi, None, status, mensagem,
    )


# Linhas marcadoras da spec 008. status próprio ('marcador') pra nunca casar
# com os filtros por status='sucesso' das outras consultas.
_DIRECAO_CHECKPOINT = "checkpoint_tiflux"
_DIRECAO_VARREDURA_COMPLETA = "varredura_completa"
_STATUS_MARCADOR = "marcador"


def obter_checkpoint_tiflux(conn: ConexaoDb, config: Config) -> datetime | None:
    """
    Início (UTC) da última execução cujo panorama do Tiflux foi lido por
    inteiro (spec 008). None se nunca houve, ou se o valor gravado está ilegível.
    Ex.: obter_checkpoint_tiflux(conn, config) -> datetime(2026, 10, 7, 19, 30, tzinfo=timezone.utc)
    """
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT mensagem FROM {config.tabela_followups} WHERE direcao = %s AND id_origem = 0",
            (_DIRECAO_CHECKPOINT,),
        )
        linha = cur.fetchone()
    if not linha:
        return None
    try:
        return datetime.fromisoformat(linha[0])
    except (TypeError, ValueError):
        log(f"⚠️ Checkpoint do Tiflux ilegível ({linha[0]!r}, esperado ISO 8601 UTC) — usando a janela padrão")
        return None


def registrar_checkpoint_tiflux(conn: ConexaoDb, config: Config, inicio_utc: datetime) -> None:
    """
    Grava o checkpoint numa linha única (id_glpi=0, id_origem=0), ISO 8601 UTC
    em `mensagem` — `atualizado_em` é hora local sem fuso e não serve.
    Ex.: registrar_checkpoint_tiflux(conn, config, datetime.now(timezone.utc))
    """
    registrar_resultado_followup(
        conn, config, 0, None, _DIRECAO_CHECKPOINT, "checkpoint", 0, None, _STATUS_MARCADOR, inicio_utc.isoformat(),
    )


def obter_chamados_para_varredura_completa(conn: ConexaoDb, config: Config, quantidade: int) -> list[tuple[int, int]]:
    """
    Pares (id_glpi, numero_tiflux) dos `quantidade` chamados status='sucesso'
    conferidos por completo há mais tempo (nunca conferidos primeiro).
    Ex.: obter_chamados_para_varredura_completa(conn, config, 1) -> [(34759, 364160)]
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.id_glpi, t.numero_tiflux
            FROM {config.tabela_auditoria} t
            LEFT JOIN {config.tabela_followups} v
              ON v.direcao = %s AND v.id_origem = -t.id_glpi
            WHERE t.status = 'sucesso' AND t.numero_tiflux IS NOT NULL
            ORDER BY v.atualizado_em ASC NULLS FIRST, t.id_glpi ASC
            LIMIT %s
            """,
            (_DIRECAO_VARREDURA_COMPLETA, quantidade),
        )
        return [(id_glpi, numero) for id_glpi, numero in cur.fetchall()]


def registrar_varredura_completa(conn: ConexaoDb, config: Config, id_glpi: int, numero_tiflux: NumeroTiflux) -> None:
    """
    Marca o chamado como conferido por completo agora (linha única por chamado,
    id_origem=-id_glpi), mandando-o pro fim da fila da varredura de segurança.
    Ex.: registrar_varredura_completa(conn, config, 34759, 364160)
    """
    registrar_resultado_followup(
        conn, config, id_glpi, numero_tiflux, _DIRECAO_VARREDURA_COMPLETA, "status", -id_glpi, None,
        _STATUS_MARCADOR, "Chamado conferido por completo (varredura de segurança, spec 008)",
    )
