import contextlib
import io
import json
import unittest

import requests

from sync.glpi_abertura_client import GlpiAberturaClient, ResultadoCriacaoGlpi
from tests.fakes import FakeRequests, FakeResponse

URL_BASE = "https://glpi.example/apirest.php"
_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())


def _client(fake: FakeRequests) -> GlpiAberturaClient:
    return GlpiAberturaClient(URL_BASE, {"Session-Token": "sess"}, fake, 30)


class FakeRequestsSemRede(FakeRequests):
    """POST que estoura timeout: o GLPI pode ou não ter criado o chamado."""

    def post(self, url, **kwargs):
        raise requests.Timeout("read timeout")


class TestBuscarUsuarioPorEmail(unittest.TestCase):
    def test_email_exato_sem_caixa_devolve_usuario(self):
        fake = FakeRequests()
        fake.programar("GET", "/UserEmail", FakeResponse(200, [
            {"users_id": 173, "email": "Paula.Avila@x.gov.br"}, {"users_id": 9, "email": "paula.avila@x.gov.br.old"},
        ]))
        self.assertEqual(_client(fake).buscar_usuario_por_email("paula.avila@x.gov.br"), 173)

    def test_sem_correspondencia_ou_sem_email_devolve_none(self):
        fake = FakeRequests()
        fake.programar("GET", "/UserEmail", FakeResponse(200, []))
        self.assertIsNone(_client(fake).buscar_usuario_por_email("ninguem@x.com"))
        self.assertIsNone(_client(fake).buscar_usuario_por_email(None))

    def test_email_de_dois_usuarios_devolve_none(self):
        fake = FakeRequests()
        fake.programar("GET", "/UserEmail", FakeResponse(200, [
            {"users_id": 1, "email": "a@x.com"}, {"users_id": 2, "email": "a@x.com"},
        ]))
        with _sem_console():
            self.assertIsNone(_client(fake).buscar_usuario_por_email("a@x.com"))

    def test_falha_http_devolve_none(self):
        fake = FakeRequests()
        fake.programar("GET", "/UserEmail", FakeResponse(500, text="boom"))
        with _sem_console():
            self.assertIsNone(_client(fake).buscar_usuario_por_email("a@x.com"))


class TestCriarChamado(unittest.TestCase):
    def test_sucesso_devolve_id_e_manda_input_wrapper(self):
        fake = FakeRequests()
        fake.programar("POST", "/Ticket", FakeResponse(201, {"id": 35001, "message": ""}))
        resultado = _client(fake).criar_chamado({"name": "#1 - x"})
        self.assertEqual(resultado, ResultadoCriacaoGlpi(35001, None, False))
        self.assertEqual(fake.chamadas[-1][2]["json"], {"input": {"name": "#1 - x"}})

    def test_recusa_4xx_e_certa(self):
        fake = FakeRequests()
        fake.programar("POST", "/Ticket", FakeResponse(400, text='["ERROR_GLPI_ADD"]'))
        resultado = _client(fake).criar_chamado({})
        self.assertEqual((resultado.id_glpi, resultado.incerto), (None, False))
        self.assertIn("400", resultado.erro)

    def test_5xx_ou_resposta_sem_id_e_incerto(self):
        for resposta in (FakeResponse(502, text="bad gateway"), FakeResponse(201, {"message": ""})):
            fake = FakeRequests()
            fake.programar("POST", "/Ticket", resposta)
            resultado = _client(fake).criar_chamado({})
            self.assertEqual((resultado.id_glpi, resultado.incerto), (None, True))

    def test_timeout_e_incerto(self):
        resultado = _client(FakeRequestsSemRede()).criar_chamado({})
        self.assertEqual((resultado.id_glpi, resultado.incerto), (None, True))
        self.assertIn("read timeout", resultado.erro)


class TestGravarTelefone(unittest.TestCase):
    def test_sem_linha_do_plugin_cria_uma(self):
        fake = FakeRequests()
        fake.programar("GET", "/PluginFieldsTickettelefonelinha", FakeResponse(200, []))
        fake.programar("POST", "/PluginFieldsTickettelefonelinha", FakeResponse(201, {"id": 5}))
        self.assertIsNone(_client(fake).gravar_telefone(35001, "1238971100"))
        entrada = fake.chamadas[-1][2]["json"]["input"]
        self.assertEqual((entrada["items_id"], entrada["telefonefield"], entrada["itemtype"]), (35001, "1238971100", "Ticket"))

    def test_linha_existente_do_chamado_e_atualizada(self):
        fake = FakeRequests()
        fake.programar("GET", "/PluginFieldsTickettelefonelinha", FakeResponse(200, [
            {"id": 7, "itemtype": "Ticket", "items_id": 350011}, {"id": 8, "itemtype": "Ticket", "items_id": 35001},
        ]))
        fake.programar("PUT", "/PluginFieldsTickettelefonelinha/8", FakeResponse(200, [{"8": True}]))
        self.assertIsNone(_client(fake).gravar_telefone(35001, "1238971100"))
        self.assertEqual(fake.chamadas[-1][2]["json"], {"input": {"telefonefield": "1238971100"}})

    def test_falha_devolve_erro_com_telefone(self):
        fake = FakeRequests()
        fake.programar("GET", "/PluginFieldsTickettelefonelinha", FakeResponse(200, []))
        fake.programar("POST", "/PluginFieldsTickettelefonelinha", FakeResponse(400, text="campo"))
        self.assertIn("1238971100", _client(fake).gravar_telefone(35001, "1238971100"))


class TestAnexarDocumento(unittest.TestCase):
    def test_manifesto_vincula_ao_chamado(self):
        fake = FakeRequests()
        fake.programar("POST", "/Document", FakeResponse(201, {"id": 900}))
        self.assertIsNone(_client(fake).anexar_documento(35001, "print.png", b"png", "image/png"))
        arquivos = fake.chamadas[-1][2]["files"]
        manifesto = json.loads(arquivos["uploadManifest"][1])["input"]
        self.assertEqual((manifesto["itemtype"], manifesto["items_id"]), ("Ticket", 35001))
        self.assertEqual(arquivos["filename[0]"], ("print.png", b"png", "image/png"))

    def test_falha_devolve_erro_com_nome(self):
        fake = FakeRequests()
        fake.programar("POST", "/Document", FakeResponse(400, text="tipo"))
        self.assertIn("print.png", _client(fake).anexar_documento(35001, "print.png", b"png", "image/png"))


if __name__ == "__main__":
    unittest.main()
