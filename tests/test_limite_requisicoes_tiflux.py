"""Limite de requisições da API do Tiflux (spec 007)."""

import contextlib
import io
import unittest
from datetime import datetime, timedelta, timezone

from sync.config import inteiro_nao_negativo
from sync.limite_requisicoes_tiflux import SessaoTifluxLimitada, segundos_ate_reset
from tests.fakes import FakeResponse

_INICIO = datetime(2026, 10, 7, 15, 51, 30, tzinfo=timezone.utc)
_RESET = "2026-10-07T15:52:00Z"  # 30 s depois de _INICIO
_sem_console = lambda: contextlib.redirect_stdout(io.StringIO())


def _resposta(status: int = 200, restantes: str | None = "100", reset: str | None = _RESET) -> FakeResponse:
    headers = {}
    if restantes is not None:
        headers["RateLimit-Remaining"] = restantes
    if reset is not None:
        headers["RateLimit-Reset"] = reset
    return FakeResponse(status, headers=headers)


class FakeSessaoHttp:
    """Substitui requests.Session: devolve respostas programadas em fila e registra cada chamada."""

    def __init__(self, respostas: list[FakeResponse]):
        self._respostas = list(respostas)
        self.chamadas: list[tuple[str, str, dict]] = []

    def request(self, method, url, **kwargs):
        self.chamadas.append((method, url, kwargs))
        return self._respostas.pop(0)


class FakeRelogio:
    """Relógio controlado: dormir() só avança o tempo e anota quanto foi pedido."""

    def __init__(self, agora: datetime = _INICIO):
        self.atual = agora
        self.esperas: list[float] = []

    def agora(self) -> datetime:
        return self.atual

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.atual += timedelta(seconds=segundos)


def _sessao(respostas: list[FakeResponse], relogio: FakeRelogio, reserva: int = 5):
    http = FakeSessaoHttp(respostas)
    return SessaoTifluxLimitada(http, reserva, dormir=relogio.dormir, agora=relogio.agora), http


class TestSegundosAteReset(unittest.TestCase):
    def test_calcula_segundos_ate_o_reset_mais_margem_de_relogio(self):
        self.assertEqual(segundos_ate_reset(_RESET, _INICIO), 33.0)

    def test_reset_recem_passado_ainda_espera_o_resto_da_margem(self):
        # Regressão 07/10 13:37:01: relógio do Tiflux 1-2 s atrás do nosso.
        self.assertEqual(segundos_ate_reset(_RESET, _INICIO + timedelta(seconds=31)), 2.0)

    def test_reset_passado_vira_zero(self):
        self.assertEqual(segundos_ate_reset(_RESET, _INICIO + timedelta(minutes=2)), 0.0)

    def test_limita_a_espera_maxima(self):
        self.assertEqual(segundos_ate_reset("2026-10-07T16:30:00Z", _INICIO), 65.0)

    def test_ausente_ou_invalido_vira_none(self):
        self.assertIsNone(segundos_ate_reset(None, _INICIO))
        self.assertIsNone(segundos_ate_reset("amanhã", _INICIO))


