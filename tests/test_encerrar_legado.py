import unittest

from sync.config import Config
from sync.encerrar_legado import encerrar_legado, motivo_recusa
from sync.sincronizacao_followups import STATUS_GLPI_SOLUCIONADO
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="siap.api_glpi_tiflux", tabela_followups="siap.api_glpi_tiflux_followups",
)

_ID_GLPI = 33500
_NUMERO_TIFLUX = "360123"


class TestMotivoRecusa(unittest.TestCase):
    def test_tiflux_aberto_recusa(self):
        self.assertIn("ainda está aberto", motivo_recusa({"status": 2}, {"is_closed": False}, _ID_GLPI, _NUMERO_TIFLUX))

    def test_glpi_ja_solucionado_recusa(self):
        self.assertIn("já não está aberto", motivo_recusa({"status": 5}, {"is_closed": True}, _ID_GLPI, _NUMERO_TIFLUX))

    def test_tiflux_fechado_e_glpi_aberto_permite(self):
        self.assertIsNone(motivo_recusa({"status": 1}, {"is_closed": True}, _ID_GLPI, _NUMERO_TIFLUX))


class TestEncerrarLegado(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.glpi = FakeGlpiClient()
        self.glpi.tickets[_ID_GLPI] = {"name": "Erro no sistema", "status": 2}
        self.tiflux = FakeTifluxClient()
        self.tiflux.ticket_tiflux = {"title": "Erro no sistema (33500)", "is_closed": True}
        self.tiflux.respostas = [
            {"id": 1, "name": "primeira", "author": "Ana", "answer_time": "2026-05-01T10:00:00Z"},
            {"id": 2, "name": "resolvido", "author": "Bruno", "answer_time": "2026-05-02T10:00:00Z"},
        ]

    def _encerrar(self):
        return encerrar_legado(self.conn, _CONFIG, self.glpi, self.tiflux, _ID_GLPI, _NUMERO_TIFLUX)

    def test_encerra_com_ultima_resposta_do_tecnico_como_solucao(self):
        status, mensagem = self._encerrar()
        self.assertEqual(status, "sucesso")
        self.assertEqual(self.glpi.chamados_encerrados, [(_ID_GLPI, STATUS_GLPI_SOLUCIONADO)])
        self.assertEqual(self.glpi.solucoes_registradas, [(_ID_GLPI, "<strong>Bruno</strong> (02/05/2026 07:00)<br><br>resolvido")])
        self.assertIn("Erro no sistema (33500)", mensagem)

    def test_atribui_tecnico_quando_glpi_nao_tem(self):
        self._encerrar()
        self.assertEqual(self.glpi.tecnicos_atribuidos_glpi, [(_ID_GLPI, _CONFIG.id_glpi_leo)])

    def test_nao_sincroniza_historico_nem_grava_vinculo_na_auditoria(self):
        self._encerrar()
        self.assertEqual(self.glpi.followups_criados, [])
        self.assertEqual(self.tiflux.publicacoes, [])
        sqls = " ".join(sql for sql, _ in self.conn.execucoes)
        self.assertNotIn("siap.api_glpi_tiflux ", sqls)

    def test_tiflux_aberto_recusa_sem_mexer_no_glpi(self):
        self.tiflux.ticket_tiflux = {"title": "x", "is_closed": False}
        status, _ = self._encerrar()
        self.assertEqual(status, "recusado")
        self.assertEqual((self.glpi.chamados_encerrados, self.glpi.solucoes_registradas), ([], []))

    def test_glpi_ja_fechado_recusa(self):
        self.glpi.tickets[_ID_GLPI]["status"] = 6
        status, _ = self._encerrar()
        self.assertEqual(status, "recusado")
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_chamado_glpi_inexistente_e_erro(self):
        del self.glpi.tickets[_ID_GLPI]
        status, mensagem = self._encerrar()
        self.assertEqual(status, "erro")
        self.assertIn(str(_ID_GLPI), mensagem)

    def test_ticket_tiflux_inexistente_e_erro(self):
        self.tiflux.ticket_tiflux = None
        status, mensagem = self._encerrar()
        self.assertEqual(status, "erro")
        self.assertIn(_NUMERO_TIFLUX, mensagem)

    def test_glpi_recusando_status_vira_erro(self):
        self.glpi.resultado_encerrar_chamado = (False, "Falha: sem solução")
        status, _ = self._encerrar()
        self.assertEqual(status, "erro")


if __name__ == "__main__":
    unittest.main()
