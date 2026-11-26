"""Rotas do contrato e do AgentOS (TestClient, sem rede e sem chave de LLM)."""

import pytest
from fastapi.testclient import TestClient

from carreira_contratos import Lacunas, RelatorioAderencia
from carreira_contratos.verificar import verificar

from radar_vagas.cache import ExtratorComCache
from radar_vagas.config import carregar_configuracao
from radar_vagas.explicador import ID_EXPLICADOR, RegistroResultados
from radar_vagas.extrator_regras import ExtratorRegras
from radar_vagas.servidor import criar_agent_os

from conftest import ModeloRoteirizado


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    monkeypatch.setenv("CACHE_REQUISITOS", str(tmp_path / "cache.json"))
    monkeypatch.setenv("SAIDAS_DIR", str(tmp_path / "saidas"))
    monkeypatch.setenv("MODELO_LLM", "")
    monkeypatch.setenv("EXTRATOR", "regras")
    return carregar_configuracao()


def cliente(cfg, modelo=None, registro=None):
    extrator = ExtratorComCache(ExtratorRegras(), cfg.cache_requisitos)
    return TestClient(criar_agent_os(cfg, modelo=modelo, registro=registro, extrator=extrator).get_app())


def corpo(cv, conjunto, perfil=None):
    dados = {"curriculo": cv.model_dump(mode="json"), "conjunto_vagas": conjunto.model_dump(mode="json")}
    if perfil is not None:
        dados["perfil_carreira"] = perfil.model_dump(mode="json")
    return dados


def test_executar_f01_com_30_vagas(cfg, cv_f01, perfil_f01, conjunto_30):
    registro = RegistroResultados(cfg.saidas_dir)
    c = cliente(cfg, registro=registro)
    r = c.post("/contrato/executar", json=corpo(cv_f01, conjunto_30, perfil_f01))
    assert r.status_code == 200
    dados = r.json()
    assert set(dados) == {"relatorio_aderencia", "lacunas"}
    rel = RelatorioAderencia.model_validate(dados["relatorio_aderencia"])
    lac = Lacunas.model_validate(dados["lacunas"])
    assert rel.id_vaga_recomendada == "vf01" and len(rel.avaliacoes) == 30
    assert rel.cabecalho.modulo == "radar_vagas" and rel.cabecalho.id_formando == "f01"
    assert verificar("radar_vagas", {"Curriculo": cv_f01, "ConjuntoVagas": conjunto_30},
                     {"RelatorioAderencia": rel, "Lacunas": lac}).erros == []
    # o resultado fica disponível para o explicador e para o relatório em Markdown
    assert registro.obter("f01") is not None
    md = c.get("/relatorio/f01")
    assert md.status_code == 200 and "vf01" in md.text


def test_executar_sem_perfil(cfg, cv_f01, conjunto_exemplo):
    r = cliente(cfg).post("/contrato/executar", json=corpo(cv_f01, conjunto_exemplo))
    assert r.status_code == 200
    assert r.json()["relatorio_aderencia"]["id_vaga_recomendada"] == "vf01"


def test_corpo_invalido_da_422(cfg, cv_f01):
    c = cliente(cfg)
    assert c.post("/contrato/executar", json={"curriculo": {"cabecalho": {}}}).status_code == 422
    sem_vagas = {"curriculo": cv_f01.model_dump(mode="json"), "conjunto_vagas": {"vagas": []}}
    assert c.post("/contrato/executar", json=sem_vagas).status_code == 422


def test_relatorio_inexistente_da_404(cfg):
    assert cliente(cfg).get("/relatorio/f99").status_code == 404


def test_docs_e_config_sem_modelo(cfg):
    c = cliente(cfg)
    assert c.get("/docs").status_code == 200
    assert c.get("/config").status_code == 200
    assert c.get("/agents").json() == []  # sem MODELO_LLM o explicador não é registrado
    assert any(w["id"] == "radar-vagas-workflow" for w in c.get("/workflows").json())


def test_explicador_registrado_com_modelo(cfg):
    c = cliente(cfg, modelo=ModeloRoteirizado())
    agentes = c.get("/agents").json()
    assert any(a["id"] == ID_EXPLICADOR for a in agentes)


def test_conversa_pela_rota_do_agentos(cfg):
    c = cliente(cfg, modelo=ModeloRoteirizado(respostas=["A vaga recomendada é a vf01, com nota 82."]))
    r = c.post(f"/agents/{ID_EXPLICADOR}/runs", data={"message": "Qual a vaga recomendada?", "stream": "false"})
    assert r.status_code == 200 and "vf01" in r.json()["content"]
