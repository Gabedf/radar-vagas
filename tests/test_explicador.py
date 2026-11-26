"""Ferramentas do agente "Explicador do radar": só leem o resultado já calculado."""

import pytest
from agno.db.sqlite import SqliteDb

from radar_vagas.documentos import salvar_resultado
from radar_vagas.explicador import ID_EXPLICADOR, RegistroResultados, criar_explicador, criar_ferramentas
from radar_vagas.extrator_regras import ExtratorRegras
from radar_vagas.workflow import executar_workflow

from conftest import ModeloRoteirizado, cv_de, perfil_de


@pytest.fixture(scope="module")
def resultado_f01():
    from carreira_contratos import ConjuntoVagas, carregar
    from conftest import INSUMOS
    conjunto = carregar(INSUMOS / "conjunto_vagas.json", ConjuntoVagas)
    return executar_workflow(cv_de("f01"), conjunto, perfil_de("f01"), extrator=ExtratorRegras())


@pytest.fixture
def ferramentas(resultado_f01, tmp_path):
    """Ferramentas lendo uma pasta de saídas gravada como a da linha de comando."""
    salvar_resultado(resultado_f01, tmp_path / "f01")
    return {f.__name__: f for f in criar_ferramentas(RegistroResultados(tmp_path))}


def test_listar_e_resumo(ferramentas):
    assert "f01" in ferramentas["listar_formandos"]()
    texto = ferramentas["resumo"]("f01")
    assert "Vaga recomendada: vf01" in texto and "30 vagas analisadas, 7 elegíveis" in texto
    assert "v04 nota 100 (fora dos filtros)" in texto


def test_ver_avaliacao_mostra_a_conta(ferramentas, resultado_f01):
    texto = ferramentas["ver_avaliacao"]("f01", "vf01")
    assert "Nota: 82" in texto and "Elegível: sim" in texto
    assert "Power BI intermediário" in texto and "parcial" in texto
    assert "arred(100 × 9 / 11)" in texto  # a mesma conta de docs/MOTOR_DE_REGRAS.md
    v04 = ferramentas["ver_avaliacao"]("f01", "v04")
    assert "Elegível: NÃO" in v04 and "Nota: 100" in v04


def test_comparar_vagas_cita_as_duas_notas(ferramentas, resultado_f01):
    notas = {a.id_vaga: a.nota for a in resultado_f01.avaliacoes}
    texto = ferramentas["comparar_vagas"]("f01", "v25", "vf01")
    assert f"Nota: {notas['vf01']}" in texto and f"Nota: {notas['v25']}" in texto
    assert texto.startswith("Ranking: vf01 na posição 2, v25 na posição 3")
    assert "tem nota maior (82 contra 80)" in texto
    fora = ferramentas["comparar_vagas"]("f01", "v04", "vf01")
    assert "v04 está fora dos filtros" in fora


def test_ver_lacunas_e_regras(ferramentas):
    lacunas = ferramentas["ver_lacunas"]("f01")
    assert lacunas.splitlines()[1].startswith("- Power BI: prioridade alta; tem básico, precisa intermediário")
    regras = ferramentas["explicar_regras"]()
    assert "peso 2 para obrigatório e 1 para desejável" in regras and "determinístico" in regras


def test_ids_inexistentes_viram_mensagem(ferramentas):
    assert ferramentas["resumo"]("f99").startswith("Erro: não há resultado")
    assert ferramentas["ver_avaliacao"]("f01", "v99").startswith("Erro: a vaga 'v99'")


def test_memoria_tem_preferencia_sobre_a_pasta(resultado_f01, tmp_path):
    registro = RegistroResultados(tmp_path)  # pasta vazia
    assert registro.ids() == [] and registro.obter("f01") is None
    registro.registrar(resultado_f01)
    assert registro.ids() == ["f01"] and registro.obter("f01") is resultado_f01


def test_saidas_do_repositorio_tem_o_rastro():
    """As saídas versionadas (saidas/f01..f03) servem de fonte para o explicador."""
    registro = RegistroResultados("saidas")
    if not registro.ids():
        pytest.skip("rode `radar-vagas executar` para gerar saidas/fXX/rastro_calculo.json")
    assert registro.obter("f01").relatorio.id_vaga_recomendada == "vf01"


def test_agente_usa_as_ferramentas(tmp_path):
    agente = criar_explicador(ModeloRoteirizado(respostas=["ok"]), SqliteDb(db_file=str(tmp_path / "t.db")),
                              RegistroResultados(tmp_path))
    assert agente.id == ID_EXPLICADOR
    nomes = {getattr(t, "__name__", getattr(t, "name", "")) for t in agente.tools}
    assert {"resumo", "ver_avaliacao", "comparar_vagas", "ver_lacunas", "explicar_regras", "listar_formandos"} <= nomes
    assert agente.run("Oi").content == "ok"
