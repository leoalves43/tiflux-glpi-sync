"""Orquestrador de followups (sync/sincronizacao_followups.py)."""

import contextlib
import io
import unittest

from sync.config import Config
from sync.sincronizacao_followups import sincronizar_followups
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient
from tests.fakes import FakeConnection

_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)


class TestSincronizarFollowups(unittest.TestCase):
    def test_chamado_fechado_manualmente_no_glpi_e_pulado_e_marcado(self):
        # status 6 (Fechado) não é o status que a cascata usa (5, Solucionado)
        # — não é reaberto automaticamente, só marcado como fora do escopo.
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        glpi.tickets[1] = {"status": 6}
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        sql, params = conn.execucoes[-1]
        self.assertIn("verificacao_status", params)
        self.assertEqual(glpi.chamados_encerrados, [])

    def test_chamado_aberto_sem_followup_novo_e_marcado_como_varrido(self):
        # Regressão GLPI #34522: sem essa marca o rodízio (ORDER BY última
        # varredura) nunca mais voltava a um chamado recém-sincronizado.
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        glpi.tickets[1] = {"status": 1}
        tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        marcas = [p[2:7] for _, p in conn.execucoes if p and len(p) >= 7]
        self.assertIn(("verificacao_status", "status", -1, None, "aberto"), marcas)

    def test_chamado_sem_numero_tiflux_e_ignorado(self):
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        conn = FakeConnection(respostas=[[(1, None)]])
        sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        # única execução é a própria SELECT de candidatos — nada mais rodou
        self.assertEqual(len(conn.execucoes), 1)

    def test_mudanca_de_status_recente_entra_antes_do_rodizio_sem_repetir(self):
        # Encerramentos/reaberturas no Tiflux não esperam a vez no rodízio
        # (GLPI #34769 levou ~20 min pra fechar). Chamado que também está na
        # leva do rodízio roda uma vez só.
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        tiflux.tickets_atualizados = [{"ticket_number": 20, "is_closed": True}]
        glpi.tickets[2] = {"status": 6}
        glpi.tickets[1] = {"status": 6}
        conn = FakeConnection(respostas=[
            [(20, 2, None)],           # obter_chamados_por_numero_tiflux
            [(1, 10), (2, 20)],        # rodízio
        ])
        with _sem_console():
            sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        marcados = [params[0] for _, params in conn.execucoes[2:]]
        self.assertEqual(marcados, [2, 1])

    def test_falha_ao_conferir_status_pula_sem_quebrar(self):
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        with _sem_console():
            sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        # única execução é a própria SELECT de candidatos — nada mais rodou
        self.assertEqual(len(conn.execucoes), 1)


if __name__ == "__main__":
    unittest.main()
