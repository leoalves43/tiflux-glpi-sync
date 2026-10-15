"""Validações do GLPI publicadas no Tiflux (sync/validacoes_glpi.py, spec 013)."""

import unittest
from dataclasses import replace

from sync.config import Config
from sync.validacoes_glpi import DIRECAO_PEDIDO, DIRECAO_RESPOSTA, publicar_validacoes_no_tiflux
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient, _FakeHttpResponse
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y", validacao_glpi_desde_id=1474,
)
_SOLICITANTE, _VALIDADOR = 1883, 4867


def _validacao(id_validacao: int = 1474, status: int = 2, comentario_resposta: str | None = None) -> dict:
    return {
        "id": id_validacao, "users_id": _SOLICITANTE, "users_id_validate": _VALIDADOR, "status": status,
        "comment_submission": "&#60;p&#62;Favor validar permissão&#60;/p&#62;", "comment_validation": comentario_resposta,
    }


def _inserts(conn: FakeConnection) -> list[tuple]:
    """(direcao, id_origem, status) de cada gravação na auditoria."""
    return [(p[2], p[4], p[6]) for sql, p in conn.execucoes if sql.lstrip().startswith("INSERT")]


class TestPublicarValidacoesNoTiflux(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.glpi.nomes_usuarios = {_SOLICITANTE: "Mirella", _VALIDADOR: "Gestor SEFAZ"}
        self.tiflux = FakeTifluxClient()

    def _publicar(self, conn: FakeConnection, config: Config = _CONFIG) -> tuple[int, int]:
        return publicar_validacoes_no_tiflux(conn, config, self.glpi, self.tiflux, 35092, 365227)

    def test_pedido_vira_resposta_com_validador_comentario_e_autor_solicitante(self):
        self.glpi.validacoes[35092] = [_validacao()]
        conn = FakeConnection(respostas=[[], []])
        self.assertEqual(self._publicar(conn), (1, 0))
        _, numero, conteudo, autor, _ = self.tiflux.publicacoes[0]
        self.assertEqual((numero, autor), (365227, "Mirella"))
        self.assertIn("🔐 Validação solicitada a Gestor SEFAZ", conteudo)
        self.assertIn("<p>Favor validar permissão</p>", conteudo)
        self.assertEqual(_inserts(conn), [(DIRECAO_PEDIDO, 1474, "sucesso")])

    def test_aprovacao_publica_resposta_com_autor_validador(self):
        self.glpi.validacoes[35092] = [_validacao(status=3, comentario_resposta="ok, liberado")]
        conn = FakeConnection(respostas=[[(1474,)], []])
        self.assertEqual(self._publicar(conn), (1, 0))
        _, _, conteudo, autor, _ = self.tiflux.publicacoes[0]
        self.assertEqual(autor, "Gestor SEFAZ")
        self.assertIn("✅ Validação aprovada por Gestor SEFAZ", conteudo)
        self.assertIn("ok, liberado", conteudo)
        self.assertEqual(_inserts(conn), [(DIRECAO_RESPOSTA, 1474, "sucesso")])

    def test_recusa_publica_resposta_de_recusa(self):
        self.glpi.validacoes[35092] = [_validacao(status=4)]
        self._publicar(FakeConnection(respostas=[[(1474,)], []]))
        self.assertIn("❌ Validação recusada por Gestor SEFAZ", self.tiflux.publicacoes[0][2])

    def test_ja_publicado_nao_publica_de_novo(self):
        self.glpi.validacoes[35092] = [_validacao(status=3)]
        conn = FakeConnection(respostas=[[(1474,)], [(1474,)]])
        self.assertEqual(self._publicar(conn), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_duas_validacoes_geram_eventos_separados(self):
        self.glpi.validacoes[35092] = [_validacao(1480), _validacao(1474)]
        conn = FakeConnection(respostas=[[], []])
        self.assertEqual(self._publicar(conn), (2, 0))
        self.assertEqual([i for _, i, _ in _inserts(conn)], [1474, 1480])

    def test_falha_grava_erro_e_nao_publica_a_resposta_antes_do_pedido(self):
        self.glpi.validacoes[35092] = [_validacao(status=3)]
        self.tiflux.resposta_publicacao = _FakeHttpResponse(500, {}, text="indisponível")
        conn = FakeConnection(respostas=[[], []])
        self.assertEqual(self._publicar(conn), (0, 1))
        self.assertEqual(len(self.tiflux.publicacoes), 1)
        self.assertEqual(_inserts(conn), [(DIRECAO_PEDIDO, 1474, "erro")])

    def test_pedido_e_resposta_no_mesmo_ciclo_saem_pedido_primeiro(self):
        self.glpi.validacoes[35092] = [_validacao(status=3)]
        conn = FakeConnection(respostas=[[], []])
        self.assertEqual(self._publicar(conn), (2, 0))
        self.assertIn("🔐", self.tiflux.publicacoes[0][2])
        self.assertIn("✅", self.tiflux.publicacoes[1][2])

    def test_validacao_anterior_ao_corte_e_ignorada(self):
        self.glpi.validacoes[35092] = [_validacao(1473)]
        conn = FakeConnection()
        self.assertEqual(self._publicar(conn), (0, 0))
        self.assertEqual(conn.execucoes, [])

    def test_corte_zero_desliga_sem_consultar(self):
        self.glpi.validacoes[35092] = [_validacao()]
        self.assertEqual(self._publicar(FakeConnection(), replace(_CONFIG, validacao_glpi_desde_id=0)), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])


if __name__ == "__main__":
    unittest.main()
