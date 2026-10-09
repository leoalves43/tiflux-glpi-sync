import unittest
from datetime import datetime, timezone

from sync.regras_abertura_glpi import (
    TELEFONE_GLPI_PADRAO,
    campos_chamado_glpi,
    conteudo_glpi_aberto_pelo_tiflux,
    telefone_para_glpi,
    ticket_candidato_a_abertura,
    titulo_glpi_aberto_pelo_tiflux,
    titulo_tiflux_com_id_glpi,
)

_CORTE = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
_TICKET_NOVO = {
    "ticket_number": 364990, "desk": {"id": 37964}, "created_at": "2026-10-10T13:00:00Z", "title": "Erro no boleto",
}


class TestTicketCandidatoAAbertura(unittest.TestCase):
    def test_ticket_novo_numa_mesa_do_contrato_e_candidato(self):
        self.assertTrue(ticket_candidato_a_abertura(_TICKET_NOVO, _CORTE, set()))

    def test_infraestrutura_vai_para_a_categoria_348(self):
        # Spec 010, AC 1.
        ticket = {**_TICKET_NOVO, "desk": {"id": 38853}, "description": "", "requestor": {}}
        self.assertTrue(ticket_candidato_a_abertura(ticket, _CORTE, set()))
        self.assertEqual(campos_chamado_glpi(ticket, 4988, 4988)["itilcategories_id"], 348)

    def test_mesa_fora_do_contrato_nao_e_candidata(self):
        # AC 4: ex. DEVOPS (INFRAESTRUTURA entrou na spec 010).
        ticket = {**_TICKET_NOVO, "desk": {"id": 11111}}
        self.assertFalse(ticket_candidato_a_abertura(ticket, _CORTE, set()))

    def test_aberto_antes_do_corte_nao_e_candidato(self):
        # AC 6.
        ticket = {**_TICKET_NOVO, "created_at": "2026-10-10T11:59:59Z"}
        self.assertFalse(ticket_candidato_a_abertura(ticket, _CORTE, set()))

    def test_ja_vinculado_na_auditoria_nao_e_candidato(self):
        # AC 5: ticket criado pela integração a partir do GLPI.
        self.assertFalse(ticket_candidato_a_abertura(_TICKET_NOVO, _CORTE, {364990}))

    def test_numero_em_texto_tambem_e_comparado_como_inteiro(self):
        ticket = {**_TICKET_NOVO, "ticket_number": "364990"}
        self.assertFalse(ticket_candidato_a_abertura(ticket, _CORTE, {364990}))

    def test_sem_data_de_criacao_nao_e_candidato(self):
        ticket = {**_TICKET_NOVO, "created_at": None}
        self.assertFalse(ticket_candidato_a_abertura(ticket, _CORTE, set()))

    def test_titulo_com_id_glpi_nao_e_candidato(self):
        ticket = {**_TICKET_NOVO, "title": "Erro no boleto (34986) "}
        self.assertFalse(ticket_candidato_a_abertura(ticket, _CORTE, set()))


class TestTelefoneParaGlpi(unittest.TestCase):
    def test_e164_fixo_e_celular_viram_digitos_com_ddd(self):
        self.assertEqual(telefone_para_glpi("+551238971108"), "1238971108")
        self.assertEqual(telefone_para_glpi("+5512982674506"), "12982674506")

    def test_vazio_ou_incompleto_usa_padrao(self):
        for telefone in (None, "", "3897-1108"):
            self.assertEqual(telefone_para_glpi(telefone), TELEFONE_GLPI_PADRAO)


class TestTitulos(unittest.TestCase):
    def test_titulo_glpi_prefixado_com_numero_tiflux(self):
        self.assertEqual(titulo_glpi_aberto_pelo_tiflux(364990, " Erro no boleto "), "#364990 - Erro no boleto")

    def test_titulo_tiflux_ganha_id_glpi_no_fim(self):
        self.assertEqual(titulo_tiflux_com_id_glpi("Erro no boleto ", 35001), "Erro no boleto (35001)")


class TestConteudoGlpi(unittest.TestCase):
    def test_solicitante_escapado_antes_da_descricao(self):
        conteudo = conteudo_glpi_aberto_pelo_tiflux({"name": "Ana", "email": "a@x.com"}, "<p>Erro</p>")
        self.assertEqual(conteudo, "<p>Solicitante: Ana &lt;a@x.com&gt;</p><p>Erro</p>")

    def test_sem_solicitante_nem_descricao(self):
        conteudo = conteudo_glpi_aberto_pelo_tiflux(None, None)
        self.assertEqual(conteudo, "<p>Solicitante: Desconhecido &lt;Sem e-mail&gt;</p>")


class TestCamposChamadoGlpi(unittest.TestCase):
    def test_campos_fixos_da_spec_e_atores(self):
        # AC 1 (parte GLPI): entidade STII, categoria pela mesa, origem, localização, prioridade, atores.
        ticket = {**_TICKET_NOVO, "description": "<p>Erro</p>", "requestor": {"name": "Ana", "email": "a@x.com"}}
        campos = campos_chamado_glpi(ticket, 173, 4988)
        self.assertEqual(campos["name"], "#364990 - Erro no boleto")
        self.assertEqual(
            {k: campos[k] for k in ("entities_id", "itilcategories_id", "requesttypes_id", "locations_id", "priority")},
            {"entities_id": 1, "itilcategories_id": 272, "requesttypes_id": 6, "locations_id": 1685, "priority": 3},
        )
        self.assertEqual(
            (campos["_users_id_requester"], campos["_users_id_assign"], campos["_groups_id_observer"]), (173, 4988, 22),
        )
        self.assertTrue(campos["content"].endswith("<p>Erro</p>"))


if __name__ == "__main__":
    unittest.main()
