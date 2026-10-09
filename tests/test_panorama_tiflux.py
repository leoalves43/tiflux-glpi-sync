"""Panorama do Tiflux por execução (sync/panorama_tiflux.py, spec 008)."""

import contextlib
import io
import unittest
from datetime import datetime, timedelta, timezone

from sync.config import Config
from sync.panorama_tiflux import concluir_panorama_tiflux, ler_panorama_tiflux
from sync.tiflux_client import ListagemTifluxIncompleta
from tests.fake_clients import FakeTifluxClient, panorama_de_teste
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)
_AGORA = datetime(2026, 10, 7, 19, 30, tzinfo=timezone.utc)
_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())


def _conn(checkpoint: str | None = None, varredura: list[tuple] | None = None) -> FakeConnection:
    # Ordem das consultas: checkpoint, [cruzamento de mudanças], varredura completa.
    return FakeConnection(respostas=[[(checkpoint,)] if checkpoint else [], varredura or []])


class TestJanelaDosAtualizados(unittest.TestCase):
    def test_sem_checkpoint_usa_janela_padrao(self):
        tiflux = FakeTifluxClient()
        ler_panorama_tiflux(_conn(), _CONFIG, tiflux, _AGORA)
        janela = timedelta(minutes=_CONFIG.janela_mudancas_status_tiflux_minutos)
        self.assertEqual(tiflux.inicios_listagem_atualizados, [_AGORA - janela])

    def test_com_checkpoint_volta_a_margem(self):
        # Parado por horas: a janela cobre desde a última execução bem-sucedida.
        tiflux = FakeTifluxClient()
        ler_panorama_tiflux(_conn("2026-10-07T10:00:00+00:00"), _CONFIG, tiflux, _AGORA)
        esperado = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc) - timedelta(minutes=5)
        self.assertEqual(tiflux.inicios_listagem_atualizados, [esperado])


class TestLerPanorama(unittest.TestCase):
    def test_monta_conjuntos_mudancas_e_varredura(self):
        tiflux = FakeTifluxClient()
        tiflux.tickets_abertos = [{"ticket_number": 7}, {"ticket_number": 8}]
        tiflux.tickets_atualizados = [{"ticket_number": 9, "is_closed": True}]
        conn = FakeConnection(respostas=[[], [(9, 3, None)], [(4, 40)]])
        panorama = ler_panorama_tiflux(conn, _CONFIG, tiflux, _AGORA)
        self.assertEqual(panorama.abertos, frozenset({7, 8}))
        self.assertEqual(panorama.atualizados, frozenset({9}))
        self.assertEqual(panorama.mudancas, ((3, 9),))
        self.assertEqual(panorama.varredura_completa, ((4, 40),))
        self.assertEqual(panorama.inicio_execucao_utc, _AGORA)

    def test_tickets_listados_um_por_numero_para_a_abertura(self):
        # Spec 009: aberto e atualizado ao mesmo tempo aparece uma vez só.
        tiflux = FakeTifluxClient()
        tiflux.tickets_abertos = [{"ticket_number": 7, "title": "aberto"}]
        tiflux.tickets_atualizados = [{"ticket_number": 7, "title": "atualizado"}, {"ticket_number": 9}]
        panorama = ler_panorama_tiflux(_conn(), _CONFIG, tiflux, _AGORA)
        self.assertEqual(panorama.tickets_listados, ({"ticket_number": 7, "title": "atualizado"}, {"ticket_number": 9}))

    def test_falha_nos_atualizados_devolve_none(self):
        tiflux = FakeTifluxClient()
        tiflux.falha_listagem_atualizados = ListagemTifluxIncompleta("status 429", [])
        with _sem_console() as saida:
            self.assertIsNone(ler_panorama_tiflux(_conn(), _CONFIG, tiflux, _AGORA))
        self.assertIn("429", saida.getvalue())

    def test_falha_nos_abertos_devolve_none_mesmo_com_lista_vazia_valida(self):
        # Critério 5/6: uma falha nunca vira "nenhum ticket aberto".
        tiflux = FakeTifluxClient()
        tiflux.falha_listagem_abertos = ListagemTifluxIncompleta("rede fora", [])
        with _sem_console():
            self.assertIsNone(ler_panorama_tiflux(_conn(), _CONFIG, tiflux, _AGORA))


class TestConcluirPanorama(unittest.TestCase):
    def test_avanca_checkpoint_pro_inicio_da_execucao(self):
        # Falhas por chamado não seguram o checkpoint: viram retentativa na
        # varredura completa (test_sincronizacao_followups.TestRetentativaPorChamado).
        conn = FakeConnection()
        concluir_panorama_tiflux(conn, _CONFIG, panorama_de_teste())
        params = conn.execucoes[0][1]
        self.assertEqual((params[2], params[7]), ("checkpoint_tiflux", "2026-10-07T19:30:00+00:00"))


if __name__ == "__main__":
    unittest.main()
