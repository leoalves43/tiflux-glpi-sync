"""Encerramento/reabertura em cascata (sync/cascata_status.py), exercitados pelo orquestrador."""

import unittest

from sync.config import Config
from sync.sincronizacao_followups import sincronizar_followups
from tests.fake_clients import FakeGlpiClient, FakeTifluxClient, panorama_de_teste
from tests.fakes import FakeConnection

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)


class TestEncerramentoEmCascata(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}  # aberto no GLPI

    def test_ticket_fechado_no_tiflux_encerra_no_glpi_como_solucionado(self):
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 5)])

    def test_ticket_aberto_no_tiflux_nao_encerra_no_glpi(self):
        self.tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_ticket_cancelado_no_tiflux_tambem_encerra_no_glpi(self):
        # Tiflux não distingue close/cancel em is_closed — ambos disparam o encerramento
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37965}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 5)])

    def test_falha_ao_encerrar_e_registrada_como_erro_mas_nao_quebra_a_execucao(self):
        self.glpi.resultado_encerrar_chamado = (False, "Falha ao encerrar chamado #1 no GLPI (500): boom")
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        sql, params = conn.execucoes[-1]
        self.assertIn("erro", params)
        self.assertIn("encerramento", params)

    def test_followups_pendentes_sao_sincronizados_antes_do_encerramento(self):
        # Ordem exigida pelo usuário: sincroniza o que falta e só depois encerra.
        self.tiflux.respostas = [{"id": 1, "name": "resp"}]
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(len(self.glpi.followups_criados), 1)
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 5)])


