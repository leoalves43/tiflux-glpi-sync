"""Ligação panorama -> followups -> checkpoint em sync/main.py (spec 008)."""

import contextlib
import io
import unittest

from sync.config import Config
from sync.main import _sincronizar_followups_com_panorama
from sync.tiflux_client import ListagemTifluxIncompleta
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)


class TestSincronizarFollowupsComPanorama(unittest.TestCase):
    def test_panorama_incompleto_nao_varre_nem_avanca_checkpoint(self):
        tiflux = FakeTifluxClient()
        tiflux.falha_listagem_abertos = ListagemTifluxIncompleta("status 500", [])
        conn = FakeConnection()
        with contextlib.redirect_stdout(io.StringIO()):
            _sincronizar_followups_com_panorama(conn, _CONFIG, FakeGlpiClient(), tiflux)
        # Só a leitura do checkpoint: nem rodízio, nem gravação.
        self.assertEqual(len(conn.execucoes), 1)
        self.assertEqual(conn.commits, 0)

    def test_panorama_completo_varre_e_avanca_checkpoint(self):
        conn = FakeConnection()  # checkpoint, varredura completa e rodízio vazios
        _sincronizar_followups_com_panorama(conn, _CONFIG, FakeGlpiClient(), FakeTifluxClient())
        self.assertIn("checkpoint_tiflux", conn.execucoes[-1][1])


if __name__ == "__main__":
    unittest.main()
