"""Testes de filtros, ranking, recomendação e competências mais pedidas (R5–R7)."""

from carreira_contratos import Requisito, Vaga

from radar_vagas.modelos import AvaliacaoInterna, Filtros
from radar_vagas.ranking import (
    combinar_filtros, competencias_mais_pedidas, filtros_do_perfil, motivos_exclusao, normalizar_cidade, ordenar,
    ranquear,
)


def _vaga(id_vaga, cidade="Vitória - ES", regime="hibrido", nivel="junior", habilidades=("SQL",)):
    return Vaga(id_vaga=id_vaga, titulo="t", empresa="e", cidade=cidade, regime=regime, nivel=nivel, descricao="d",
                requisitos=[Requisito(descricao=h, habilidade=h, obrigatorio=True) for h in habilidades])


def _aval(id_vaga, nota, obr_ok=0, obr_total=1, elegivel=True):
    return AvaliacaoInterna(id_vaga=id_vaga, nota=nota, classificacoes=[], elegivel=elegivel,
                            motivos_filtro=[] if elegivel else ["fora"], obrigatorios_total=obr_total,
                            obrigatorios_atendidos=obr_ok, justificativa="j")


def test_normalizar_cidade():
    assert normalizar_cidade("Vitória - ES") == normalizar_cidade("vitoria") == "vitoria"
    assert normalizar_cidade("Vila Velha/ES") == "vila velha"


def test_filtros_do_perfil_f01(perfil_f01):
    f = filtros_do_perfil(perfil_f01)
    assert f.regimes == ["hibrido", "remoto"] and f.cidades == ["Serra", "Vitória"] and f.niveis == ["junior"]
    assert filtros_do_perfil(None).vazio()


def test_linha_de_comando_substitui_so_o_que_foi_passado(perfil_f01):
    f = combinar_filtros(filtros_do_perfil(perfil_f01), Filtros(regimes=["presencial"]))
    assert f.regimes == ["presencial"] and f.cidades == ["Serra", "Vitória"]


def test_motivos_exclusao():
    f = Filtros(regimes=["hibrido", "remoto"], cidades=["Serra", "Vitória"], niveis=["junior"])
    assert motivos_exclusao(_vaga("a"), f) == []
    assert motivos_exclusao(_vaga("b", nivel="trainee"), f) == []  # junior aceita trainee
    assert "nível pleno" in motivos_exclusao(_vaga("c", nivel="pleno"), f)[0]
    assert "regime presencial" in motivos_exclusao(_vaga("d", regime="presencial"), f)[0]
    assert "cidade Cariacica" in motivos_exclusao(_vaga("e", cidade="Cariacica - ES"), f)[0]
    # Vaga remota dispensa a cidade.
    assert motivos_exclusao(_vaga("f", cidade="São Paulo - SP", regime="remoto"), f) == []
    # Estágio só aceita estágio.
    assert motivos_exclusao(_vaga("g", nivel="junior"), Filtros(niveis=["estagio"]))
    # Sem filtros, tudo passa.
    assert motivos_exclusao(_vaga("h", nivel="senior", regime="presencial"), Filtros()) == []


def test_ordem_e_desempates():
    avals = [_aval("b", 50, 1, 2), _aval("a", 50, 1, 2), _aval("c", 50, 2, 2), _aval("d", 90)]
    assert [a.id_vaga for a in ordenar(avals)] == ["d", "c", "a", "b"]


def test_recomenda_a_primeira_elegivel():
    vagas = [_vaga("x"), _vaga("y")]
    r = ranquear([_aval("x", 90, elegivel=False), _aval("y", 70)], vagas, Filtros(niveis=["junior"]))
    assert r.id_vaga_recomendada == "y" and r.elegiveis == ["y"]
    assert [a.nota for a in r.avaliacoes] == [90, 70]


def test_sem_elegiveis_recomenda_a_melhor_com_aviso():
    vagas = [_vaga("x"), _vaga("y")]
    r = ranquear([_aval("x", 40, elegivel=False), _aval("y", 70, elegivel=False)], vagas, Filtros(niveis=["estagio"]))
    assert r.id_vaga_recomendada == "y"
    assert r.justificativa_recomendacao.startswith("Atenção: nenhuma vaga passa nos filtros")


def test_competencias_mais_pedidas():
    vagas = [_vaga("1", habilidades=("SQL", "Python")), _vaga("2", habilidades=("SQL", "Git")),
             _vaga("3", habilidades=("SQL", "Python"))]
    assert competencias_mais_pedidas(vagas) == ["SQL", "Python", "Git"]
    assert competencias_mais_pedidas(vagas, n=1) == ["SQL"]
