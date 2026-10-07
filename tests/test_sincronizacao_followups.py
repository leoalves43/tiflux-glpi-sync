"""Orquestrador de followups (sync/sincronizacao_followups.py)."""

import contextlib
import io
import unittest

from sync.config import Config
from sync.main import _sincronizar_followups_com_panorama
from sync.sincronizacao_followups import conferir_por_completo, sincronizar_followups
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient, FakeTifluxClientContador, panorama_de_teste
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
        sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste())
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
        sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste())
        marcas = [p[2:7] for _, p in conn.execucoes if p and len(p) >= 7]
        self.assertIn(("verificacao_status", "status", -1, None, "aberto"), marcas)

    def test_chamado_sem_numero_tiflux_e_ignorado(self):
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        conn = FakeConnection(respostas=[[(1, None)]])
        sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste())
        # única execução é a própria SELECT de candidatos — nada mais rodou
        self.assertEqual(len(conn.execucoes), 1)

    def test_mudanca_de_status_recente_entra_antes_do_rodizio_sem_repetir(self):
        # Encerramentos/reaberturas no Tiflux não esperam a vez no rodízio
        # (GLPI #34769 levou ~20 min pra fechar). Chamado que também está na
        # leva do rodízio roda uma vez só.
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        glpi.tickets[2] = {"status": 6}
        glpi.tickets[1] = {"status": 6}
        conn = FakeConnection(respostas=[[(1, 10), (2, 20)]])  # rodízio
        with _sem_console():
            sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste(mudancas=((2, 20),)))
        marcados = [params[0] for _, params in conn.execucoes[1:]]
        self.assertEqual(marcados, [2, 1])

    def test_falha_ao_conferir_status_pula_sem_quebrar(self):
        glpi = FakeGlpiClient()
        tiflux = FakeTifluxClient()
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        with _sem_console():
            sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste())
        # única execução é a própria SELECT de candidatos — nada mais rodou
        self.assertEqual(len(conn.execucoes), 1)



def _gravacoes(conn: FakeConnection) -> list[tuple]:
    """(direcao, tipo, id_origem, id_destino, status) de cada registrar_resultado_followup."""
    return [p[2:7] for _, p in conn.execucoes if p and len(p) >= 7]


class TestExecucaoSemMudancas(unittest.TestCase):
    """Spec 008, critério 1: execução sem mudanças custa no máximo 5 requisições ao Tiflux."""

    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClientContador()
        self.tiflux.tickets_abertos = [{"ticket_number": 10}, {"ticket_number": 11}]
        self.glpi.tickets.update({1: {"status": 2}, 2: {"status": 1}, 3: {"status": 6}, 4: {"status": 5}})
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[
            [],                                       # checkpoint
            [(3, 30)],                                # varredura completa
            [(1, 10), (2, 11), (3, 30), (4, 40)],     # rodízio
        ])
        _sincronizar_followups_com_panorama(conn, _CONFIG, self.glpi, self.tiflux)

    def test_no_maximo_cinco_requisicoes(self):
        self.assertLessEqual(len(self.tiflux.requisicoes), 5, self.tiflux.requisicoes)

    def test_so_a_varredura_de_seguranca_le_ticket_individual(self):
        self.assertEqual(self.tiflux.requisicoes.count("obter_ticket"), 1)
        self.assertNotIn("listar_respostas", self.tiflux.requisicoes)


