"""Duplos de teste para GlpiClient/TifluxClient — implementam a mesma interface
pública usada por sync.processamento_chamado e pelos módulos de followups,
sem depender de HTTP real."""

from datetime import datetime, timezone

from sync.panorama_tiflux import PanoramaTiflux


def panorama_de_teste(
    abertos: tuple = (), atualizados: tuple = (), mudancas: tuple = (), varredura_completa: tuple = (),
) -> PanoramaTiflux:
    """Panorama do Tiflux montado à mão (spec 008); o padrão não tem nenhum ticket aberto nem atualizado."""
    return PanoramaTiflux(
        datetime(2026, 10, 7, 19, 30, tzinfo=timezone.utc),
        frozenset(abertos), frozenset(atualizados), tuple(mudancas), tuple(varredura_completa),
    )


class FakeGlpiClient:
    def __init__(self):
        self.tickets: dict[int, dict] = {}
        self.status_ticket_ausente = 404
        self.grupo_observador: dict[int, tuple[bool, str | None]] = {}
        self.followups: dict[int, list[dict]] = {}
        self.requerentes: dict[int, tuple[str, str | None, int | None]] = {}
        self.nomes_usuarios: dict[int, str] = {}
        self.telefones_chamado: dict[int, str] = {}
        self.anexos: dict[int, tuple[list, list]] = {}
        self.anexos_followup: dict[int, tuple[list, list]] = {}
        self.followups_criados: list[dict] = []
        self.proximo_id_followup = 1000
        self.erro_ao_criar_followup: str | None = None
        self.chamados_encerrados: list[tuple[int, int]] = []
        self.resultado_encerrar_chamado: tuple[bool, str | None] = (True, None)
        self.titulos_atualizados: list[tuple[int, str]] = []
        self.resultado_atualizar_titulo: tuple[bool, str | None] = (True, None)
        self.tecnicos_atribuidos_glpi: list[tuple[int, int]] = []
        self.resultado_atribuir_tecnico_glpi: tuple[bool, str | None] = (True, None)
        self.tecnico_ja_atribuido: dict[int, int | None] = {}
        self.solucoes_registradas: list[tuple[int, str]] = []
        self.resultado_registrar_solucao: tuple[bool, str | None] = (True, None)
        self.ja_tem_solucao: dict[int, bool] = {}
        self.status_restaurados_para_novo: list[int] = []
        self.resultado_voltar_status_para_novo: tuple[bool, str | None] = (True, None)

    def chamado_tem_grupo_observador(self, id_chamado, ids_grupo_observador):
        return self.grupo_observador.get(id_chamado, (True, None))

    def obter_ticket(self, id_chamado):
        ticket = self.tickets.get(id_chamado)
        if ticket is None:
            return None, self.status_ticket_ausente
        return ticket, 200

    def obter_requerente(self, id_chamado, ticket):
        return self.requerentes.get(id_chamado, ("Desconhecido", None, None))

    def obter_telefone_chamado(self, id_chamado):
        return self.telefones_chamado.get(id_chamado)

    def obter_nome_usuario(self, id_usuario):
        return self.nomes_usuarios.get(id_usuario, "Desconhecido")

    def obter_anexos(self, id_chamado, tamanho_maximo_mb):
        return self.anexos.get(id_chamado, ([], []))

    def obter_anexos_do_followup(self, id_followup, tamanho_maximo_mb):
        return self.anexos_followup.get(id_followup, ([], []))

    def obter_followups(self, id_chamado):
        return self.followups.get(id_chamado, [])

    def criar_followup(self, id_chamado, conteudo_html, is_private=0, users_id=None):
        if self.erro_ao_criar_followup:
            return None, self.erro_ao_criar_followup
        self.proximo_id_followup += 1
        self.followups_criados.append({
            "id_chamado": id_chamado, "conteudo": conteudo_html, "is_private": is_private, "users_id": users_id,
        })
        return self.proximo_id_followup, None

    def encerrar_chamado(self, id_chamado, status):
        self.chamados_encerrados.append((id_chamado, status))
        return self.resultado_encerrar_chamado

    def atualizar_titulo(self, id_chamado, titulo):
        self.titulos_atualizados.append((id_chamado, titulo))
        return self.resultado_atualizar_titulo

    def atribuir_tecnico(self, id_chamado, id_usuario):
        self.tecnicos_atribuidos_glpi.append((id_chamado, id_usuario))
        return self.resultado_atribuir_tecnico_glpi

    def tecnico_atribuido(self, id_chamado):
        return self.tecnico_ja_atribuido.get(id_chamado)

    def registrar_solucao(self, id_chamado, conteudo):
        self.solucoes_registradas.append((id_chamado, conteudo))
        return self.resultado_registrar_solucao

    def solucao_registrada(self, id_chamado):
        return self.ja_tem_solucao.get(id_chamado, False)

    def voltar_status_para_novo(self, id_chamado):
        self.status_restaurados_para_novo.append(id_chamado)
        return self.resultado_voltar_status_para_novo


