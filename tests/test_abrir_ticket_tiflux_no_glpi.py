import unittest
from datetime import datetime, timezone

from sync.abrir_ticket_tiflux_no_glpi import simular_abertura
from sync.config import Config
from tests.fake_clients import FakeGlpiAberturaClient, FakeTifluxClient

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
    abertura_tiflux_desde=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
)
_TICKET = {
    "ticket_number": 364990, "client": {"id": 762707}, "desk": {"id": 37965}, "created_at": "2026-10-10T13:00:00Z", "title": "Empenho",
    "requestor": {"email": "a@x.gov.br", "telephone": ""}, "description": "<p>x</p>",
}


class TestSimularAbertura(unittest.TestCase):
    def setUp(self):
        self.tiflux = FakeTifluxClient()
        self.glpi_abertura = FakeGlpiAberturaClient()

    def test_mostra_payload_sem_escrever(self):
        self.tiflux.tickets_por_numero[364990] = _TICKET
        texto = simular_abertura(_CONFIG, self.glpi_abertura, self.tiflux, 364990, set())
        self.assertIn("Candidato: sim", texto)
        self.assertIn('"itilcategories_id": 277', texto)
        self.assertIn("Telefone no plugin: 1238971100", texto)
        self.assertEqual((self.glpi_abertura.chamados_criados, self.tiflux.renomeados), ([], []))

    def test_avisa_quando_nao_seria_aberto(self):
        self.tiflux.tickets_por_numero[364990] = _TICKET
        self.assertIn("NÃO (seria ignorado)", simular_abertura(_CONFIG, self.glpi_abertura, self.tiflux, 364990, {364990}))

    def test_ticket_ilegivel(self):
        self.tiflux.tickets_por_numero[1] = _TICKET
        self.assertIn("não lido (status 404)", simular_abertura(_CONFIG, self.glpi_abertura, self.tiflux, 364990, set()))


if __name__ == "__main__":
    unittest.main()
