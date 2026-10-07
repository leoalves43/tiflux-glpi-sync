"""Funções extraídas na refatoração 005 (sem mudança de comportamento) — cada uma com teste próprio."""

import contextlib
import io
import unittest

from sync.config import Config
from sync.forcar_sincronizacao import _chamado_aberto_no_glpi, _recusar_titulo_ja_sincronizado
from sync.main import _registrar_processamento
from sync.processamento_chamado import _descricao_tiflux, _mensagem_criacao, _TicketPlanejado
from sync.publicacao_followups import _interpretar_publicacao_no_tiflux
from sync.tiflux_client import _cabecalhos_tiflux
from tests.fake_clients import FakeGlpiClient
from tests.fakes import FakeConnection, FakeResponse

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)


class TestCabecalhosTiflux(unittest.TestCase):
    def test_get_e_form_sem_content_type(self):
        json_, form, get = _cabecalhos_tiflux("abc")
        self.assertEqual(json_["Content-Type"], "application/json")
        self.assertNotIn("Content-Type", form)
        self.assertNotIn("Content-Type", get)
        self.assertEqual(get["Authorization"], "Bearer abc")


class TestInterpretarPublicacaoNoTiflux(unittest.TestCase):
    def test_sucesso_com_avisos(self):
        resp = FakeResponse(201, {"id": 9})
        self.assertEqual(
            _interpretar_publicacao_no_tiflux(resp, 77817, ["grande.pdf acima do limite"]),
            (9, "Followup GLPI #77817 publicado no Tiflux (id 9) | Avisos anexos: grande.pdf acima do limite"),
        )

    def test_falha_http(self):
        id_destino, mensagem = _interpretar_publicacao_no_tiflux(FakeResponse(422, text="closed"), 1, [])
        self.assertIsNone(id_destino)
        self.assertEqual(mensagem, "Falha ao publicar followup no Tiflux (422): closed")

    def test_resposta_sem_id(self):
        id_destino, mensagem = _interpretar_publicacao_no_tiflux(FakeResponse(200, {}), 1, [])
        self.assertIsNone(id_destino)
        self.assertIn("não foi possível identificar o id", mensagem)


class TestMensagemCriacao(unittest.TestCase):
    def test_sem_tecnico_e_com_avisos(self):
        planejado = _TicketPlanejado(37963, 120547, None, None, "Fulano (Existente)", {})
        self.assertEqual(
            _mensagem_criacao(planejado, "364569", " | Anexos: 1 enviado(s)"),
            "Ticket #364569 criado no Tiflux | Mesa 37963 | Prioridade ID 120547 | Sem técnico atribuído | "
            "Solicitante Fulano (Existente) | Anexos: 1 enviado(s)",
        )

    def test_com_tecnico(self):
        planejado = _TicketPlanejado(37964, 120549, 7, "Léo Alves", "X", {})
        self.assertIn("| Técnico Léo Alves |", _mensagem_criacao(planejado, "1", ""))


class TestDescricaoTiflux(unittest.TestCase):
    def test_monta_cabecalho_solicitante_e_descricao_em_html(self):
        descricao = _descricao_tiflux({"priority": 3, "content": "erro"}, "Fulano", None)
        self.assertIn("Solicitante: Fulano &lt;Sem e-mail&gt;<br><br>Descrição:<br>erro", descricao)


class TestRegistrarProcessamento(unittest.TestCase):
    def _registrar(self, status: str) -> tuple[str, FakeConnection]:
        conn = FakeConnection()
        with contextlib.redirect_stdout(io.StringIO()):
            categoria = _registrar_processamento(conn, _CONFIG, 1, status, "T-1", "msg")
        return categoria, conn

    def test_ignorado_nao_grava(self):
        categoria, conn = self._registrar("ignorado")
        self.assertEqual((categoria, conn.execucoes), ("ignorado", []))

    def test_sucesso_grava(self):
        categoria, conn = self._registrar("sucesso")
        self.assertEqual((categoria, len(conn.execucoes)), ("sucesso", 1))

    def test_outro_status_conta_como_erro_e_grava(self):
        categoria, conn = self._registrar("erro")
        self.assertEqual((categoria, len(conn.execucoes)), ("erro", 1))


class TestPreChecagensDoForcar(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()

    def _silencioso(self, funcao, *args) -> bool:
        with contextlib.redirect_stdout(io.StringIO()):
            return funcao(*args)

    def test_titulo_prefixado_e_recusado(self):
        self.glpi.tickets[1] = {"name": "#364160 - Relatório", "status": 2}
        self.assertTrue(self._silencioso(_recusar_titulo_ja_sincronizado, self.glpi, 1))

    def test_titulo_sem_prefixo_segue(self):
        self.glpi.tickets[1] = {"name": "Relatório", "status": 2}
        self.assertFalse(self._silencioso(_recusar_titulo_ja_sincronizado, self.glpi, 1))

    def test_chamado_fechado_no_glpi_nao_segue(self):
        self.glpi.tickets[1] = {"status": 6}
        self.assertFalse(self._silencioso(_chamado_aberto_no_glpi, self.glpi, 1, "T-1"))

    def test_chamado_aberto_no_glpi_segue(self):
        self.glpi.tickets[1] = {"status": 2}
        self.assertTrue(self._silencioso(_chamado_aberto_no_glpi, self.glpi, 1, "T-1"))


if __name__ == "__main__":
    unittest.main()