class FakeTifluxClient:
    def __init__(self):
        self.cliente_id = 762707
        self.mesas_validas: set[int] | None = None
        self.id_solicitante = (3758056, "Ju STII (Padrão)")
        self.solicitantes_pedidos: list[tuple[str, str | None, str | None]] = []
        self.resultado_criar_ticket: tuple[str | None, str | None] = ("T-1", None)
        self.resultado_buscar_ticket_existente: tuple[str | None, str | None] = (None, None)
        self.ticket_tiflux: dict | None = {}
        self.resultado_atribuir_tecnico: tuple[bool, int, str] = (True, 200, "")
        self.resultado_anexos = (0, 0, [])
        self.tickets_criados: list[dict] = []
        self.respostas: list[dict] = []
        self.comunicacoes: list[dict] = []
        self.publicacoes: list[tuple] = []
        self.resposta_publicacao = _FakeHttpResponse(201, {"id": 555})
        self.tickets_reabertos: list[str] = []
        self.resultado_reabrir_ticket: tuple[bool, str | None] = (True, None)
        # Simula o que o Tiflux devolve no GET depois de reabrir (spec 006):
        # None mantém o ticket como estava, só que aberto.
        self.ticket_apos_reabrir: dict | None = None
        self.falhar_get_apos_reabrir = False
        self.tecnicos_atribuidos: list[tuple[str, int]] = []
        self.tickets_atualizados: list[dict] = []
        self.inicios_listagem_atualizados: list = []
        self.tickets_abertos: list[dict] = []
        # Exceção levantada pela listagem correspondente (spec 008), ou None.
        self.falha_listagem_atualizados: Exception | None = None
        self.falha_listagem_abertos: Exception | None = None
        self.listagens_com_falha = 0
        # Simula listar_respostas com falha: devolve [] e conta, como o cliente real.
        self.falhar_listagem_respostas = False
        self.requisicoes_enviadas = 0

    def validar_mesa_do_cliente(self, id_mesa):
        return True if self.mesas_validas is None else id_mesa in self.mesas_validas

    def obter_ticket(self, ticket_number):
        return self.ticket_tiflux, (200 if self.ticket_tiflux is not None else 404)

    def obter_id_solicitante(self, nome_glpi, email_glpi, telefone=None):
        self.solicitantes_pedidos.append((nome_glpi, email_glpi, telefone))
        return self.id_solicitante

    def buscar_ticket_por_chamado_glpi(self, id_chamado):
        return self.resultado_buscar_ticket_existente

    def criar_ticket(self, form_data):
        self.tickets_criados.append(form_data)
        return self.resultado_criar_ticket

    def atribuir_tecnico(self, ticket_number, id_tecnico):
        self.tecnicos_atribuidos.append((ticket_number, id_tecnico))
        return self.resultado_atribuir_tecnico

    def enviar_anexos(self, ticket_number, anexos):
        return self.resultado_anexos

    def listar_tickets_atualizados_desde(self, inicio_utc, tamanho_pagina, max_paginas):
        self.inicios_listagem_atualizados.append(inicio_utc)
        if self.falha_listagem_atualizados:
            raise self.falha_listagem_atualizados
        return self.tickets_atualizados

    def listar_tickets_abertos(self, tamanho_pagina, max_paginas):
        if self.falha_listagem_abertos:
            raise self.falha_listagem_abertos
        return self.tickets_abertos

    def listar_respostas(self, ticket_number, tamanho_pagina, max_paginas):
        if self.falhar_listagem_respostas:
            self.listagens_com_falha += 1
            return []
        return self.respostas

    def listar_comunicacoes_internas(self, ticket_number, tamanho_pagina, max_paginas):
        return self.comunicacoes

    def publicar_comunicacao_interna(self, ticket_number, conteudo):
        self.publicacoes.append(("interna", ticket_number, conteudo))
        return self.resposta_publicacao

    def publicar_resposta_cliente(self, ticket_number, conteudo, nome_requerente, anexos=None):
        self.publicacoes.append(("cliente", ticket_number, conteudo, nome_requerente, anexos or []))
        return self.resposta_publicacao

    def reabrir_ticket(self, ticket_number, motivo_reprovacao):
        self.tickets_reabertos.append((ticket_number, motivo_reprovacao))
        sucesso, erro = self.resultado_reabrir_ticket
        if not sucesso or self.ticket_tiflux is None:
            return sucesso, erro
        self.ticket_tiflux = self.ticket_apos_reabrir or {**self.ticket_tiflux, "is_closed": False}
        if self.falhar_get_apos_reabrir:
            self.ticket_tiflux = None
        return sucesso, erro



class FakeTifluxClientContador(FakeTifluxClient):
    """
    FakeTifluxClient que registra em `requisicoes` o nome de cada método que,
    no cliente real, faz requisição HTTP (spec 008, critério 1).
    """

    _METODOS_HTTP = frozenset({
        "obter_ticket", "listar_tickets_atualizados_desde", "listar_tickets_abertos", "listar_respostas",
        "listar_comunicacoes_internas", "publicar_resposta_cliente", "publicar_comunicacao_interna",
        "reabrir_ticket", "atribuir_tecnico", "enviar_anexos",
    })

    def __init__(self):
        super().__init__()
        self.requisicoes: list[str] = []

    def __getattribute__(self, nome):
        if nome in type(self)._METODOS_HTTP:
            object.__getattribute__(self, "requisicoes").append(nome)
        return object.__getattribute__(self, nome)

class _FakeHttpResponse:
    def __init__(self, status_code, json_data, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data
