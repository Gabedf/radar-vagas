"""Testes de ponta a ponta: pipeline, documentos e linha de comando."""

import json

import pytest

from carreira_contratos import ConjuntoVagas, Lacunas, RelatorioAderencia, carregar
from carreira_contratos.verificar import verificar

from radar_vagas.cli import main
from radar_vagas.extrator_regras import ExtratorRegras
from radar_vagas.modelos import Filtros
from radar_vagas.pipeline import executar_radar

from conftest import EXEMPLOS, INSUMOS, cv_de, perfil_de


@pytest.mark.parametrize("idf", ["f01", "f02", "f03"])
def test_ponta_a_ponta_passa_no_verificador(idf, conjunto_30):
    cv = cv_de(idf)
    r = executar_radar(cv, conjunto_30, perfil_de(idf), extrator=ExtratorRegras())
    # Os documentos validam contra os modelos do contrato...
    RelatorioAderencia.model_validate(r.relatorio.model_dump())
    Lacunas.model_validate(r.lacunas.model_dump())
    # ...e passam na mesma verificação do carreira-verificar.
    rel = verificar("radar_vagas", {"Curriculo": cv, "ConjuntoVagas": conjunto_30},
                    {"RelatorioAderencia": r.relatorio, "Lacunas": r.lacunas})
    assert rel.erros == []
    assert r.relatorio.cabecalho.modulo == "radar_vagas"
    assert r.relatorio.cabecalho.id_formando == idf
    assert len(r.relatorio.avaliacoes) == 30
    assert r.relatorio.id_vaga_recomendada in r.elegiveis
    assert "## Ranking das vagas" in r.markdown


def test_exemplo_do_kit_de_ponta_a_ponta(cv_f01, perfil_f01, conjunto_exemplo, relatorio_exemplo):
    """Extraindo as 3 vagas do exemplo pelas regras, as avaliações são as do gabarito do kit."""
    r = executar_radar(cv_f01, conjunto_exemplo, perfil_f01, extrator=ExtratorRegras())
    obtido = [(a.id_vaga, a.nota, a.requisitos_atendidos, a.requisitos_parciais, a.requisitos_faltantes)
              for a in r.relatorio.avaliacoes]
    esperado = [(a.id_vaga, a.nota, a.requisitos_atendidos, a.requisitos_parciais, a.requisitos_faltantes)
                for a in relatorio_exemplo.avaliacoes]
    assert obtido == esperado
    assert r.relatorio.id_vaga_recomendada == "vf01"
    assert r.relatorio.competencias_mais_pedidas[:3] == ["SQL", "Power BI", "Python"]


def test_recomendacoes_esperadas(conjunto_30):
    """Sanidade: cada formando recebe uma vaga da sua área e dentro dos filtros."""
    recs = {idf: executar_radar(cv_de(idf), conjunto_30, perfil_de(idf), extrator=ExtratorRegras())
            for idf in ("f01", "f02", "f03")}
    assert recs["f01"].relatorio.id_vaga_recomendada == "vf01"
    vagas = {v.id_vaga: v for v in conjunto_30.vagas}
    assert vagas[recs["f03"].relatorio.id_vaga_recomendada].nivel == "estagio"
    assert "Python" in vagas[recs["f02"].relatorio.id_vaga_recomendada].titulo or \
           "Back-end" in vagas[recs["f02"].relatorio.id_vaga_recomendada].titulo


def test_vaga_ja_estruturada_mantem_os_requisitos(cv_f01, relatorio_exemplo):
    conjunto = ConjuntoVagas(cabecalho=relatorio_exemplo.cabecalho, vagas=relatorio_exemplo.vagas_estruturadas)

    class Proibido:
        origem = "proibido"

        def extrair(self, vaga):
            raise AssertionError("não deveria extrair vagas que já têm requisitos")

    r = executar_radar(cv_f01, conjunto, extrator=Proibido())
    assert [a.nota for a in r.relatorio.avaliacoes] == [82, 43, 43]


def test_sem_perfil_todas_sao_elegiveis(cv_f01, conjunto_30):
    r = executar_radar(cv_f01, conjunto_30, extrator=ExtratorRegras())
    assert len(r.elegiveis) == 30


def test_filtros_explicitos(cv_f01, perfil_f01, conjunto_30):
    r = executar_radar(cv_f01, conjunto_30, perfil_f01, Filtros(cidades=["Cariacica"]), extrator=ExtratorRegras())
    vagas = {v.id_vaga: v for v in conjunto_30.vagas}
    assert all(vagas[i].cidade.startswith("Cariacica") or vagas[i].regime == "remoto" for i in r.elegiveis)


def test_cli_executar(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_REQUISITOS", str(tmp_path / "cache.json"))
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    saida = tmp_path / "f01"
    codigo = main(["executar", "--curriculo", str(EXEMPLOS / "f01" / "curriculo.json"),
                   "--vagas", str(INSUMOS / "conjunto_vagas.json"),
                   "--perfil", str(EXEMPLOS / "f01" / "perfil_carreira.json"), "--saida-dir", str(saida)])
    assert codigo == 0
    rel = carregar(saida / "relatorio_aderencia.json", RelatorioAderencia)
    assert rel.id_vaga_recomendada == "vf01"
    assert (saida / "lacunas.json").exists() and (saida / "relatorio.md").exists()
    assert len(json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))) == 30


def test_cli_vagas_em_texto(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_REQUISITOS", str(tmp_path / "cache.json"))
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    codigo = main(["executar", "--curriculo", str(EXEMPLOS / "f01" / "curriculo.json"),
                   "--vagas", str(INSUMOS / "vagas_texto"), "--saida-dir", str(tmp_path / "txt")])
    assert codigo == 0
    rel = carregar(tmp_path / "txt" / "relatorio_aderencia.json", RelatorioAderencia)
    assert {v.id_vaga for v in rel.vagas_estruturadas} == {"v01", "v02", "v03", "v04", "v05"}


def test_cli_erro_de_entrada_devolve_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    codigo = main(["executar", "--curriculo", str(tmp_path / "nao_existe.json"),
                   "--vagas", str(INSUMOS / "conjunto_vagas.json"), "--saida-dir", str(tmp_path / "x")])
    assert codigo == 2
    assert "Erro" in capsys.readouterr().err


def test_cli_extrator_llm_sem_modelo_devolve_2(tmp_path, monkeypatch, capsys):
    # Sem MODELO_LLM, --extrator llm é erro de configuração (código 2), com mensagem clara.
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    monkeypatch.setenv("MODELO_LLM", "")
    codigo = main(["executar", "--curriculo", str(EXEMPLOS / "f01" / "curriculo.json"),
                   "--vagas", str(INSUMOS / "conjunto_vagas.json"), "--extrator", "llm",
                   "--saida-dir", str(tmp_path / "x")])
    assert codigo == 2
    assert "MODELO_LLM" in capsys.readouterr().err
