import unittest

from sync.config import Config
from sync.regras_negocio import (
    cabecalho_prioridade_glpi,
    definir_autor_glpi,
    definir_prioridade,
    definir_tecnico,
    depara_categoria,
    numero_tiflux_no_titulo,
    telefone_para_tiflux,
)

_CONFIG_TESTE = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x.y", tabela_followups="x.z",
)


class TestDeparaCategoria(unittest.TestCase):
    def test_limites_administrativo(self):
        self.assertEqual(depara_categoria(267), 37963)
        self.assertEqual(depara_categoria(271), 37963)

    def test_categoria_233_e_administrativo(self):
        self.assertEqual(depara_categoria(233), 37963)

    def test_limites_arrecadacao(self):
        self.assertEqual(depara_categoria(272), 37964)
        self.assertEqual(depara_categoria(276), 37964)

    def test_limites_financas(self):
        self.assertEqual(depara_categoria(277), 37965)
        self.assertEqual(depara_categoria(281), 37965)

    def test_limites_suprimentos(self):
        self.assertEqual(depara_categoria(282), 37966)
        self.assertEqual(depara_categoria(286), 37966)

    def test_fora_de_qualquer_faixa_retorna_none(self):
        self.assertIsNone(depara_categoria(266))
        self.assertIsNone(depara_categoria(287))
        self.assertIsNone(depara_categoria(None))


class TestDefinirTecnico(unittest.TestCase):
    def test_arrecadacao_vai_para_leo(self):
        id_tecnico, nome = definir_tecnico(37964, _CONFIG_TESTE)
        self.assertEqual((id_tecnico, nome), (_CONFIG_TESTE.id_tecnico_leo, "Léo Alves"))

    def test_qualquer_outra_mesa_fica_sem_tecnico(self):
        for mesa in (37963, 37965, 37966):
            id_tecnico, nome = definir_tecnico(mesa, _CONFIG_TESTE)
            self.assertEqual((id_tecnico, nome), (None, None))


class TestDefinirAutorGlpi(unittest.TestCase):
    def test_sempre_leo_independente_da_mesa(self):
        self.assertEqual(definir_autor_glpi(_CONFIG_TESTE), _CONFIG_TESTE.id_glpi_leo)


class TestDefinirPrioridade(unittest.TestCase):
    def test_mesas_configuradas(self):
        self.assertEqual(definir_prioridade(37963), 120547)
        self.assertEqual(definir_prioridade(37964), 120549)
        self.assertEqual(definir_prioridade(37965), 120551)
        self.assertEqual(definir_prioridade(37966), 121197)

    def test_mesa_nao_configurada_retorna_none(self):
        self.assertIsNone(definir_prioridade(99999))


class TestCabecalhoPrioridadeGlpi(unittest.TestCase):
    def test_muito_baixa_e_baixa_usam_sla_de_72_horas(self):
        for prioridade, nome in ((1, "Muito baixa"), (2, "Baixa")):
            cabecalho = cabecalho_prioridade_glpi(prioridade)
            self.assertTrue(cabecalho.startswith(f"Este chamado tem a prioridade: {nome}\n\n"))
            self.assertIn("Ação em 72 horas da abertura do chamado", cabecalho)

    def test_media_e_alta_usam_sla_de_8_horas(self):
        for prioridade, nome in ((3, "Média"), (4, "Alta")):
            cabecalho = cabecalho_prioridade_glpi(prioridade)
            self.assertTrue(cabecalho.startswith(f"Este chamado tem a prioridade: {nome}\n\n"))
            self.assertIn("Deverá apresentar solução de contorno.", cabecalho)

    def test_muito_alta_e_critica_usam_sla_de_2_horas(self):
        for prioridade, nome in ((5, "Muito alta"), (6, "Crítica")):
            cabecalho = cabecalho_prioridade_glpi(prioridade)
            self.assertTrue(cabecalho.startswith(f"Este chamado tem a prioridade: {nome}\n\n"))
            self.assertIn("Deverá apresentar solução de emergência.", cabecalho)

    def test_valor_desconhecido_cai_em_media(self):
        for prioridade in (99, None):
            self.assertEqual(cabecalho_prioridade_glpi(prioridade), cabecalho_prioridade_glpi(3))


class TestNumeroTifluxNoTitulo(unittest.TestCase):
    def test_titulo_prefixado_devolve_numero(self):
        self.assertEqual(numero_tiflux_no_titulo("#361535 - Erro no boleto"), "361535")
        self.assertEqual(numero_tiflux_no_titulo(" #361535 - Erro"), "361535")

    def test_titulo_sem_prefixo_ou_vazio_devolve_none(self):
        self.assertIsNone(numero_tiflux_no_titulo("Erro #361535 - boleto"))
        self.assertIsNone(numero_tiflux_no_titulo(None))


if __name__ == "__main__":
    unittest.main()


class TestTelefoneParaTiflux(unittest.TestCase):
    def test_fixo_com_mascara_vira_e164(self):
        self.assertEqual(telefone_para_tiflux("(12) 3982-8120"), "+551239828120")

    def test_celular_com_ddi_e_zero_de_operadora(self):
        self.assertEqual(telefone_para_tiflux("+55 (12) 98267-4506"), "+5512982674506")
        self.assertEqual(telefone_para_tiflux("012 98267-4506"), "+5512982674506")

    def test_vazio_ou_incompleto_retorna_none(self):
        self.assertIsNone(telefone_para_tiflux(None))
        self.assertIsNone(telefone_para_tiflux(""))
        self.assertIsNone(telefone_para_tiflux("3982-8120"))
