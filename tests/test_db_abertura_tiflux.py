import unittest

from sync import db_abertura_tiflux
from sync.config import Config
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="siap.api_glpi_tiflux", tabela_followups="siap.api_glpi_tiflux_followups",
)


def _linha_gravada(conn: FakeConnection) -> tuple:
    """(id_glpi, numero_tiflux, direcao, tipo, id_origem, id_destino, status, mensagem) do último upsert."""
    return conn.execucoes[-1][1]


class TestObterEstadosAbertura(unittest.TestCase):
    def test_mapeia_numero_para_status_filtrando_a_direcao(self):
        conn = FakeConnection(respostas=[[(364990, "sucesso"), (364991, "pendente")]])
        estados = db_abertura_tiflux.obter_estados_abertura(conn, _CONFIG)
        self.assertEqual(estados, {364990: "sucesso", 364991: "pendente"})
        self.assertEqual(conn.execucoes[0][1], ("abertura_tiflux",))


class TestObterNumerosTifluxNaAuditoria(unittest.TestCase):
    def test_qualquer_status_conta_e_vira_inteiro(self):
        conn = FakeConnection(respostas=[[(364569,), ("364678",)]])
        self.assertEqual(db_abertura_tiflux.obter_numeros_tiflux_na_auditoria(conn, _CONFIG), {364569, 364678})
        self.assertNotIn("status", conn.execucoes[0][0])


class TestRegistrarAbertura(unittest.TestCase):
    def test_intencao_grava_pendente_com_id_origem_no_numero(self):
        conn = FakeConnection()
        db_abertura_tiflux.registrar_intencao_abertura(conn, _CONFIG, 364990)
        self.assertEqual(_linha_gravada(conn)[:7], (0, 364990, "abertura_tiflux", "abertura", 364990, None, "pendente"))
        self.assertEqual(conn.commits, 1)

    def test_sucesso_guarda_id_glpi_em_id_destino(self):
        conn = FakeConnection()
        db_abertura_tiflux.registrar_abertura_sucesso(conn, _CONFIG, 364990, 35001)
        self.assertEqual(_linha_gravada(conn)[:7], (35001, 364990, "abertura_tiflux", "abertura", 364990, 35001, "sucesso"))

    def test_erro_guarda_mensagem_sem_id_destino(self):
        conn = FakeConnection()
        db_abertura_tiflux.registrar_abertura_erro(conn, _CONFIG, 364990, "GLPI recusou (400)")
        self.assertEqual(_linha_gravada(conn)[5:], (None, "erro", "GLPI recusou (400)"))


if __name__ == "__main__":
    unittest.main()
