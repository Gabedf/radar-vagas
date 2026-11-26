"""Workflow do Agno "Radar de vagas": as cinco etapas do pipeline como Steps.

    extração -> normalização -> comparação -> ranqueamento -> consolidação

Cada Step é uma função Python (executor) que chama a etapa correspondente de
`pipeline.py`; nenhuma regra é reimplementada aqui. O Workflow só organiza a
execução em etapas nomeadas (o que aparece nos logs e no AgentOS).

Como os dados passam de uma etapa para a outra:

- a ENTRADA do workflow (`EntradaRadar`: currículo, vagas, perfil, filtros)
  chega a todos os Steps em `step_input.input`;
- cada Step devolve seu produto em `StepOutput.content`, e o Step seguinte o
  lê com `step_input.get_step_output("<nome da etapa>")`;
- as dependências de execução (o extrator e o dicionário) ficam no
  `session_state` da execução, compartilhado entre os Steps (sem elas, por
  exemplo numa execução pela interface do AgentOS, valem regras + cache).

`executar_workflow` dá exatamente o mesmo resultado de `executar_radar`
(conferido em tests/test_workflow.py).
"""

from __future__ import annotations

from typing import Optional

from agno.workflow import HumanReview, OnError, Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel, ConfigDict

from carreira_contratos import ConjuntoVagas, Curriculo, PerfilCarreira, Vaga

from .extrator_regras import Extrator
from .modelos import AvaliacaoInterna, Filtros, Ranking, ResultadoRadar
from .normalizacao import Dicionario, dicionario_padrao
from .pipeline import (etapa_comparacao, etapa_consolidacao, etapa_extracao, etapa_normalizacao,
                       etapa_ranqueamento, extrator_padrao, itens_sem_habilidade)
from .ranking import combinar_filtros, filtros_do_perfil

NOME_WORKFLOW = "Radar de vagas"
ID_WORKFLOW = "radar-vagas-workflow"

EXTRACAO, NORMALIZACAO, COMPARACAO, RANQUEAMENTO, CONSOLIDACAO = (
    "extracao", "normalizacao", "comparacao", "ranqueamento", "consolidacao")


# ------------------------------------------------------- dados entre as etapas

class EntradaRadar(BaseModel):
    """Entrada do workflow: os documentos do contrato e os filtros finais."""

    curriculo: Curriculo
    conjunto: ConjuntoVagas
    filtros: Filtros = Filtros()  # já combinados (perfil + linha de comando)


class SaidaNormalizacao(BaseModel):
    vagas: list[Vaga]
    nao_mapeadas: list[str]
    avisos: list[str]


class SaidaComparacao(BaseModel):
    avaliacoes: list[AvaliacaoInterna]


def _entrada(step_input: StepInput) -> EntradaRadar:
    """Entrada do workflow. Pela interface do AgentOS ela chega como dict/JSON; aqui vira EntradaRadar."""
    dados = step_input.input
    if isinstance(dados, EntradaRadar):
        return dados
    if isinstance(dados, str):
        return EntradaRadar.model_validate_json(dados)
    return EntradaRadar.model_validate(dados)


def _dependencias(run_context) -> tuple[Extrator, Dicionario]:
    """Extrator e dicionário da execução (session_state); sem eles, os padrões (regras + cache)."""
    estado = (run_context.session_state if run_context is not None else None) or {}
    return estado.get("extrator") or extrator_padrao(), estado.get("dicionario") or dicionario_padrao()


def _produto(step_input: StepInput, etapa: str):
    """Produto (content) de uma etapa anterior."""
    saida = step_input.get_step_output(etapa)
    if saida is None or not saida.success:
        raise RuntimeError(f"a etapa '{etapa}' não produziu resultado")
    return saida.content


# ------------------------------------------------------------- os cinco Steps

def passo_extracao(step_input: StepInput, run_context) -> StepOutput:
    extrator, _ = _dependencias(run_context)
    return StepOutput(content=etapa_extracao(_entrada(step_input).conjunto, extrator))


def passo_normalizacao(step_input: StepInput, run_context) -> StepOutput:
    extrator, dic = _dependencias(run_context)
    vagas, nao_mapeadas, avisos = etapa_normalizacao(_produto(step_input, EXTRACAO), dic)
    if getattr(extrator, "origem", "desconhecida") == "regras":
        # Diagnóstico do dicionário: itens de requisito em que as regras não acharam habilidade.
        nao_mapeadas += itens_sem_habilidade(_entrada(step_input).conjunto, dic)
    return StepOutput(content=SaidaNormalizacao(vagas=vagas, nao_mapeadas=nao_mapeadas, avisos=avisos))


