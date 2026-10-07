"""Spec 004: recusa no GLPI não pode ser desfeita quando o Tiflux não reabre (GLPI #34759)."""

import contextlib
import io
import unittest

from sync.config import Config
from sync.sincronizacao_followups import sincronizar_followups
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)

_ERRO_403 = 'Falha ao reabrir ticket no Tiflux (403): {"error_code":40301}'


def _gravacoes(conn: FakeConnection) -> list[tuple]:
    """(direcao, tipo, id_origem, id_destino, status) de cada registrar_resultado_followup."""
    return [p[2:7] for _, p in conn.execucoes if p and len(p) >= 7]


class TestFalhaAoReabrirTiflux(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}  # recusado: aberto de novo no GLPI
        self.glpi.followups[1] = [{"id": 10, "content": "recusado", "is_private": 0, "users_id": 42}]
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 42)
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        self.tiflux.resultado_reabrir_ticket = (False, _ERRO_403)
        self.conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)]])
        self.saida = io.StringIO()
        with contextlib.redirect_stdout(self.saida):
            sincronizar_followups(self.conn, _CONFIG, self.glpi, self.tiflux)

    def test_nao_encerra_o_glpi_de_novo(self):
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_grava_falha_em_linha_propria_glpi_para_tiflux(self):
        self.assertIn(("glpi_para_tiflux", "reabertura_tiflux", -1, None, "erro"), _gravacoes(self.conn))

    def test_nao_altera_a_linha_de_cascata(self):
        self.assertFalse([g for g in _gravacoes(self.conn) if g[0] == "tiflux_para_glpi"])

    def test_loga_chamado_ticket_e_erro(self):
        log = self.saida.getvalue()
        for trecho in ("#1", "#T-1", "403", "manualmente"):
            self.assertIn(trecho, log)

    def test_nao_tenta_publicar_followup_no_tiflux(self):
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_marca_o_chamado_como_varrido(self):
        self.assertIn(("verificacao_status", "status", -1, None, "aberto"), _gravacoes(self.conn))


class TestReaberturaTifluxBemSucedida(unittest.TestCase):
    def test_grava_sucesso_nas_duas_linhas(self):
        glpi, tiflux = FakeGlpiClient(), FakeTifluxClient()
        glpi.tickets[1] = {"status": 1}
        tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)]])
        with contextlib.redirect_stdout(io.StringIO()):
            sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        gravacoes = _gravacoes(conn)
        self.assertIn(("glpi_para_tiflux", "reabertura_tiflux", -1, None, "sucesso"), gravacoes)
        self.assertIn(("tiflux_para_glpi", "reabertura_tiflux", -1, None, "sucesso"), gravacoes)


class TestEqualizaReaberturaManualDoTiflux(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}
        self.tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}

    def _sincronizar(self, ultima_acao: list[tuple]) -> list[tuple]:
        # Fila: rodízio, respostas já processadas no Tiflux, marca de
        # varredura, e por fim a última ação de cascata.
        conn = FakeConnection(respostas=[[(1, "T-1")], [], [], ultima_acao])
        with contextlib.redirect_stdout(io.StringIO()):
            sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux)
        return _gravacoes(conn)

    def test_cascata_encerramento_vira_reabertura_tiflux(self):
        gravacoes = self._sincronizar([("encerramento",)])
        self.assertIn(("tiflux_para_glpi", "reabertura_tiflux", -1, None, "sucesso"), gravacoes)

    def test_sem_encerramento_registrado_nao_grava_cascata(self):
        gravacoes = self._sincronizar([])
        self.assertFalse([g for g in gravacoes if g[0] == "tiflux_para_glpi"])

    def test_nao_reabre_nem_encerra_nada(self):
        self._sincronizar([("encerramento",)])
        self.assertEqual(self.tiflux.tickets_reabertos, [])
        self.assertEqual(self.glpi.chamados_encerrados, [])


class TestMarcaDeChamadoFechadoNoGlpi(unittest.TestCase):
    def _marca(self, status_glpi: int) -> str:
        glpi, tiflux = FakeGlpiClient(), FakeTifluxClient()
        glpi.tickets[1] = {"status": status_glpi}
        tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        with contextlib.redirect_stdout(io.StringIO()):
            sincronizar_followups(conn, _CONFIG, glpi, tiflux)
        return [g[4] for g in _gravacoes(conn) if g[0] == "verificacao_status"][0]

    def test_solucionado_recusavel_e_marcado_solucionado(self):
        # Fora do lote limitado de fechados: recusa notada na execução seguinte.
        self.assertEqual(self._marca(5), "solucionado")

    def test_fechado_definitivo_e_marcado_fechado(self):
        self.assertEqual(self._marca(6), "fechado")


if __name__ == "__main__":
    unittest.main()
