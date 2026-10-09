import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sync.config import Config, log


class TestLog(unittest.TestCase):
    def test_nao_quebra_quando_console_nao_suporta_emoji(self):
        """
        Regressão: log() crashava com UnicodeEncodeError em consoles cp1252
        (comum no Windows em pt-BR) ao imprimir mensagens com emoji — isso
        derrubava a sincronização inteira mesmo com o trabalho já feito.
        """
        saida_cp1252 = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        with patch("sys.stdout", saida_cp1252):
            log("🔎 Sondagem de #1 até #2: 1 chamado(s) encontrado(s)")
        saida_cp1252.flush()

    def test_mensagem_sem_caracteres_especiais_passa_direto(self):
        buffer = io.StringIO()
        with patch("sys.stdout", buffer):
            log("Finalizado. Sucesso: 1 | Ignorado: 0 | Erro: 0")
        self.assertIn("Finalizado. Sucesso: 1", buffer.getvalue())


class TestConfigCarregar(unittest.TestCase):
    def setUp(self):
        arquivo = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        arquivo.write("DB_HOST=localhost\nDB_NAME=banco\nDB_SCHEMA=esquema\n")
        arquivo.close()
        self.caminho_env = arquivo.name
        self.addCleanup(os.remove, self.caminho_env)

    def test_variavel_de_ambiente_sobrescreve_env(self):
        config = Config.carregar(self.caminho_env, ambiente={"DB_HOST": "host.docker.internal"})
        self.assertEqual(config.db_host, "host.docker.internal")
        self.assertEqual(config.db_name, "banco")

    def test_sem_variavel_de_ambiente_usa_env(self):
        config = Config.carregar(self.caminho_env, ambiente={})
        self.assertEqual(config.db_host, "localhost")
        self.assertEqual(config.tabela_auditoria, "esquema.api_glpi_tiflux")

    def test_reserva_do_tiflux_vem_do_ambiente_ou_padrao_5(self):
        self.assertEqual(Config.carregar(self.caminho_env, ambiente={}).reserva_requisicoes_tiflux, 5)
        config = Config.carregar(self.caminho_env, ambiente={"RESERVA_REQUISICOES_TIFLUX": "10"})
        self.assertEqual(config.reserva_requisicoes_tiflux, 10)

    def test_chaves_da_spec_008_vem_do_ambiente_ou_padrao(self):
        padrao = Config.carregar(self.caminho_env, ambiente={})
        self.assertEqual((padrao.margem_checkpoint_tiflux_minutos, padrao.varredura_completa_por_execucao), (5, 1))
        config = Config.carregar(
            self.caminho_env, ambiente={"MARGEM_CHECKPOINT_TIFLUX_MINUTOS": "10", "VARREDURA_COMPLETA_POR_EXECUCAO": "3"},
        )
        self.assertEqual((config.margem_checkpoint_tiflux_minutos, config.varredura_completa_por_execucao), (10, 3))

    def test_abertura_tiflux_desde_vazia_desliga_e_iso_utc_liga(self):
        self.assertIsNone(Config.carregar(self.caminho_env, ambiente={}).abertura_tiflux_desde)
        config = Config.carregar(self.caminho_env, ambiente={"ABERTURA_TIFLUX_DESDE": "2026-10-10T12:00:00Z"})
        self.assertEqual(config.abertura_tiflux_desde, datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc))

    def test_abertura_tiflux_desde_sem_fuso_ou_invalida_falha_com_o_valor(self):
        for valor in ("2026-10-10T12:00:00", "amanhã"):
            with self.assertRaisesRegex(ValueError, valor):
                Config.carregar(self.caminho_env, ambiente={"ABERTURA_TIFLUX_DESDE": valor})


if __name__ == "__main__":
    unittest.main()
