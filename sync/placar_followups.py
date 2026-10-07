"""Contagens de uma execução da sincronização de followups (linha de resumo do log)."""

from dataclasses import dataclass


@dataclass
class PlacarFollowups:
    """
    Substitui o dict `totais` de chaves montadas por string
    (`totais[f"status_{status}"]`): um nome errado agora falha na hora.
    Ex.: placar = PlacarFollowups(); placar.contar_cascata(True); placar.cascata_sucesso -> 1
    """

    glpi_para_tiflux_sucesso: int = 0
    glpi_para_tiflux_erro: int = 0
    tiflux_para_glpi_sucesso: int = 0
    tiflux_para_glpi_erro: int = 0
    cascata_sucesso: int = 0
    cascata_erro: int = 0

    def somar_glpi_para_tiflux(self, sucessos: int, erros: int) -> None:
        self.glpi_para_tiflux_sucesso += sucessos
        self.glpi_para_tiflux_erro += erros

    def somar_tiflux_para_glpi(self, sucessos: int, erros: int) -> None:
        self.tiflux_para_glpi_sucesso += sucessos
        self.tiflux_para_glpi_erro += erros

    def contar_cascata(self, sucesso: bool) -> None:
        if sucesso:
            self.cascata_sucesso += 1
        else:
            self.cascata_erro += 1

    def resumo(self) -> str:
        """Ex.: PlacarFollowups().resumo() -> "Followups. GLPI->Tiflux: 0 ok / 0 erro | ..." """
        return (
            f"Followups. GLPI->Tiflux: {self.glpi_para_tiflux_sucesso} ok / {self.glpi_para_tiflux_erro} erro | "
            f"Tiflux->GLPI: {self.tiflux_para_glpi_sucesso} ok / {self.tiflux_para_glpi_erro} erro | "
            f"Encerramento/reabertura em cascata: {self.cascata_sucesso} ok / {self.cascata_erro} erro"
        )
