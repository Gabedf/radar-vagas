"""Testes do motor de regras (R1–R4), a parte mais importante do módulo."""

import pytest

from carreira_contratos import Curriculo, Habilidade, Idioma, Requisito, Vaga

from radar_vagas.motor import (
    PESO_DESEJAVEL, PESO_OBRIGATORIO, alternativas, arredondar, avaliar_vaga, calcular_nota,
    classificar, justificar, mapa_habilidades,
)


def test_ancora_notas_e_listas_do_exemplo_do_kit(cv_f01, relatorio_exemplo):
    """TESTE-ÂNCORA: com as vagas estruturadas do kit, o motor reproduz 82/43/43 e as listas."""
    mapa = mapa_habilidades(cv_f01)
    esperado = {a.id_vaga: a for a in relatorio_exemplo.avaliacoes}
    for vaga in relatorio_exemplo.vagas_estruturadas:
        aval = avaliar_vaga(vaga, mapa).para_contrato()
        gabarito = esperado[vaga.id_vaga]
        assert aval.nota == gabarito.nota, vaga.id_vaga
        assert aval.requisitos_atendidos == gabarito.requisitos_atendidos, vaga.id_vaga
        assert aval.requisitos_parciais == gabarito.requisitos_parciais, vaga.id_vaga
        assert aval.requisitos_faltantes == gabarito.requisitos_faltantes, vaga.id_vaga
    assert [esperado[i].nota for i in ("vf01", "vx01", "vx02")] == [82, 43, 43]


def test_mapa_habilidades_inclui_idiomas_e_ignora_tecnologias(cv_f01):
    mapa = mapa_habilidades(cv_f01)
    assert mapa["inglês"].nivel == "intermediario"
    assert mapa["sql"].nome_original == "SQL"
    # PostgreSQL e Matplotlib só aparecem em `tecnologias`: não contam (R1).
    assert "matplotlib" not in mapa
    assert len(mapa) == 8  # 7 habilidades + 1 idioma


def _cv(habilidades=(), idiomas=()):
    return Curriculo.model_validate({
        "cabecalho": {"modulo": "teste", "gerado_em": "2026-11-01T10:00:00-03:00", "id_formando": "t01"},
        "dados_pessoais": {"nome": "Teste", "email": "t@exemplo.com", "cidade": "Serra"},
        "habilidades": [Habilidade(nome=n, categoria="tecnica", nivel=nv).model_dump() for n, nv in habilidades],
        "idiomas": [Idioma(idioma=n, nivel=nv).model_dump() for n, nv in idiomas],
    })


def _req(hab, nivel=None, obrigatorio=True, descricao=None):
    return Requisito(descricao=descricao or hab, habilidade=hab, nivel_minimo=nivel, obrigatorio=obrigatorio)


def test_fluente_conta_como_avancado():
    mapa = mapa_habilidades(_cv(idiomas=[("Inglês", "fluente")]))
    assert classificar(_req("Inglês", "avancado"), mapa).status == "atendido"


def test_nomes_do_curriculo_passam_pelo_dicionario():
    mapa = mapa_habilidades(_cv(habilidades=[("PostgreSQL", "avancado")]))
    c = classificar(_req("SQL", "intermediario"), mapa)
    assert c.status == "atendido" and c.habilidade == "SQL"


def test_duas_entradas_no_mesmo_canonico_fica_o_maior_nivel():
    mapa = mapa_habilidades(_cv(habilidades=[("SQL", "basico"), ("PostgreSQL", "avancado")]))
    assert mapa["sql"].nivel == "avancado" and mapa["sql"].nome_original == "PostgreSQL"


@pytest.mark.parametrize("tem,pede,status,credito", [
    (None, "basico", "faltante", 0.0),
    ("basico", None, "atendido", 1.0),  # sem nível na vaga -> pede básico
    ("basico", "basico", "atendido", 1.0),
    ("avancado", "intermediario", "atendido", 1.0),
    ("basico", "intermediario", "parcial", 0.5),
    ("intermediario", "avancado", "parcial", 0.5),
    ("basico", "avancado", "parcial", 0.5),  # parcial não é graduado pela distância
])
def test_classificacao_r2(tem, pede, status, credito):
    mapa = mapa_habilidades(_cv(habilidades=[("Docker", tem)] if tem else []))
    c = classificar(_req("Docker", pede), mapa)
    assert (c.status, c.credito) == (status, credito)
    assert c.nivel_atual == (tem or "nenhum")


def test_pesos():
    assert classificar(_req("Git", obrigatorio=True), {}).peso == PESO_OBRIGATORIO == 2
    assert classificar(_req("Git", obrigatorio=False), {}).peso == PESO_DESEJAVEL == 1


def test_alternativas_valem_a_melhor_opcao():
    req = _req("Python", descricao="Python ou R para análise de dados")
    assert alternativas(req) == ["Python", "R"]
    mapa = mapa_habilidades(_cv(habilidades=[("R", "intermediario")]))
    c = classificar(req, mapa)
    assert c.status == "atendido" and c.habilidade == "R"
    # Sem "ou" no texto, não há alternativas.
    assert alternativas(_req("Python", descricao="Python com pandas")) == ["Python"]


def test_arredondamento_meio_para_cima():
    assert arredondar(42.5) == 43  # round(42.5) daria 42
    assert arredondar(42.49) == 42
    assert arredondar(81.818) == 82
    assert arredondar(0) == 0 and arredondar(100) == 100


def test_nota_extremos_e_vaga_vazia():
    mapa = mapa_habilidades(_cv(habilidades=[("Git", "avancado")]))
    assert calcular_nota([classificar(_req("Git"), mapa)]) == 100
    assert calcular_nota([classificar(_req("Docker"), mapa)]) == 0
    assert calcular_nota([]) == 0


def test_nota_tres_setimos():
    """2 (atendido) + 1 (parcial) + 0 + 0 sobre pesos 2+2+2+1: 3/7 = 42,86 -> 43."""
    mapa = mapa_habilidades(_cv(habilidades=[("SQL", "intermediario"), ("Power BI", "basico")]))
    cs = [classificar(r, mapa) for r in (
        _req("SQL", "intermediario"), _req("Power BI", "avancado"), _req("Excel", "avancado"),
        _req("DAX", obrigatorio=False),
    )]
    assert calcular_nota(cs) == 43


def test_justificativa_menciona_parcial_falta_e_filtro(cv_f01, relatorio_exemplo):
    vf01 = relatorio_exemplo.vagas_estruturadas[0]
    texto = avaliar_vaga(vf01, mapa_habilidades(cv_f01)).justificativa
    assert texto.startswith("Atende a 3 de 4 requisitos obrigatórios e a 2 de 3 desejáveis.")
    assert "Power BI (pede intermediário, tem básico)" in texto
    assert "Apache Airflow (desejável)" in texto
    com_filtro = justificar([], ["nível pleno incompatível com o pretendido (junior)"])
    assert "Fora dos filtros do perfil: nível pleno" in com_filtro


def test_rotulo_distingue_requisitos_do_mesmo_item():
    vaga = Vaga(id_vaga="x", titulo="t", empresa="e", cidade="c", regime="remoto", nivel="junior", descricao="d",
                requisitos=[_req("Windows", descricao="Windows e Linux"), _req("Linux", descricao="Windows e Linux")])
    aval = avaliar_vaga(vaga, {}).para_contrato()
    assert aval.requisitos_faltantes == ["Windows (Windows e Linux)", "Linux (Windows e Linux)"]
