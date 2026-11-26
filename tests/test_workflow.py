"""O Workflow do Agno ("Radar de vagas") dá exatamente o mesmo resultado do pipeline."""

import pytest

from radar_vagas.extrator_regras import ExtratorRegras
from radar_vagas.lacunas import ErroInvariante
from radar_vagas.modelos import Filtros
from radar_vagas.pipeline import executar_radar
from radar_vagas.workflow import NOME_WORKFLOW, criar_workflow, executar_workflow

from conftest import cv_de, perfil_de

# O cabeçalho tem a data/hora de geração, que muda entre execuções.
SEM_CABECALHO = {"relatorio": {"cabecalho"}, "lacunas": {"cabecalho"}}


def test_workflow_tem_as_cinco_etapas():
    wf = criar_workflow()
    assert wf.name == NOME_WORKFLOW
    assert [s.name for s in wf.steps] == ["extracao", "normalizacao", "comparacao", "ranqueamento", "consolidacao"]


@pytest.mark.parametrize("idf", ["f01", "f02", "f03"])
def test_mesmo_resultado_do_pipeline(idf, conjunto_30):
    cv, perfil = cv_de(idf), perfil_de(idf)
    esperado = executar_radar(cv, conjunto_30, perfil, extrator=ExtratorRegras())
    obtido = executar_workflow(cv, conjunto_30, perfil, extrator=ExtratorRegras())
    assert obtido.model_dump(exclude=SEM_CABECALHO) == esperado.model_dump(exclude=SEM_CABECALHO)
    assert obtido.markdown == esperado.markdown


def test_f01_recomenda_vf01_no_exemplo(cv_f01, perfil_f01, conjunto_exemplo):
    r = executar_workflow(cv_f01, conjunto_exemplo, perfil_f01, extrator=ExtratorRegras())
    assert r.relatorio.id_vaga_recomendada == "vf01"
    assert [a.nota for a in r.relatorio.avaliacoes] == [82, 43, 43]


def test_filtros_da_linha_de_comando(cv_f01, perfil_f01, conjunto_30):
    filtros = Filtros(regimes=["presencial"])
    esperado = executar_radar(cv_f01, conjunto_30, perfil_f01, filtros, ExtratorRegras())
    obtido = executar_workflow(cv_f01, conjunto_30, perfil_f01, filtros, ExtratorRegras())
    assert obtido.elegiveis == esperado.elegiveis
    assert obtido.relatorio.id_vaga_recomendada == esperado.relatorio.id_vaga_recomendada


def test_erro_numa_etapa_interrompe_o_workflow(cv_f01, conjunto_30, monkeypatch):
    import radar_vagas.workflow as wf

    def quebra(*args, **kwargs):
        raise ErroInvariante("teste")

    monkeypatch.setattr(wf, "etapa_consolidacao", quebra)
    with pytest.raises(ErroInvariante):
        executar_workflow(cv_f01, conjunto_30, extrator=ExtratorRegras())
