"""TifluxClient: chamadas usadas só pela abertura Tiflux -> GLPI (spec 009)."""

import unittest

from sync.tiflux_client import TifluxClient
from tests.fakes import FakeRequests, FakeResponse

URL_BASE = "https://api.tiflux.com/api/v2"


def _client(fake: FakeRequests) -> TifluxClient:
    return TifluxClient(URL_BASE, "token", cliente_id=762707, id_solicitante_padrao=3758056, session=fake)


class TestRenomearTicket(unittest.TestCase):
    def test_sucesso_manda_so_o_titulo(self):
        fake = FakeRequests()
        fake.programar("PUT", "/tickets/364990", FakeResponse(200, {"ticket_number": 364990}))
        self.assertIsNone(_client(fake).renomear_ticket(364990, "Erro (35001)"))
        self.assertEqual(fake.chamadas[-1][2]["json"], {"title": "Erro (35001)"})

    def test_falha_devolve_erro_com_titulo_e_status(self):
        fake = FakeRequests()
        fake.programar("PUT", "/tickets/364990", FakeResponse(422, text="invalid"))
        erro = _client(fake).renomear_ticket(364990, "Erro (35001)")
        self.assertIn("'Erro (35001)'", erro)
        self.assertIn("422", erro)


class TestMoverParaEstagio(unittest.TestCase):
    def test_sucesso_manda_so_o_estagio(self):
        fake = FakeRequests()
        fake.programar("PUT", "/tickets/364990", FakeResponse(200, {"ticket_number": 364990}))
        self.assertIsNone(_client(fake).mover_para_estagio(364990, 233286))
        self.assertEqual(fake.chamadas[-1][2]["json"], {"stage_id": 233286})

    def test_falha_devolve_erro_com_estagio(self):
        fake = FakeRequests()
        fake.programar("PUT", "/tickets/364990", FakeResponse(422, text="invalid stage"))
        self.assertIn("estágio 233286 (422)", _client(fake).mover_para_estagio(364990, 233286))


class TestArquivosTicket(unittest.TestCase):
    def test_lista_arquivos_paginando(self):
        fake = FakeRequests()
        fake.programar("GET", "/tickets/364925/files", FakeResponse(200, [{"id": 1, "file_name": "a.jpg"}]))
        self.assertEqual(_client(fake).listar_arquivos_ticket(364925, 100, 5), [{"id": 1, "file_name": "a.jpg"}])

    def test_baixa_sem_o_token_do_tiflux(self):
        fake = FakeRequests()
        fake.programar("GET", "s3.amazonaws.com/a.jpg", FakeResponse(200, content=b"jpg"))
        self.assertEqual(_client(fake).baixar_arquivo("https://s3.amazonaws.com/a.jpg"), b"jpg")
        self.assertNotIn("headers", fake.chamadas[-1][2])

    def test_falha_no_download_devolve_none(self):
        fake = FakeRequests()
        fake.programar("GET", "s3.amazonaws.com/a.jpg", FakeResponse(403, text="expired"))
        self.assertIsNone(_client(fake).baixar_arquivo("https://s3.amazonaws.com/a.jpg"))


if __name__ == "__main__":
    unittest.main()
