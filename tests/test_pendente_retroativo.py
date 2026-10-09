import contextlib
import io
import unittest

from sync.pendente_retroativo import chamados_novos_sincronizados, deixar_pendentes
from tests.fake_clients import FakeGlpiClient

_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())


class TestChamadosNovosSincronizados(unittest.TestCase):
    def test_so_os_que_estao_novo(self):
        # AC 13: outros status abertos (Processando 2, Pendente 4) não mudam.
        glpi = FakeGlpiClient()
        glpi.tickets = {1: {"status": 1}, 2: {"status": 2}, 3: {"status": 4}, 4: {"status": 6}}
        self.assertEqual(chamados_novos_sincronizados(glpi, [1, 2, 3, 4]), [1])

    def test_ilegivel_fica_de_fora_com_aviso(self):
        with _sem_console() as saida:
            self.assertEqual(chamados_novos_sincronizados(FakeGlpiClient(), [7]), [])
        self.assertIn("#7 ilegível", saida.getvalue())


class TestDeixarPendentes(unittest.TestCase):
    def test_aplica_em_todos_e_conta_falhas(self):
        glpi = FakeGlpiClient()
        glpi.resultado_definir_status_pendente = (False, "GLPI recusou")
        with _sem_console() as saida:
            self.assertEqual(deixar_pendentes(glpi, [1, 2]), 2)
        self.assertEqual(glpi.chamados_deixados_pendentes, [1, 2])
        self.assertIn("#1: GLPI recusou", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
