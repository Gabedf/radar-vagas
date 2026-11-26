"""Testes da consolidação das lacunas (R8) e das invariantes do verificador."""

import pytest

from carreira_contratos import Lacuna
from carreira_contratos.verificar import Relatorio, _checar_lacunas

from radar_vagas.extrator_regras import ExtratorRegras
from radar_vagas.lacunas import ErroInvariante, checar_invariantes, e_frequente
from radar_vagas.pipeline import executar_radar

from conftest import cv_de, perfil_de


def test_exemplo_f01_reproduz_as_lacunas_do_kit(cv_f01, perfil_f01, conjunto_exemplo):
    """Com as 3 vagas do exemplo e o perfil do f01: Power BI (alta) e Apache Airflow (baixa), como no kit."""
    r = executar_radar(cv_f01, conjunto_exemplo, perfil_f01, extrator=ExtratorRegras())
    itens = [(l.habilidade, l.nivel_atual, l.nivel_necessario, l.prioridade, l.obrigatoria, l.frequencia,
              l.vagas_relacionadas) for l in r.lacunas.itens]
    assert itens == [
        ("Power BI", "basico", "intermediario", "alta", True, 1, ["vf01"]),
        ("Apache Airflow", "nenhum", "basico", "baixa", False, 1, ["vf01"]),
    ]
    assert r.lacunas.id_vaga_alvo == "vf01"


@pytest.mark.parametrize("idf", ["f01", "f02", "f03"])
def test_lacunas_passam_no_verificador(idf, conjunto_30):
    cv = cv_de(idf)
    r = executar_radar(cv, conjunto_30, perfil_de(idf), extrator=ExtratorRegras())
    rel = Relatorio()
    _checar_lacunas(r.lacunas.itens, cv, rel, "Lacunas")
    assert rel.erros == []
    ids = {v.id_vaga for v in conjunto_30.vagas}
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    chaves = [ordem[l.prioridade] for l in r.lacunas.itens]
    assert chaves == sorted(chaves)
    for l in r.lacunas.itens:
        assert set(l.vagas_relacionadas) <= set(r.elegiveis) <= ids  # só vagas elegíveis
        assert l.frequencia == len(l.vagas_relacionadas)


def test_lacuna_usa_o_nome_original_do_curriculo(cv_f01, perfil_f01, conjunto_30):
    r = executar_radar(cv_f01, conjunto_30, perfil_f01, extrator=ExtratorRegras())
    power_bi = next(l for l in r.lacunas.itens if l.habilidade == "Power BI")
    assert power_bi.nivel_atual == "basico" and power_bi.prioridade == "alta"  # obrigatória na recomendada


def test_frequente_exige_duas_vagas_e_30_por_cento():
    assert not e_frequente(1, 1)  # uma vaga isolada não é tendência
    assert e_frequente(2, 6) and not e_frequente(2, 7)
    assert e_frequente(3, 10)


def test_checar_invariantes_detecta_incoerencias(cv_f01):
    with pytest.raises(ErroInvariante):  # o currículo diz intermediario
        checar_invariantes([Lacuna(habilidade="SQL", nivel_atual="basico", nivel_necessario="avancado",
                                   prioridade="alta", obrigatoria=True, frequencia=1)], cv_f01)
    with pytest.raises(ErroInvariante):  # já tem o nível necessário
        checar_invariantes([Lacuna(habilidade="SQL", nivel_atual="intermediario", nivel_necessario="intermediario",
                                   prioridade="alta", obrigatoria=True, frequencia=1)], cv_f01)
    checar_invariantes([Lacuna(habilidade="Docker", nivel_atual="nenhum", nivel_necessario="basico",
                               prioridade="baixa", obrigatoria=False, frequencia=1)], cv_f01)
