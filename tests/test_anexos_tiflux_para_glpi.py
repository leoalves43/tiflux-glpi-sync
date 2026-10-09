import unittest

from sync.anexos_tiflux_para_glpi import copiar_anexos_tiflux_para_glpi
from sync.config import Config
from tests.fake_clients import FakeGlpiAberturaClient, FakeTifluxClient

_CONFIG = Config(
    url_glpi="", app_token="", user_token="",
    url_tiflux="", token_tiflux="",
    db_host="", db_port="5432", db_name="", db_user="", db_password="",
    tabela_auditoria="x", tabela_followups="y",
)
_ARQUIVO = {"id": 1, "file_name": "erro.jpg", "content_type": "image/jpeg", "size": 158274, "url": "https://s3/erro.jpg"}


class TestCopiarAnexosTifluxParaGlpi(unittest.TestCase):
    def setUp(self):
        self.tiflux = FakeTifluxClient()
        self.glpi_abertura = FakeGlpiAberturaClient()

    def _copiar(self) -> str:
        return copiar_anexos_tiflux_para_glpi(self.tiflux, self.glpi_abertura, _CONFIG, 364925, 35001)

    def test_sem_arquivos_nao_gera_resumo(self):
        self.assertEqual(self._copiar(), "")

    def test_arquivo_baixado_vai_pro_chamado(self):
        self.tiflux.arquivos_ticket = [_ARQUIVO]
        self.tiflux.conteudos_por_url["https://s3/erro.jpg"] = b"jpg"
        self.assertEqual(self._copiar(), " | Anexos: 1 copiado(s)")
        self.assertEqual(self.glpi_abertura.documentos_anexados, [(35001, "erro.jpg", b"jpg", "image/jpeg")])

    def test_falhas_de_download_tamanho_e_glpi_entram_no_resumo(self):
        grande = {**_ARQUIVO, "file_name": "video.mp4", "size": 30 * 1024 * 1024}
        sem_download = {**_ARQUIVO, "file_name": "sumiu.png", "url": "https://s3/sumiu.png"}
        self.tiflux.arquivos_ticket = [grande, sem_download]
        resumo = self._copiar()
        self.assertIn("0 copiado(s), 2 falhou(aram)", resumo)
        self.assertIn("'video.mp4' acima de 25MB", resumo)
        self.assertIn("'sumiu.png': falha ao baixar", resumo)

    def test_recusa_do_glpi_conta_como_falha(self):
        self.tiflux.arquivos_ticket = [_ARQUIVO]
        self.tiflux.conteudos_por_url["https://s3/erro.jpg"] = b"jpg"
        self.glpi_abertura.erro_ao_anexar = "'erro.jpg': falha ao anexar (400)"
        self.assertIn("1 falhou(aram)", self._copiar())


if __name__ == "__main__":
    unittest.main()