class TestCaminhoPeloPanorama(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClientContador()
        self.glpi.tickets[1] = {"status": 2}

    def _sincronizar(self, panorama, respostas_db=None) -> FakeConnection:
        conn = FakeConnection(respostas=respostas_db or [[(1, 10)]])
        with _sem_console():
            sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama)
        return conn

    def test_resposta_nova_no_tiflux_chega_ao_glpi_sem_get_individual(self):
        # Critério 2: ticket atualizado desde o checkpoint -> /answers.
        self.tiflux.respostas = [{"id": 5, "name": "resposta por e-mail"}]
        self._sincronizar(panorama_de_teste(abertos=(10,), atualizados=(10,)))
        self.assertEqual(len(self.glpi.followups_criados), 1)
        self.assertNotIn("obter_ticket", self.tiflux.requisicoes)

    def test_ticket_nao_atualizado_nao_lista_respostas(self):
        self.tiflux.respostas = [{"id": 5, "name": "já vista"}]
        conn = self._sincronizar(panorama_de_teste(abertos=(10,)))
        self.assertEqual(self.tiflux.requisicoes, [])
        self.assertIn(("verificacao_status", "status", -1, None, "aberto"), _gravacoes(conn))

    def test_followup_do_glpi_segue_para_o_tiflux(self):
        # Critério 8.
        self.glpi.followups[1] = [{"id": 77, "content": "novo", "is_private": 0, "users_id": 42}]
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 42)
        self._sincronizar(panorama_de_teste(abertos=(10,)))
        self.assertEqual(len(self.tiflux.publicacoes), 1)

    def test_encerrado_no_tiflux_e_confirmado_antes_da_cascata(self):
        # Critério 3: mudança recente -> leitura individual -> encerra no GLPI.
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        self._sincronizar(panorama_de_teste(mudancas=((1, 10),)), [[(1, 10)], [], []])
        self.assertIn("obter_ticket", self.tiflux.requisicoes)
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 5)])

    def test_fora_da_lista_de_abertos_so_fecha_se_a_leitura_confirmar(self):
        # Critério 6: a leitura individual diz aberto -> nada é encerrado.
        self.tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        self._sincronizar(panorama_de_teste(), [[(1, 10)], [], []])
        self.assertIn("obter_ticket", self.tiflux.requisicoes)
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_recusa_no_glpi_reabre_o_tiflux(self):
        # Critério 4: GLPI aberto de novo, Tiflux fechado, cascata 'encerramento'.
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        self._sincronizar(panorama_de_teste(), [[(1, 10)], [("encerramento",)]])
        self.assertEqual([n for n, _ in self.tiflux.tickets_reabertos], [10])

    def test_solucionado_fechado_nos_dois_lados_so_ganha_a_marca(self):
        self.glpi.tickets[1] = {"status": 5}
        conn = self._sincronizar(panorama_de_teste())
        self.assertEqual(self.tiflux.requisicoes, [])
        self.assertIn(("verificacao_status", "status", -1, None, "solucionado"), _gravacoes(conn))


class TestVarreduraDeSeguranca(unittest.TestCase):
    """Critério 7: o chamado da vez é conferido por completo e vai pro fim da fila."""

    def test_confere_por_completo_e_marca(self):
        glpi, tiflux = FakeGlpiClient(), FakeTifluxClientContador()
        glpi.tickets[1] = {"status": 2}
        tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, 10)]])
        sincronizar_followups(conn, _CONFIG, glpi, tiflux, panorama_de_teste(abertos=(10,), varredura_completa=((1, 10),)))
        self.assertEqual(tiflux.requisicoes[:2], ["obter_ticket", "listar_respostas"])
        self.assertEqual(_gravacoes(conn)[-1][:3], ("varredura_completa", "status", -1))

    def test_falha_no_glpi_nao_marca(self):
        conn = FakeConnection(respostas=[[]])
        with _sem_console():
            sincronizar_followups(
                conn, _CONFIG, FakeGlpiClient(), FakeTifluxClient(), panorama_de_teste(varredura_completa=((1, 10),)),
            )
        self.assertFalse([g for g in _gravacoes(conn) if g[0] == "varredura_completa"])


class TestConferirPorCompleto(unittest.TestCase):
    def test_aberto_nos_dois_lados_dispensa_leitura(self):
        self.assertFalse(conferir_por_completo(1, 10, {"status": 2}, panorama_de_teste(abertos=(10,))))

    def test_aberto_no_glpi_e_fora_dos_abertos_exige_leitura(self):
        self.assertTrue(conferir_por_completo(1, 10, {"status": 2}, panorama_de_teste()))

    def test_solucionado_e_aberto_no_tiflux_exige_leitura(self):
        self.assertTrue(conferir_por_completo(1, 10, {"status": 5}, panorama_de_teste(abertos=(10,))))

    def test_fechado_no_glpi_e_fora_dos_abertos_dispensa_leitura(self):
        self.assertFalse(conferir_por_completo(1, 10, {"status": 6}, panorama_de_teste()))

    def test_mudanca_recente_exige_leitura_mesmo_concordando(self):
        panorama = panorama_de_teste(abertos=(10,), mudancas=((1, 10),))
        self.assertTrue(conferir_por_completo(1, 10, {"status": 2}, panorama))


if __name__ == "__main__":
    unittest.main()