class TestSessaoTifluxLimitada(unittest.TestCase):
    def setUp(self):
        self.relogio = FakeRelogio()

    def test_cota_folgada_nao_espera(self):
        sessao, http = _sessao([_resposta(restantes="100"), _resposta()], self.relogio)
        sessao.get("u1")
        sessao.get("u2")
        self.assertEqual(self.relogio.esperas, [])
        self.assertEqual(len(http.chamadas), 2)

    def test_cota_na_reserva_faz_a_proxima_chamada_esperar_o_reset(self):
        sessao, _ = _sessao([_resposta(restantes="5"), _resposta()], self.relogio)
        with _sem_console():
            sessao.get("u1")
            self.assertEqual(self.relogio.esperas, [])  # só a PRÓXIMA chamada espera
            sessao.get("u2")
        self.assertEqual(self.relogio.esperas, [33.0])

    def test_espera_da_reserva_desconta_o_tempo_ja_passado(self):
        sessao, _ = _sessao([_resposta(restantes="0"), _resposta()], self.relogio)
        with _sem_console():
            sessao.get("u1")
            self.relogio.atual += timedelta(seconds=20)
            sessao.get("u2")
        self.assertEqual(self.relogio.esperas, [13.0])

    def test_reset_ja_passado_nao_espera(self):
        sessao, _ = _sessao([_resposta(restantes="0"), _resposta()], self.relogio)
        sessao.get("u1")
        self.relogio.atual += timedelta(minutes=2)
        sessao.get("u2")
        self.assertEqual(self.relogio.esperas, [])

    def test_429_espera_o_reset_e_repete_a_mesma_chamada(self):
        sessao, http = _sessao([_resposta(429, restantes="0"), _resposta(200)], self.relogio)
        with _sem_console():
            resposta = sessao.post("u1", json={"a": 1})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.relogio.esperas, [33.0])
        self.assertEqual(http.chamadas, [("POST", "u1", {"json": {"a": 1}})] * 2)

    def test_conta_cada_envio_incluindo_repeticoes_de_429(self):
        sessao, _ = _sessao([_resposta(200), _resposta(429, restantes="0"), _resposta(200)], self.relogio)
        with _sem_console():
            sessao.get("u1")
            sessao.post("u2")
        self.assertEqual(sessao.requisicoes_enviadas, 3)

    def test_429_sem_reset_espera_60s(self):
        sessao, _ = _sessao([_resposta(429, restantes=None, reset=None), _resposta(200)], self.relogio)
        with _sem_console():
            sessao.get("u1")
        self.assertEqual(self.relogio.esperas, [60.0])

    def test_429_com_reset_ja_passado_espera_ao_menos_1s(self):
        sessao, _ = _sessao([_resposta(429, reset="2026-10-07T15:51:00Z"), _resposta(200)], self.relogio)
        with _sem_console():
            sessao.get("u1")
        self.assertEqual(self.relogio.esperas, [1.0])

    def test_429_persistente_devolve_429_apos_2_repeticoes(self):
        sessao, http = _sessao([_resposta(429, restantes=None)] * 3, self.relogio)
        with _sem_console():
            resposta = sessao.get("u1")
        self.assertEqual(resposta.status_code, 429)
        self.assertEqual(len(http.chamadas), 3)

    def test_cada_espera_e_logada_com_motivo_e_segundos(self):
        sessao, _ = _sessao([_resposta(429), _resposta(200)], self.relogio)
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            sessao.put("https://api/tickets/1")
        self.assertEqual(saida.getvalue().count("aguardando 33s"), 1)
        self.assertIn("429 em PUT https://api/tickets/1", saida.getvalue())

    def test_resposta_sem_cabecalhos_de_limite_nao_espera(self):
        sessao, _ = _sessao([_resposta(restantes=None, reset=None), _resposta()], self.relogio)
        sessao.get("u1")
        sessao.get("u2")
        self.assertEqual(self.relogio.esperas, [])


class TestReservaConfiguravel(unittest.TestCase):
    def test_le_reserva_do_ambiente(self):
        self.assertEqual(inteiro_nao_negativo({"RESERVA_REQUISICOES_TIFLUX": "10"}, "RESERVA_REQUISICOES_TIFLUX", 5), 10)

    def test_ausente_usa_padrao(self):
        self.assertEqual(inteiro_nao_negativo({}, "RESERVA_REQUISICOES_TIFLUX", 5), 5)

    def test_invalida_falha_citando_o_valor(self):
        with self.assertRaisesRegex(ValueError, "RESERVA_REQUISICOES_TIFLUX='-3'"):
            inteiro_nao_negativo({"RESERVA_REQUISICOES_TIFLUX": "-3"}, "RESERVA_REQUISICOES_TIFLUX", 5)


if __name__ == "__main__":
    unittest.main()
