"""Publicação de followups nos dois sentidos (sync/publicacao_followups.py)."""

import unittest

from requests import Timeout

from sync.config import Config
from sync.publicacao_followups import (
    formatar_data_hora_brasilia,
    prefixar_autor_tiflux,
    sincronizar_followups_glpi_para_tiflux,
    sincronizar_followups_tiflux_para_glpi,
)
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient, _FakeHttpResponse
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)


class TestFormatarDataHoraBrasilia(unittest.TestCase):
    def test_converte_utc_para_brasilia(self):
        self.assertEqual(formatar_data_hora_brasilia("2026-09-09T14:10:26Z"), "09/09/2026 11:10")

    def test_none_retorna_none(self):
        self.assertIsNone(formatar_data_hora_brasilia(None))

    def test_formato_invalido_retorna_none(self):
        self.assertIsNone(formatar_data_hora_brasilia("não é uma data"))


class TestPrefixarAutorTiflux(unittest.TestCase):
    def test_com_nome_e_data(self):
        resultado = prefixar_autor_tiflux("José Augusto", "2026-09-09T14:10:26Z", "conteúdo")
        self.assertEqual(resultado, "<strong>José Augusto</strong> (09/09/2026 11:10)<br><br>conteúdo")

    def test_sem_nome_usa_desconhecido(self):
        resultado = prefixar_autor_tiflux(None, "2026-09-09T14:10:26Z", "conteúdo")
        self.assertTrue(resultado.startswith("<strong>Desconhecido</strong>"))

    def test_sem_data_omite_parenteses(self):
        resultado = prefixar_autor_tiflux("José Augusto", None, "conteúdo")
        self.assertEqual(resultado, "<strong>José Augusto</strong><br><br>conteúdo")


