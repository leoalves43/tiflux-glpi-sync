"""Abertura Tiflux -> GLPI de ponta a ponta com fakes (spec 009)."""

import contextlib
import dataclasses
import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sync.abertura_tiflux_para_glpi import abrir_chamados_do_tiflux
from sync.config import Config
from sync.glpi_abertura_client import ResultadoCriacaoGlpi
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient, FakeTifluxClientContador, panorama_de_teste
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
    abertura_tiflux_desde=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
)
_LISTADO = {
    "ticket_number": 364990, "desk": {"id": 37964}, "created_at": "2026-10-10T13:00:00Z", "title": "Erro no boleto",
    "requestor": {"name": "Paula", "email": "paula@x.gov.br", "telephone": "+551238971108"},
}
_COMPLETO = {**_LISTADO, "description": "<p>Boleto não gera</p>"}
_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())


def _conn(estados: list[tuple] | None = None, na_auditoria: list[tuple] | None = None) -> FakeConnection:
    # Ordem das consultas: estados da abertura, números na auditoria, depois só escritas.
    return FakeConnection(respostas=[estados or [], na_auditoria or []])


def _escritas(conn: FakeConnection) -> list[tuple]:
    """(tabela, status) de cada INSERT, na ordem: mostra a sequência intenção -> auditoria -> sucesso."""
    return [("followups" if "direcao" in sql else "chamados", params[6] if "direcao" in sql else params[2])
            for sql, params in conn.execucoes if sql.lstrip().startswith("INSERT")]


