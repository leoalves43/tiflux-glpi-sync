"""Escritas no GLPI da abertura Tiflux -> GLPI (spec 009), na sessão já autenticada.

Fora de glpi_client.py só pelo limite de 500 linhas; obtido com
GlpiClient.cliente_abertura(), que compartilha sessão, headers e timeout.
"""

import json
from dataclasses import dataclass

import requests
from requests import RequestException

from sync.config import log

# Plugin Fields: bloco "Telefone / Linhas" do chamado (ver glpi_client.obter_telefone_chamado).
_ITEMTYPE_TELEFONE_CHAMADO = "PluginFieldsTickettelefonelinha"
_ID_CONTAINER_TELEFONE = 3  # plugin_fields_containers_id visto ao vivo no GLPI #34900


@dataclass(frozen=True)
class ResultadoCriacaoGlpi:
    """
    `incerto`: o chamado PODE ter sido criado (timeout, 5xx, resposta sem id) —
    quem chama não deve tentar de novo sozinho. Recusa 4xx é certa: nada foi criado.
    Ex.: ResultadoCriacaoGlpi(35001, None, False)
    """

    id_glpi: int | None
    erro: str | None
    incerto: bool


class GlpiAberturaClient:
    def __init__(self, url_base: str, headers: dict[str, str], session: requests.Session, timeout: int) -> None:
        self._url_base = url_base
        self._headers = headers
        self._session = session
        self._timeout = timeout

    def buscar_usuario_por_email(self, email: str | None) -> int | None:
        """
        users_id do único usuário do GLPI com esse e-mail (exato, sem caixa);
        None se nenhum, ambíguo ou erro. searchText faz LIKE, daí o filtro aqui.
        Ex.: glpi_abertura.buscar_usuario_por_email("paula.avila@caraguatatuba.sp.gov.br") -> 173
        """
        if not email:
            return None
        emails = _lista_json(self._get("/UserEmail", params={"searchText[email]": email}))
        if emails is None:
            log(f"⚠️ Falha ao buscar usuário do GLPI pelo e-mail {email} (esperado lista JSON)")
            return None
        ids = {e.get("users_id") for e in emails if (e.get("email") or "").lower() == email.lower()}
        if len(ids) > 1:
            log(f"⚠️ E-mail {email} pertence a {len(ids)} usuários do GLPI ({sorted(ids)}) — usando o requerente padrão")
        return ids.pop() if len(ids) == 1 else None

    def criar_chamado(self, campos: dict) -> ResultadoCriacaoGlpi:
        """
        POST /Ticket com o input wrapper do GLPI.
        Ex.: glpi_abertura.criar_chamado({"name": "#364990 - Erro", ...}) -> ResultadoCriacaoGlpi(35001, None, False)
        """
        try:
            resp = self._session.post(
                f"{self._url_base}/Ticket", json={"input": campos}, headers=self._headers, timeout=self._timeout,
            )
        except RequestException as e:
            return ResultadoCriacaoGlpi(None, f"Falha de rede ao criar chamado no GLPI: {e}", True)
        return _resultado_criacao(resp)

    def gravar_telefone(self, id_glpi: int, telefone: str) -> str | None:
        """
        Telefone no plugin Fields: atualiza a linha do chamado se existir, senão
        cria. Devolve o erro, ou None se gravou.
        Ex.: glpi_abertura.gravar_telefone(35001, "1238971100") -> None
        """
        id_linha = self._linha_telefone(id_glpi)
        if id_linha is not None:
            caminho, metodo = f"/{_ITEMTYPE_TELEFONE_CHAMADO}/{id_linha}", self._session.put
            campos: dict = {"telefonefield": telefone}
        else:
            caminho, metodo = f"/{_ITEMTYPE_TELEFONE_CHAMADO}", self._session.post
            campos = {"itemtype": "Ticket", "items_id": id_glpi,
                      "plugin_fields_containers_id": _ID_CONTAINER_TELEFONE, "telefonefield": telefone}
        resp = metodo(f"{self._url_base}{caminho}", json={"input": campos}, headers=self._headers, timeout=self._timeout)
        if resp.status_code in (200, 201):
            return None
        return f"Falha ao gravar telefone {telefone} no chamado #{id_glpi} ({resp.status_code}): {resp.text}"

    def anexar_documento(self, id_glpi: int, nome_arquivo: str, conteudo: bytes, mime: str) -> str | None:
        """
        POST /Document multipart (uploadManifest + filename[0]) já vinculado ao
        chamado via itemtype/items_id. Devolve o erro, ou None se anexou.
        Ex.: glpi_abertura.anexar_documento(35001, "print.png", b"...", "image/png") -> None
        """
        manifesto = {"input": {"name": nome_arquivo, "_filename": [nome_arquivo],
                               "itemtype": "Ticket", "items_id": id_glpi}}
        arquivos = {"uploadManifest": (None, json.dumps(manifesto), "application/json"),
                    "filename[0]": (nome_arquivo, conteudo, mime)}
        resp = self._session.post(
            f"{self._url_base}/Document", files=arquivos, headers=self._headers, timeout=self._timeout,
        )
        if resp.status_code in (200, 201):
            return None
        return f"'{nome_arquivo}': falha ao anexar no chamado #{id_glpi} ({resp.status_code}): {resp.text[:200]}"

    def _linha_telefone(self, id_glpi: int) -> int | None:
        linhas = _lista_json(self._get(f"/{_ITEMTYPE_TELEFONE_CHAMADO}", params={"searchText[items_id]": id_glpi}))
        for linha in linhas or []:
            if linha.get("itemtype") == "Ticket" and linha.get("items_id") == id_glpi:
                return linha.get("id")
        return None

    def _get(self, caminho: str, **kwargs) -> requests.Response:
        return self._session.get(f"{self._url_base}{caminho}", headers=self._headers, timeout=self._timeout, **kwargs)


def _lista_json(resp: requests.Response) -> list[dict] | None:
    """Corpo da listagem do GLPI, ou None se não veio 200/206 com uma lista JSON."""
    if resp.status_code not in (200, 206):
        return None
    try:
        dados = resp.json()
    except ValueError:
        return None
    return dados if isinstance(dados, list) else None


def _resultado_criacao(resp: requests.Response) -> ResultadoCriacaoGlpi:
    if 400 <= resp.status_code < 500:
        return ResultadoCriacaoGlpi(None, f"GLPI recusou o chamado ({resp.status_code}): {resp.text[:300]}", False)
    if resp.status_code not in (200, 201):
        return ResultadoCriacaoGlpi(None, f"Resposta inesperada do GLPI ao criar chamado ({resp.status_code}): {resp.text[:300]}", True)
    try:
        dados = resp.json()
    except ValueError:
        dados = None
    id_glpi = dados.get("id") if isinstance(dados, dict) else None
    if not id_glpi:
        return ResultadoCriacaoGlpi(None, f"Chamado criado no GLPI sem id na resposta: {resp.text[:300]}", True)
    return ResultadoCriacaoGlpi(int(id_glpi), None, False)