class TestSincronizarFollowupsGlpiParaTiflux(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.conn = FakeConnection(respostas=[[]])  # nenhum followup já processado

    def test_sem_followups_no_glpi_nao_faz_nada(self):
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))

    def test_followup_privado_nao_e_sincronizado(self):
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 1, "users_id": 5}]
        self.glpi.tickets[1] = {}
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_followup_publico_do_requerente_vai_com_nome_dele(self):
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 5}]
        self.glpi.nomes_usuarios[5] = "Fulano"
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(self.tiflux.publicacoes[0][0], "cliente")
        self.assertEqual(self.tiflux.publicacoes[0][3], "Fulano")

    def test_followup_publico_de_quem_nao_e_requerente_vai_com_nome_do_autor(self):
        # GLPI #34522: followup do Marcio (não requerente) chegava no Tiflux
        # como resposta de agente, assinada "API Embras" (dono do token).
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 780}]
        self.glpi.nomes_usuarios[780] = "Marcio Silva"
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(self.tiflux.publicacoes[0][0], "cliente")
        self.assertEqual(self.tiflux.publicacoes[0][3], "Marcio Silva")

    def test_falha_http_ao_publicar_conta_como_erro(self):
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 5}]
        self.glpi.tickets[1] = {}
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 5)
        self.tiflux.resposta_publicacao = _FakeHttpResponse(500, None)
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 1))

    def test_followup_criado_pela_integracao_em_nome_de_leo_nao_e_reenviado_ao_tiflux(self):
        # Eco: um followup Tiflux->GLPI criado com users_id=Léo (mesa
        # ARRECADAÇÃO) não pode voltar pro Tiflux como se fosse resposta nova.
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": _CONFIG.id_glpi_leo}]
        self.glpi.tickets[1] = {}
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_followup_criado_pela_integracao_em_nome_de_sania_nao_e_reenviado_ao_tiflux(self):
        self.glpi.followups[1] = [{"id": 11, "content": "oi", "is_private": 0, "users_id": _CONFIG.id_glpi_sania}]
        self.glpi.tickets[1] = {}
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_followup_de_outro_autor_e_enviado_normalmente_mesmo_com_outros_ja_filtrados(self):
        self.glpi.followups[1] = [
            {"id": 10, "content": "eco", "is_private": 0, "users_id": _CONFIG.id_glpi_leo},
            {"id": 12, "content": "resposta real", "is_private": 0, "users_id": 42},
        ]
        self.glpi.tickets[1] = {}
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 5)
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(len(self.tiflux.publicacoes), 1)

    def test_ja_processado_e_ignorado(self):
        self.conn = FakeConnection(respostas=[[(10,)]])
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 5}]
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.tiflux.publicacoes, [])

    def test_anexo_do_followup_vai_junto_na_resposta_nao_como_anexo_do_chamado(self):
        # Regressão: chamado GLPI #34234 / Tiflux #362601 — anexo mandado num
        # followup do requerente nunca aparecia em /Ticket/{id}/Document_Item
        # (só em /ITILFollowup/{id}/Document_Item), então era descartado.
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 5}]
        self.glpi.tickets[1] = {}
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 5)
        anexo = ("planilha.xlsx", b"conteudo", "application/vnd.ms-excel")
        self.glpi.anexos_followup[10] = ([anexo], [])
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(self.tiflux.publicacoes[0][4], [anexo])
        self.assertEqual(self.tiflux.resultado_anexos, (0, 0, []))  # nada foi pro nível do chamado

    def test_mais_de_dez_anexos_manda_excedente_pro_nivel_do_chamado(self):
        self.glpi.followups[1] = [{"id": 10, "content": "oi", "is_private": 0, "users_id": 5}]
        self.glpi.tickets[1] = {}
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 5)
        anexos = [(f"a{i}.txt", b"x", "text/plain") for i in range(12)]
        self.glpi.anexos_followup[10] = (anexos, [])
        self.tiflux.resultado_anexos = (2, 0, [])
        sucesso, erro = sincronizar_followups_glpi_para_tiflux(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(len(self.tiflux.publicacoes[0][4]), 10)


class TestSincronizarFollowupsTifluxParaGlpi(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.conn = FakeConnection(respostas=[[]])

    def test_resposta_publica_vira_followup_publico_no_glpi(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        sucesso, erro = sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (1, 0))
        self.assertEqual(self.glpi.followups_criados[0]["is_private"], 0)

    def test_resposta_publica_e_prefixada_com_autor_e_data_em_negrito(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp", "author": "José Augusto", "answer_time": "2026-09-09T14:10:26Z"}]
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        conteudo = self.glpi.followups_criados[0]["conteudo"]
        self.assertEqual(conteudo, "<strong>José Augusto</strong> (09/09/2026 11:10)<br><br>resp")
        # autoria real no GLPI (users_id) é sempre Léo, não o autor exibido no texto
        self.assertEqual(self.glpi.followups_criados[0]["users_id"], _CONFIG.id_glpi_leo)

    def test_comunicacao_interna_no_tiflux_nao_e_sincronizada(self):
        self.tiflux.comunicacoes = [{"id": 2, "text": "com"}]
        sucesso, erro = sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.glpi.followups_criados, [])

    def test_sem_autor_ou_data_usa_desconhecido_e_omite_parenteses(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        conteudo = self.glpi.followups_criados[0]["conteudo"]
        self.assertEqual(conteudo, "<strong>Desconhecido</strong><br><br>resp")

    def test_followup_e_sempre_atribuido_ao_leo_no_glpi_independente_da_mesa(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual(self.glpi.followups_criados[0]["users_id"], _CONFIG.id_glpi_leo)

    def test_respostas_sao_publicadas_da_mais_antiga_para_a_mais_nova(self):
        # Regressão GLPI #34848: o Tiflux lista da mais nova pra mais antiga.
        self.tiflux.respostas = [
            {"id": 2, "name": "nova", "answer_time": "2025-01-01T10:00:00Z"},
            {"id": 1, "name": "antiga", "answer_time": "2023-01-01T10:00:00Z"},
        ]
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        conteudos = [f["conteudo"] for f in self.glpi.followups_criados]
        self.assertTrue(conteudos[0].endswith("antiga") and conteudos[1].endswith("nova"))

    def test_resposta_de_origem_api_e_ignorada_eco(self):
        self.tiflux.respostas = [{"id": 1, "name": "eco", "answer_origin": "api"}]
        sucesso, erro = sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 0))
        self.assertEqual(self.glpi.followups_criados, [])

    def test_falha_ao_criar_followup_no_glpi_conta_como_erro(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        self.glpi.erro_ao_criar_followup = "Falha ao criar followup no GLPI (500): boom"
        sucesso, erro = sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual((sucesso, erro), (0, 1))

    def test_followup_criado_com_sucesso_deixa_pendente_no_glpi(self):
        """Criar o followup faz o GLPI mudar o status pra "Processando (atribuído)" automaticamente; deve ficar Pendente (spec 009)."""
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual(self.glpi.chamados_deixados_pendentes, [1])

    def test_falha_ao_criar_followup_nao_tenta_voltar_status(self):
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        self.glpi.erro_ao_criar_followup = "Falha ao criar followup no GLPI (500): boom"
        sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 1, "T-1")
        self.assertEqual(self.glpi.chamados_deixados_pendentes, [])


class FakeLeituraRespostaComTimeout:
    """listar_arquivos_resposta que levanta como requests faria num timeout do Tiflux."""

    def __call__(self, ticket_number: int, id_resposta: int) -> list[dict] | None:
        raise Timeout(f"/tickets/{ticket_number}/answers/{id_resposta}")


_ARQUIVO_RESPOSTA = {"id": 9, "file_name": "a.xlsx", "content_type": "application/xlsx", "size": 4028, "url": "https://s3/a.xlsx"}


class TestAnexosDaRespostaTifluxNoFollowupGlpi(unittest.TestCase):
    """Spec 014 (GLPI #35249): arquivos da resposta vão pro followup que ela gerou."""

    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.conn = FakeConnection(respostas=[[]])
        self.tiflux.respostas = [{"id": 32082144, "name": "planilhas", "files_count": 1}]
        self.tiflux.arquivos_por_resposta[32082144] = [_ARQUIVO_RESPOSTA]
        self.tiflux.conteudos_por_url["https://s3/a.xlsx"] = b"xlsx"

    def _sincronizar(self) -> tuple[int, int]:
        return sincronizar_followups_tiflux_para_glpi(self.conn, _CONFIG, self.glpi, self.tiflux, 35249, 365680)

    def _mensagem_auditada(self) -> str:
        return next(p for _, params in self.conn.execucoes for p in (params or ()) if "publicada como followup" in str(p))

    def test_arquivo_vai_pro_followup_criado(self):
        self.assertEqual(self._sincronizar(), (1, 0))
        id_followup = self.glpi.proximo_id_followup
        self.assertEqual(
            self.glpi.cliente_abertura().documentos_anexados,
            [("ITILFollowup", id_followup, "a.xlsx", b"xlsx", "application/xlsx")],
        )
        self.assertIn("| Anexos: 1 copiado(s)", self._mensagem_auditada())

    def test_resposta_sem_arquivos_nao_le_a_resposta_no_tiflux(self):
        self.tiflux.respostas = [{"id": 1, "name": "texto", "files_count": 0}]
        self._sincronizar()
        self.assertEqual(self.tiflux.respostas_com_arquivos_lidas, [])
        self.assertEqual(self.glpi.cliente_abertura().documentos_anexados, [])

    def test_falha_no_anexo_fica_na_mensagem_e_followup_segue_sucesso(self):
        self.tiflux.conteudos_por_url.clear()
        self.assertEqual(self._sincronizar(), (1, 0))
        self.assertIn("'a.xlsx': falha ao baixar do Tiflux", self._mensagem_auditada())

    def test_falha_ao_ler_a_resposta_fica_na_mensagem(self):
        self.tiflux.arquivos_por_resposta[32082144] = None
        self.assertEqual(self._sincronizar(), (1, 0))
        self.assertIn("falha ao ler os 1 arquivo(s)", self._mensagem_auditada())

    def test_timeout_ao_ler_a_resposta_nao_impede_a_auditoria(self):
        # Exceção aqui deixaria o followup sem linha na auditoria -> duplicado no próximo ciclo.
        self.tiflux.listar_arquivos_resposta = FakeLeituraRespostaComTimeout()
        self.assertEqual(self._sincronizar(), (1, 0))
        self.assertIn("falha ao ler os 1 arquivo(s)", self._mensagem_auditada())

    def test_falha_ao_criar_followup_nao_envia_anexo(self):
        self.glpi.erro_ao_criar_followup = "Falha ao criar followup no GLPI (500): boom"
        self.assertEqual(self._sincronizar(), (0, 1))
        self.assertEqual(self.tiflux.respostas_com_arquivos_lidas, [])
        self.assertEqual(self.glpi.cliente_abertura().documentos_anexados, [])


if __name__ == "__main__":
    unittest.main()