def passo_comparacao(step_input: StepInput, run_context) -> StepOutput:
    entrada = _entrada(step_input)
    _, dic = _dependencias(run_context)
    norm: SaidaNormalizacao = _produto(step_input, NORMALIZACAO)
    avaliacoes = etapa_comparacao(entrada.curriculo, norm.vagas, entrada.filtros, dic)
    return StepOutput(content=SaidaComparacao(avaliacoes=avaliacoes))


def passo_ranqueamento(step_input: StepInput, run_context) -> StepOutput:
    norm: SaidaNormalizacao = _produto(step_input, NORMALIZACAO)
    comp: SaidaComparacao = _produto(step_input, COMPARACAO)
    return StepOutput(content=etapa_ranqueamento(comp.avaliacoes, norm.vagas, _entrada(step_input).filtros))


def passo_consolidacao(step_input: StepInput, run_context) -> StepOutput:
    entrada = _entrada(step_input)
    extrator, dic = _dependencias(run_context)
    norm: SaidaNormalizacao = _produto(step_input, NORMALIZACAO)
    ranking: Ranking = _produto(step_input, RANQUEAMENTO)
    avisos = list(norm.avisos)
    if not ranking.elegiveis:
        avisos.append("nenhuma vaga passa nos filtros; a recomendação e as lacunas usam todas as vagas")
    origem = getattr(extrator, "origem", "desconhecida")
    resultado = etapa_consolidacao(entrada.curriculo, norm.vagas, ranking, entrada.filtros,
                                   norm.nao_mapeadas, avisos, origem, dic)
    return StepOutput(content=resultado)


def _passo(nome: str, descricao: str, executor) -> Step:
    # max_retries=0: as etapas são determinísticas, repetir não muda nada.
    # on_error=fail: um erro (ex.: invariante das lacunas) interrompe o workflow
    # e chega a quem chamou; o padrão do Agno seria pular a etapa e seguir.
    return Step(name=nome, description=descricao, executor=executor, max_retries=0,
                human_review=HumanReview(on_error=OnError.fail))


def criar_workflow(telemetria: bool = False) -> Workflow:
    return Workflow(
        id=ID_WORKFLOW,
        name=NOME_WORKFLOW,
        description="Extrai os requisitos das vagas, calcula a aderência em código, ranqueia e consolida as lacunas.",
        steps=[
            _passo(EXTRACAO, "F1/F2: requisitos de cada vaga (regras, LLM ou cache)", passo_extracao),
            _passo(NORMALIZACAO, "F3: nomes canônicos, nível conferido no texto, sem repetições", passo_normalizacao),
            _passo(COMPARACAO, "R1–R5: filtros e nota de cada vaga", passo_comparacao),
            _passo(RANQUEAMENTO, "R6–R7: ranking, recomendação e competências mais pedidas", passo_ranqueamento),
            _passo(CONSOLIDACAO, "R8/F9: lacunas, documentos do contrato e relatório Markdown", passo_consolidacao),
        ],
        telemetry=telemetria,
    )


def executar_workflow(curriculo: Curriculo, conjunto: ConjuntoVagas, perfil: Optional[PerfilCarreira] = None,
                      filtros: Optional[Filtros] = None, extrator: Optional[Extrator] = None,
                      telemetria: bool = False) -> ResultadoRadar:
    """Mesmos parâmetros e mesmo resultado de `pipeline.executar_radar`, via Workflow do Agno."""
    entrada = EntradaRadar(curriculo=curriculo, conjunto=conjunto,
                           filtros=combinar_filtros(filtros_do_perfil(perfil), filtros))
    estado = {"extrator": extrator or extrator_padrao(), "dicionario": dicionario_padrao()}
    saida = criar_workflow(telemetria).run(input=entrada, session_state=estado)
    resultado = saida.content
    if not isinstance(resultado, ResultadoRadar):  # não deveria acontecer com on_error=fail
        raise RuntimeError(f"o workflow terminou sem resultado ({saida.status}): {resultado}")
    return resultado