class _Base(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.abertura = self.glpi.cliente_abertura()
        self.tiflux = FakeTifluxClient()
        self.tiflux.tickets_por_numero[364990] = _COMPLETO

    def _abrir(self, conn: FakeConnection, *listados: dict, config: Config = _CONFIG) -> str:
        with _sem_console() as saida:
            abrir_chamados_do_tiflux(conn, config, self.glpi, self.tiflux, panorama_de_teste(tickets_listados=listados))
        return saida.getvalue()


class TestAberturaDeTicketNovo(_Base):
    def test_cria_no_glpi_com_campos_da_spec_e_registra_na_ordem_segura(self):
        # AC 1: intenção antes do POST, auditoria de chamados logo depois.
        conn = _conn()
        self._abrir(conn, _LISTADO)
        campos = self.abertura.chamados_criados[0]
        self.assertEqual((campos["name"], campos["itilcategories_id"], campos["entities_id"]), ("#364990 - Erro no boleto", 272, 1))
        self.assertEqual(_escritas(conn), [("followups", "pendente"), ("chamados", "sucesso"), ("followups", "sucesso")])

    def test_passos_seguintes_renomeiam_gravam_telefone_e_deixam_pendente(self):
        # AC 3 e 10, e status Pendente.
        self._abrir(_conn(), _LISTADO)
        self.assertEqual(self.tiflux.renomeados, [(364990, "Erro no boleto (35001)")])
        self.assertEqual(self.abertura.telefones_gravados, [(35001, "1238971108")])
        self.assertEqual(self.glpi.chamados_deixados_pendentes, [35001])

    def test_requerente_pelo_email_ou_suporte_embras(self):
        # AC 2.
        self.abertura.usuarios_por_email["paula@x.gov.br"] = 173
        self._abrir(_conn(), _LISTADO)
        self.assertEqual(self.abertura.chamados_criados[0]["_users_id_requester"], 173)
        self.abertura.usuarios_por_email.clear()
        self._abrir(_conn(), _LISTADO)
        self.assertEqual(self.abertura.chamados_criados[1]["_users_id_requester"], 4988)

    def test_sem_telefone_no_tiflux_grava_o_padrao(self):
        self.tiflux.tickets_por_numero[364990] = {**_COMPLETO, "requestor": {"email": "a@x", "telephone": ""}}
        self._abrir(_conn(), _LISTADO)
        self.assertEqual(self.abertura.telefones_gravados, [(35001, "1238971100")])

    def test_falha_nos_passos_seguintes_so_avisa(self):
        self.tiflux.erro_ao_renomear = "Falha ao renomear (422)"
        saida = self._abrir(_conn(), _LISTADO)
        self.assertIn("aberto no GLPI como chamado #35001 | Aviso: Falha ao renomear (422)", saida)


class TestTicketsQueNaoAbrem(_Base):
    def _nada_criado(self, conn: FakeConnection, *listados: dict, config: Config = _CONFIG) -> None:
        self._abrir(conn, *listados, config=config)
        self.assertEqual(self.abertura.chamados_criados, [])
        self.assertEqual(_escritas(conn), [])

    def test_funcionalidade_desligada_nao_consulta_nada(self):
        conn = _conn()
        self._nada_criado(conn, _LISTADO, config=dataclasses.replace(_CONFIG, abertura_tiflux_desde=None))
        self.assertEqual(conn.execucoes, [])

    def test_mesa_fora_do_contrato(self):
        # AC 4.
        self._nada_criado(_conn(), {**_LISTADO, "desk": {"id": 11111}})

    def test_ticket_ja_na_auditoria_mesmo_com_erro(self):
        # AC 5: criado pela integração a partir do GLPI.
        self._nada_criado(_conn(na_auditoria=[(364990,)]), _LISTADO)

    def test_aberto_antes_do_corte(self):
        # AC 6.
        self._nada_criado(_conn(), {**_LISTADO, "created_at": "2026-10-09T13:00:00Z"})

    def test_abertura_pendente_nao_e_refeita_e_e_avisada(self):
        conn = _conn(estados=[(364990, "pendente")])
        self.assertIn("revisar manualmente", self._abrir(conn, _LISTADO))
        self.assertEqual(self.abertura.chamados_criados, [])

    def test_sem_ticket_novo_nao_faz_requisicao_ao_tiflux(self):
        # AC 14: a meta de requisições ociosas da spec 008 não muda.
        self.tiflux = FakeTifluxClientContador()
        self._nada_criado(_conn(na_auditoria=[(364990,)]), _LISTADO, {**_LISTADO, "desk": {"id": 1}})
        self.assertEqual(self.tiflux.requisicoes, [])

    def test_ticket_ilegivel_no_tiflux_vira_erro_retentavel(self):
        # Fechado entre execuções + 5xx: sem a linha 'erro', a retentativa se perderia.
        self.tiflux.tickets_por_numero = {1: {}}
        conn = _conn()
        self._abrir(conn, _LISTADO)
        self.assertEqual(self.abertura.chamados_criados, [])
        self.assertEqual(_escritas(conn), [("followups", "erro")])


class TestFalhaAoCriarNoGlpi(_Base):
    def test_recusa_clara_vira_erro_retentavel_sem_auditoria_de_chamado(self):
        # AC 8.
        self.abertura.resultado_criar_chamado = ResultadoCriacaoGlpi(None, "GLPI recusou o chamado (400)", False)
        conn = _conn()
        self._abrir(conn, _LISTADO)
        self.assertEqual(_escritas(conn), [("followups", "pendente"), ("followups", "erro")])

    def test_resultado_incerto_fica_pendente(self):
        self.abertura.resultado_criar_chamado = ResultadoCriacaoGlpi(None, "timeout", True)
        conn = _conn()
        self._abrir(conn, _LISTADO)
        self.assertEqual(_escritas(conn), [("followups", "pendente")])

    def test_erro_anterior_e_retentado_mesmo_fora_da_listagem(self):
        # Ticket já fechado sai da lista de abertos e o checkpoint já passou dele.
        self._abrir(_conn(estados=[(364990, "erro")]))
        self.assertEqual(len(self.abertura.chamados_criados), 1)

    def test_ticket_que_deixou_de_ser_candidato_nao_e_aberto(self):
        # Ex.: renomeado à mão com "(id_glpi)" entre a listagem e a leitura individual.
        self.tiflux.tickets_por_numero[364990] = {**_COMPLETO, "title": "Erro (34999)"}
        conn = _conn(estados=[(364990, "erro")])
        self.assertIn("não é mais candidato", self._abrir(conn, _LISTADO))
        self.assertEqual(self.abertura.chamados_criados, [])
        self.assertEqual(_escritas(conn), [("followups", "ignorado")])

    def test_excecao_num_ticket_nao_para_os_demais(self):
        outro = {**_LISTADO, "ticket_number": 364991}
        self.tiflux.tickets_por_numero[364991] = {**_COMPLETO, "ticket_number": 364991}
        obter_original = self.tiflux.obter_ticket

        def obter_ou_falhar(numero):
            if numero == 364990:
                raise ConnectionError("rede caiu")
            return obter_original(numero)

        with patch.object(self.tiflux, "obter_ticket", side_effect=obter_ou_falhar):
            saida = self._abrir(_conn(), _LISTADO, outro)
        self.assertIn("#364990: erro inesperado ao abrir no GLPI (rede caiu)", saida)
        self.assertEqual([c["name"] for c in self.abertura.chamados_criados], ["#364991 - Erro no boleto"])

if __name__ == "__main__":
    unittest.main()
