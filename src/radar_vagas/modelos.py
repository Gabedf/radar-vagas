"""Modelos internos do radar de vagas.

Os documentos que entram e saem do módulo (Curriculo, ConjuntoVagas,
RelatorioAderencia, Lacunas...) são os do contrato, no pacote
`carreira_contratos`. Os modelos DESTE arquivo são só de uso interno: guardam
os resultados intermediários de cada etapa do pipeline para que o motor de
regras, o relatório em Markdown e (depois) o agente explicador possam
consultá-los sem recalcular nada.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from carreira_contratos import AvaliacaoVaga, Lacunas, Nivel, NivelAtual, RelatorioAderencia, Requisito, Vaga

Status = Literal["atendido", "parcial", "faltante"]


class RequisitoBruto(BaseModel):
    """Requisito como sai de um extrator, antes da normalização.

    `trecho` é o texto da vaga de onde o requisito saiu; `habilidade` é o nome
    ainda não normalizado (pode ser "PostgreSQL", que vira "SQL" depois).
    O extrator LLM devolve uma lista destes (saída estruturada).
    """

    trecho: str = Field(min_length=1)
    habilidade: str = Field(min_length=1)
    nivel_minimo: Optional[Nivel] = None
    obrigatorio: bool = True


class Filtros(BaseModel):
    """Filtros de elegibilidade (F6). Lista vazia = aquele filtro não restringe nada.

    `niveis` guarda os níveis PRETENDIDOS pelo formando (ex.: "junior"); a
    tabela de compatibilidade em ranking.py diz quais níveis de vaga eles
    aceitam (junior aceita junior e trainee).
    """

    regimes: list[str] = []
    cidades: list[str] = []
    niveis: list[str] = []

    def vazio(self) -> bool:
        return not (self.regimes or self.cidades or self.niveis)


class Classificacao(BaseModel):
    """Resultado da regra R2 para UM requisito de UMA vaga."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    requisito: Requisito
    rotulo: str  # texto que vai para as listas atendidos/parciais/faltantes
    habilidade: str  # nome canônico efetivamente comparado (pode ser uma alternativa)
    nivel_pedido: Nivel
    nivel_atual: NivelAtual
    status: Status
    credito: float  # 1.0, 0.5 ou 0.0
    peso: int  # 2 (obrigatório) ou 1 (desejável)


class AvaliacaoInterna(BaseModel):
    """Avaliação completa de uma vaga (R1–R4 + elegibilidade de R5)."""

    id_vaga: str
    nota: int
    classificacoes: list[Classificacao]
    elegivel: bool = True
    motivos_filtro: list[str] = []
    obrigatorios_total: int = 0
    obrigatorios_atendidos: int = 0
    desejaveis_total: int = 0
    desejaveis_atendidos: int = 0
    justificativa: str

    @property
    def fracao_obrigatorios(self) -> float:
        """Fração de obrigatórios totalmente atendidos (critério de desempate de R6)."""
        if not self.obrigatorios_total:
            return 0.0
        return self.obrigatorios_atendidos / self.obrigatorios_total

    def por_status(self, status: Status) -> list[Classificacao]:
        return [c for c in self.classificacoes if c.status == status]

    def para_contrato(self) -> AvaliacaoVaga:
        """Converte para o AvaliacaoVaga do contrato."""
        return AvaliacaoVaga(
            id_vaga=self.id_vaga,
            nota=self.nota,
            requisitos_atendidos=[c.rotulo for c in self.por_status("atendido")],
            requisitos_parciais=[c.rotulo for c in self.por_status("parcial")],
            requisitos_faltantes=[c.rotulo for c in self.por_status("faltante")],
            justificativa=self.justificativa,
        )


class Ranking(BaseModel):
    """Resultado de R5–R7: avaliações ordenadas, recomendação e mais pedidas."""

    avaliacoes: list[AvaliacaoInterna]  # já ordenadas (R6)
    id_vaga_recomendada: str
    justificativa_recomendacao: str
    elegiveis: list[str]  # ids das vagas que passam nos filtros, na ordem do ranking
    competencias_mais_pedidas: list[str]
    contagem_competencias: dict[str, int] = {}


class ResultadoRadar(BaseModel):
    """Tudo o que uma execução do radar produz.

    `relatorio` e `lacunas` são os documentos do contrato; o resto é o
    "rastro" do cálculo, útil para o relatório em Markdown e para o agente
    explicador responder perguntas com os números calculados.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    relatorio: RelatorioAderencia
    lacunas: Lacunas
    markdown: str
    vagas_estruturadas: list[Vaga]
    avaliacoes: list[AvaliacaoInterna]
    elegiveis: list[str]
    filtros: Filtros
    contagem_competencias: dict[str, int] = {}
    nao_mapeadas: list[str] = []
    avisos: list[str] = []
    origem_extracao: str = "regras"
