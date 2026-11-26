"""Testes da normalização de habilidades e níveis (F3)."""

import pytest

from radar_vagas.normalizacao import (
    canonizar, detectar_nivel, dicionario_padrao, encontrar_habilidades, grupos_alternativos, normalizar_texto,
)


@pytest.mark.parametrize("nome,canonico", [
    ("PostgreSQL", "SQL"), ("SQL Server", "SQL"), ("bancos de dados relacionais", "SQL"), ("consultas SQL", "SQL"),
    ("Redes", "Redes de computadores"), ("redes TCP/IP", "Redes de computadores"),
    ("power-bi", "Power BI"), ("AIRFLOW", "Apache Airflow"), ("Scripts em Shell", "Shell script"),
    ("ingles", "Inglês"), ("Comunicacao", "Comunicação"), ("pytest", "Testes automatizados"),
])
def test_canonizar_aliases(nome, canonico):
    assert canonizar(nome) == (canonico, True)


def test_nomes_dos_curriculos_sao_canonicos():
    """Os nomes usados nos 3 currículos do kit são canônicos (mapeiam para si mesmos)."""
    for nome in ["SQL", "Python", "pandas", "Estatística", "Power BI", "Git", "Comunicação", "Inglês", "Django",
                 "Java", "Docker", "Trabalho em equipe", "Linux", "Redes de computadores", "Shell script",
                 "Atendimento ao usuário"]:
        assert canonizar(nome) == (nome, True)


def test_nome_desconhecido_nao_mapeado():
    nome, mapeado = canonizar("cobol avançado")
    assert not mapeado and nome == "Cobol avançado"


def test_normalizar_texto_acentos_e_simbolos():
    assert normalizar_texto("Estatística Descritiva!") == "estatistica descritiva"
    assert normalizar_texto("Node.js, C# e C++.") == "node.js c# e c++"
    assert normalizar_texto("Spark.") == "spark"
    assert normalizar_texto("CI/CD") == "ci/cd"


@pytest.mark.parametrize("trecho,nivel", [
    ("Noções de SQL", "basico"), ("Python básico", "basico"), ("Windows e Linux básicos", "basico"),
    ("Excel intermediário", "intermediario"), ("HTML, CSS e JavaScript intermediários", "intermediario"),
    ("Python avançado", "avancado"), ("Experiência sólida em machine learning", "avancado"),
    ("Estatística avançada", "avancado"), ("Git", None), ("Conhecimentos de estatística descritiva", None),
])
def test_detectar_nivel(trecho, nivel):
    assert detectar_nivel(trecho) == nivel


def test_python_avancado():
    (oc,) = encontrar_habilidades("Python avançado")
    assert oc.canonico == "Python" and detectar_nivel("Python avançado") == "avancado"


def test_alias_mais_longo_vence_e_consome():
    ocs = encontrar_habilidades("PostgreSQL ou SQL Server")
    assert [o.canonico for o in ocs] == ["SQL", "SQL"]  # "SQL Server" não casa também como "SQL"
    assert [o.trecho for o in ocs] == ["PostgreSQL", "SQL Server"]


def test_bordas_de_palavra():
    assert [o.canonico for o in encontrar_habilidades("JavaScript")] == ["JavaScript"]  # não casa "Java"
    assert encontrar_habilidades("Levantamento de requisitos")[0].canonico == "Levantamento de requisitos"
    assert all(o.canonico != "R" for o in encontrar_habilidades("Requisitos e regras"))


@pytest.mark.parametrize("texto,grupos", [
    ("Python ou Java", [["Python", "Java"]]),
    ("experiência com serviços de nuvem (AWS, Azure ou GCP)", [["AWS", "Azure", "GCP"]]),
    ("HTML, CSS e JavaScript", [["HTML"], ["CSS"], ["JavaScript"]]),
    ("Python com Django ou Node.js", [["Python"], ["Django", "Node.js"]]),
    ("Docker e Kubernetes", [["Docker"], ["Kubernetes"]]),
])
def test_grupos_alternativos(texto, grupos):
    assert grupos_alternativos(texto) == grupos


def test_dicionario_tem_versao():
    assert len(dicionario_padrao().versao) == 8