class TestPreparacaoEncerramentoCascata(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}  # ARRECADAÇÃO

    def test_atribui_tecnico_no_glpi_quando_ainda_nao_tem(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.tecnicos_atribuidos_glpi, [(1, _CONFIG.id_glpi_leo)])

    def test_nao_atribui_tecnico_de_novo_se_ja_tem(self):
        self.glpi.tecnico_ja_atribuido[1] = _CONFIG.id_glpi_leo
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.tecnicos_atribuidos_glpi, [])

    def test_registra_ultima_resposta_publica_como_solucao_prefixada_com_autor_e_data(self):
        self.tiflux.respostas = [
            {"id": 1, "name": "primeira resposta", "answer_time": "2026-09-01T10:00:00Z", "author": "Fulano"},
            {"id": 2, "name": "resposta mais recente", "answer_time": "2026-09-05T10:00:00Z", "author": "José Augusto"},
        ]
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        conteudo = self.glpi.solucoes_registradas[0][1]
        self.assertIn("<strong>José Augusto</strong> (05/09/2026 07:00)", conteudo)
        self.assertIn("resposta mais recente", conteudo)

    def test_solucao_ignora_resposta_criada_pela_integracao_mesmo_mais_recente(self):
        # GLPI #34522: followup do Marcio (vindo do GLPI via API) era a
        # resposta mais recente e virou a solução, no lugar da do técnico.
        self.tiflux.respostas = [
            {"id": 1, "name": "resposta do tecnico", "answer_time": "2026-09-25T19:41:50Z",
             "author": "Leonardo", "answer_origin": "tiflux_web"},
            {"id": 2, "name": "followup vindo do GLPI", "answer_time": "2026-09-25T19:59:20Z",
             "author": "[API] MARCIO", "answer_origin": "api"},
        ]
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        conteudo = self.glpi.solucoes_registradas[0][1]
        self.assertIn("resposta do tecnico", conteudo)
        self.assertNotIn("followup vindo do GLPI", conteudo)

    def test_so_respostas_da_integracao_usa_texto_padrao(self):
        self.tiflux.respostas = [{"id": 2, "name": "eco", "answer_time": "2026-09-25T19:59:20Z", "author": "[API] X"}]
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertNotIn("eco", self.glpi.solucoes_registradas[0][1])

    def test_sem_resposta_publica_usa_texto_padrao(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.solucoes_registradas, [(1, "Chamado encerrado no Tiflux, sem resposta pública registrada.")])

    def test_sem_resposta_publica_mas_agrupado_usa_texto_de_agrupamento_com_ticket_pai(self):
        # Ticket agrupado (is_grouped) não tem resposta própria — a resposta de
        # verdade está no ticket pai (ticket_reference). Ver chamado GLPI #34294
        # / ticket Tiflux #362749, agrupado ao #362748.
        self.tiflux.ticket_tiflux = {
            "is_closed": True, "desk": {"id": 37964},
            "is_grouped": True, "ticket_reference": {"ticket_number": 362748},
        }
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.solucoes_registradas, [(1, "Chamado encerrado no Tiflux por agrupamento ao ticket #362748.")])

    def test_agrupado_sem_referencia_de_ticket_pai_usa_texto_generico_de_agrupamento(self):
        self.tiflux.ticket_tiflux = {
            "is_closed": True, "desk": {"id": 37964}, "is_grouped": True, "ticket_reference": {},
        }
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.solucoes_registradas, [(1, "Chamado encerrado no Tiflux por agrupamento a outro ticket.")])

    def test_nao_registra_solucao_de_novo_se_ja_tem(self):
        self.glpi.ja_tem_solucao[1] = True
        conn = FakeConnection(respostas=[[(1, "T-1")], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.solucoes_registradas, [])


class TestReaberturaEmCascata(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 5}  # Solucionado — presumivelmente por cascata anterior

    def test_reaberto_no_tiflux_reabre_no_glpi_como_processando(self):
        self.tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 2)])
        sql, params = conn.execucoes[-1]
        self.assertIn("reabertura", params)
        self.assertIn("sucesso", params)

    def test_continua_fechado_no_tiflux_nao_reabre_no_glpi(self):
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [])
        sql, params = conn.execucoes[-1]
        self.assertIn("verificacao_status", params)

    def test_falha_ao_consultar_tiflux_nao_reabre_no_glpi(self):
        self.tiflux.ticket_tiflux = None  # falha ao consultar o ticket no Tiflux
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_status_glpi_fechado_manualmente_nunca_e_reaberto(self):
        # status 6 (Fechado) não é o status que a cascata usa — mesmo com o
        # ticket aberto de novo no Tiflux, não mexe (foi encerrado por um
        # técnico direto no GLPI, fora do escopo desta integração).
        self.glpi.tickets[1] = {"status": 6}
        self.tiflux.ticket_tiflux = {"is_closed": False, "desk": {"id": 37964}}
        conn = FakeConnection(respostas=[[(1, "T-1")]])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [])


