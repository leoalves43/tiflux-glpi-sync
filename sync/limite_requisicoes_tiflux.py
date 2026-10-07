"""Sessão HTTP que respeita o limite de 120 requisições/minuto da API do Tiflux (spec 007)."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

import requests

from sync.config import log

# Teto de uma espera: a janela do Tiflux é o minuto fechado, mais folga de relógio.
ESPERA_MAXIMA_SEGUNDOS = 65.0
# Usada quando o 429 vem sem RateLimit-Reset legível.
ESPERA_PADRAO_429_SEGUNDOS = 60.0
REPETICOES_APOS_429 = 2
# O relógio do Tiflux fica 1-2 s atrás do nosso: acordar no reset exato dava
# 429 de novo logo após a virada do minuto (medido em 07/10, 13:36-13:41).
MARGEM_RELOGIO_SEGUNDOS = 3.0


class SessaoHttp(Protocol):
    def request(self, method: str, url: str, **kwargs: object) -> requests.Response: ...


def segundos_ate_reset(cabecalho_reset: str | None, agora: datetime) -> float | None:
    """
    Segundos até o `RateLimit-Reset` (ISO 8601 UTC, ex.: "2026-10-07T15:52:00Z")
    mais MARGEM_RELOGIO_SEGUNDOS, limitados a [0, ESPERA_MAXIMA_SEGUNDOS].
    None se ausente ou ilegível.
    Ex.: segundos_ate_reset("2026-10-07T15:52:00Z", datetime(2026, 10, 7, 15, 51, 30, tzinfo=timezone.utc)) -> 33.0
    """
    if not cabecalho_reset:
        return None
    try:
        reset = datetime.fromisoformat(cabecalho_reset.replace("Z", "+00:00"))
    except ValueError:
        return None
    segundos = (reset - agora).total_seconds() + MARGEM_RELOGIO_SEGUNDOS
    return min(max(segundos, 0.0), ESPERA_MAXIMA_SEGUNDOS)


def _restantes(resposta: requests.Response) -> int | None:
    try:
        return int(resposta.headers.get("RateLimit-Remaining"))
    except (TypeError, ValueError):
        return None


class SessaoTifluxLimitada:
    """
    Mesma interface get/post/put de requests.Session. Lê a cota que a própria
    API informa (compartilhada por todo uso do token): com a cota na reserva,
    a próxima chamada espera a virada do minuto; um 429 espera e repete.
    Ex.: TifluxClient(..., session=SessaoTifluxLimitada(requests.Session(), reserva=5))
    """

    def __init__(
        self, sessao: SessaoHttp, reserva: int,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._sessao = sessao
        self._reserva = reserva
        self._dormir = dormir
        self._agora = agora
        # RateLimit-Reset da última resposta que deixou a cota na reserva;
        # a espera é calculada na próxima chamada, que pode vir bem depois.
        self._reset_pendente: str | None = None

    def get(self, url: str, **kwargs: object) -> requests.Response:
        return self._requisitar("GET", url, kwargs)

    def post(self, url: str, **kwargs: object) -> requests.Response:
        return self._requisitar("POST", url, kwargs)

    def put(self, url: str, **kwargs: object) -> requests.Response:
        return self._requisitar("PUT", url, kwargs)

    def _requisitar(self, metodo: str, url: str, kwargs: dict[str, object]) -> requests.Response:
        self._esperar_se_cota_na_reserva()
        resposta = self._repetir_enquanto_429(metodo, url, kwargs, self._sessao.request(metodo, url, **kwargs))
        self._registrar_cota(resposta)
        return resposta

    def _repetir_enquanto_429(
        self, metodo: str, url: str, kwargs: dict[str, object], resposta: requests.Response,
    ) -> requests.Response:
        # 429 = a API não processou a chamada, então repetir até um POST é seguro.
        for _ in range(REPETICOES_APOS_429):
            if resposta.status_code != 429:
                return resposta
            self._esperar(self._espera_apos_429(resposta), f"429 em {metodo} {url}")
            resposta = self._sessao.request(metodo, url, **kwargs)
        return resposta

    def _espera_apos_429(self, resposta: requests.Response) -> float:
        espera = segundos_ate_reset(resposta.headers.get("RateLimit-Reset"), self._agora())
        if espera is None:
            return ESPERA_PADRAO_429_SEGUNDOS
        # Piso de 1 s: um reset "já passado" pelo nosso relógio não deve
        # virar repetição imediata (relógios de cliente e API diferem).
        return max(espera, 1.0)

    def _registrar_cota(self, resposta: requests.Response) -> None:
        restantes = _restantes(resposta)
        na_reserva = restantes is not None and restantes <= self._reserva
        self._reset_pendente = resposta.headers.get("RateLimit-Reset") if na_reserva else None

    def _esperar_se_cota_na_reserva(self) -> None:
        espera = segundos_ate_reset(self._reset_pendente, self._agora())
        self._reset_pendente = None
        if espera is not None:
            self._esperar(espera, f"cota do minuto na reserva ({self._reserva})")

    def _esperar(self, segundos: float, motivo: str) -> None:
        if segundos <= 0:
            return
        log(f"⏳ Limite da API do Tiflux: aguardando {segundos:.0f}s — {motivo}")
        self._dormir(segundos)
