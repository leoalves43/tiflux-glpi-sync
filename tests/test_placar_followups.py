import unittest

from sync.placar_followups import PlacarFollowups


class TestPlacarFollowups(unittest.TestCase):
    def test_resumo_inicial_igual_ao_formato_do_log(self):
        self.assertEqual(
            PlacarFollowups().resumo(),
            "Followups. GLPI->Tiflux: 0 ok / 0 erro | Tiflux->GLPI: 0 ok / 0 erro | "
            "Encerramento/reabertura em cascata: 0 ok / 0 erro",
        )

    def test_soma_cada_sentido_separadamente(self):
        placar = PlacarFollowups()
        placar.somar_glpi_para_tiflux(2, 1)
        placar.somar_tiflux_para_glpi(3, 0)
        self.assertEqual((placar.glpi_para_tiflux_sucesso, placar.glpi_para_tiflux_erro), (2, 1))
        self.assertEqual((placar.tiflux_para_glpi_sucesso, placar.tiflux_para_glpi_erro), (3, 0))

    def test_conta_cascata_por_resultado(self):
        placar = PlacarFollowups()
        placar.contar_cascata(True)
        placar.contar_cascata(False)
        placar.contar_cascata(False)
        self.assertEqual((placar.cascata_sucesso, placar.cascata_erro), (1, 2))


if __name__ == "__main__":
    unittest.main()