class TestReaberturaTifluxAposRecusaGlpi(unittest.TestCase):
    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}  # aberto no GLPI de novo
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}}

    def test_recusa_apos_encerramento_em_cascata_reabre_o_tiflux(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(len(self.tiflux.tickets_reabertos), 1)
        ticket_reaberto, motivo = self.tiflux.tickets_reabertos[0]
        self.assertEqual(ticket_reaberto, "T-1")
        self.assertIn("1", motivo)  # id_glpi referenciado no motivo

    def test_apos_reabrir_o_tiflux_nao_encerra_o_glpi_de_novo(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.glpi.chamados_encerrados, [])

    def test_reabertura_e_registrada_na_auditoria(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertTrue(any(
            "reabertura_tiflux" in params and "sucesso" in params for _, params in conn.execucoes
        ))

    def test_followup_da_recusa_e_publicado_no_tiflux_apos_reabrir(self):
        # A recusa em si chega como um followup novo no GLPI; só é publicável
        # no Tiflux depois que o ticket reabre — sem tratamento especial, é o
        # mesmo caminho de qualquer followup pendente.
        self.glpi.followups[1] = [{"id": 10, "content": "recusado, favor verificar", "is_private": 0, "users_id": 42}]
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 42)
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(len(self.tiflux.publicacoes), 1)

    def test_sem_historico_de_encerramento_em_cascata_nao_reabre_o_tiflux(self):
        # Tiflux fechado por um humano direto, chamado nunca foi encerrado em
        # cascata por esta integração — deve seguir o caminho normal
        # (encerrar o GLPI em cascata), não reabrir o Tiflux.
        conn = FakeConnection(respostas=[[(1, "T-1")], [], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.tiflux.tickets_reabertos, [])
        self.assertEqual(self.glpi.chamados_encerrados, [(1, 5)])

    def test_ultima_acao_de_cascata_foi_reabertura_nao_reabre_de_novo(self):
        # Já reaberto numa execução anterior (tipo='reabertura_tiflux') —
        # não deve tentar de novo.
        conn = FakeConnection(respostas=[[(1, "T-1")], [("reabertura_tiflux",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertEqual(self.tiflux.tickets_reabertos, [])

    def test_falha_ao_reabrir_e_registrada_como_erro(self):
        self.tiflux.resultado_reabrir_ticket = (False, "Falha ao reabrir ticket no Tiflux (500): boom")
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())
        self.assertTrue(any(
            "reabertura_tiflux" in params and "erro" in params for _, params in conn.execucoes
        ))


class TestResponsavelAposReaberturaDoTiflux(unittest.TestCase):
    """Spec 006: ticket reaberto pela integração mantém o técnico responsável."""

    def setUp(self):
        self.glpi = FakeGlpiClient()
        self.tiflux = FakeTifluxClient()
        self.glpi.tickets[1] = {"status": 1}  # aberto no GLPI de novo (recusa)
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}, "responsible": {"id": 77}}

    def _sincronizar_recusa(self):
        conn = FakeConnection(respostas=[[(1, "T-1")], [("encerramento",)], [], []])
        sincronizar_followups(conn, _CONFIG, self.glpi, self.tiflux, panorama_de_teste())

    def test_mesmo_responsavel_apos_reabrir_nao_atribui(self):
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [])

    def test_reaberto_sem_responsavel_atribui_o_anterior(self):
        self.tiflux.ticket_apos_reabrir = {"is_closed": False, "desk": {"id": 37964}, "responsible": None}
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [("T-1", 77)])

    def test_reaberto_com_outro_responsavel_atribui_o_anterior(self):
        self.tiflux.ticket_apos_reabrir = {"is_closed": False, "desk": {"id": 37964}, "responsible": {"id": 5}}
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [("T-1", 77)])

    def test_fechado_sem_responsavel_nao_atribui(self):
        self.tiflux.ticket_tiflux = {"is_closed": True, "desk": {"id": 37964}, "responsible": None}
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [])

    def test_falha_no_get_apos_reabrir_atribui_mesmo_assim(self):
        self.tiflux.falhar_get_apos_reabrir = True
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [("T-1", 77)])

    def test_falha_ao_atribuir_nao_impede_publicar_followups(self):
        self.tiflux.ticket_apos_reabrir = {"is_closed": False, "desk": {"id": 37964}, "responsible": None}
        self.tiflux.resultado_atribuir_tecnico = (False, 422, "boom")
        self.glpi.followups[1] = [{"id": 10, "content": "recusado", "is_private": 0, "users_id": 42}]
        self.glpi.requerentes[1] = ("Fulano", "f@x.com", 42)
        self._sincronizar_recusa()
        self.assertEqual(len(self.tiflux.publicacoes), 1)

    def test_falha_ao_reabrir_nao_atribui(self):
        self.tiflux.resultado_reabrir_ticket = (False, "Falha ao reabrir ticket no Tiflux (403): nope")
        self._sincronizar_recusa()
        self.assertEqual(self.tiflux.tecnicos_atribuidos, [])


if __name__ == "__main__":
    unittest.main()
