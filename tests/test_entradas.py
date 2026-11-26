"""Testes da leitura das vagas (F1)."""

import pytest

from carreira_contratos import ConjuntoVagas, Vaga

from radar_vagas.entradas import carregar_pasta_texto, carregar_vagas, deduzir_nivel, deduzir_regime, vaga_de_texto

from conftest import INSUMOS


def test_cinco_vagas_de_texto_viram_vagas_validas():
    conjunto = carregar_pasta_texto(INSUMOS / "vagas_texto")
    assert isinstance(conjunto, ConjuntoVagas)
    assert [v.id_vaga for v in conjunto.vagas] == ["v01", "v02", "v03", "v04", "v05"]
    for v in conjunto.vagas:
        Vaga.model_validate(v.model_dump())
        assert v.requisitos == []
    v01 = conjunto.vagas[0]
    assert (v01.titulo, v01.empresa, v01.cidade) == ("Estágio em Análise de Dados", "Cais Alimentos S.A.", "Serra - ES")
    assert v01.nivel == "estagio"
    assert conjunto.cabecalho.modulo == "radar_vagas"


def test_texto_bate_com_o_json_nos_campos_explicitos(conjunto_30):
    por_id = {v.id_vaga: v for v in conjunto_30.vagas}
    for v in carregar_vagas(INSUMOS / "vagas_texto").vagas:
        j = por_id[v.id_vaga]
        assert (v.titulo, v.empresa, v.cidade, v.descricao) == (j.titulo, j.empresa, j.cidade, j.descricao)
        assert v.nivel == j.nivel  # nas 5 vagas o nível está no título
        assert len(v.responsabilidades) == len(j.responsabilidades) == 3


def test_v03_remoto_pelo_texto():
    v03 = carregar_vagas(INSUMOS / "vagas_texto" / "v03.txt").vagas[0]
    assert (v03.id_vaga, v03.regime, v03.nivel) == ("v03", "remoto", "pleno")


def test_heuristicas_de_nivel_e_regime():
    assert deduzir_nivel("Cientista de Dados Pleno", "") == "pleno"
    assert deduzir_nivel("Analista", "vaga para analista júnior") == "junior"
    assert deduzir_nivel("Analista", "", padrao="trainee") == "trainee"
    assert deduzir_regime("", "Benefícios: trabalho remoto.") == "remoto"
    assert deduzir_regime("", "dois dias de trabalho remoto por semana") == "hibrido"
    assert deduzir_regime("", "modelo híbrido") == "hibrido"
    assert deduzir_regime("", "sem pistas") == "presencial"
    assert deduzir_regime("", "sem pistas", padrao="remoto") == "remoto"


def test_texto_mal_formado():
    with pytest.raises(ValueError):
        vaga_de_texto("só uma linha", "x")
    with pytest.raises(ValueError):
        vaga_de_texto("Título\nEmpresa sem travessão\n\nDescrição", "x")
