"""Extrator LLM (F2, modo "llm") com um modelo roteirizado: sem rede, sem chave."""

import json

import pytest

from radar_vagas.cli import main
from radar_vagas.config import ErroConfiguracao, carregar_configuracao
from radar_vagas.extrator_llm import ExtratorLLM, criar_extrator_llm
from radar_vagas.extrator_regras import ExtratorRegras

from conftest import EXEMPLOS, INSUMOS, ModeloRoteirizado, resposta_extrator

# Requisitos corretos da vf01 (mesmos trechos do texto da vaga).
VALIDOS = [
    ("SQL intermediário", "PostgreSQL", None, True),
    ("Python básico para tratamento de dados", "Python", "avancado", True),  # nível errado do modelo
    ("Git", "Git", None, True),  # está em "Desejável:", o modelo errou o tipo
    ("noções de Apache Airflow", "Airflow", None, False),
]


@pytest.fixture
def vf01(conjunto_exemplo):
    return conjunto_exemplo.vagas[0]


def extrator(*respostas):
    modelo = ModeloRoteirizado(respostas=list(respostas))
    return ExtratorLLM(modelo), modelo


def test_guardas_mantem_validos_e_corrigem_o_modelo(vf01):
    ext, modelo = extrator(resposta_extrator(*VALIDOS))
    reqs = {r.habilidade: r for r in ext.extrair(vf01)}
    assert modelo.chamadas == 1 and not ext.usou_reserva
    assert set(reqs) == {"SQL", "Python", "Git", "Apache Airflow"}  # nomes canônicos do dicionário
    assert reqs["SQL"].nivel_minimo == "intermediario" and reqs["SQL"].descricao == "SQL intermediário"
    assert reqs["Python"].nivel_minimo == "basico"  # vale o nível escrito no trecho
    assert reqs["Git"].obrigatorio is False  # seção "Desejável:" rebaixa
    assert reqs["Apache Airflow"].nivel_minimo == "basico"  # "noções"


def test_trecho_inventado_e_formacao_sao_descartados(vf01):
    ext, _ = extrator(resposta_extrator(
        *VALIDOS,
        ("Kubernetes avançado", "Kubernetes", "avancado", True),  # não existe na vaga
        ("SQL avançado e Spark", "Spark", None, True),  # trecho reescrito
    ))
    habilidades = {r.habilidade for r in ext.extrair(vf01)}
    assert "Kubernetes" not in habilidades and "Spark" not in habilidades
    assert len(habilidades) == 4


def test_nao_confunde_pedaco_de_palavra(conjunto_exemplo):
    vaga = conjunto_exemplo.vagas[0].model_copy(update={"descricao": "Requisitos: marketing digital; SQL."})
    ext, _ = extrator(resposta_extrator(("Git", "Git", None, True), ("SQL", "SQL", None, True)))
    assert [r.habilidade for r in ext.extrair(vaga)] == ["SQL"]  # "git" de "digital" não conta


def test_resposta_vazia_tenta_de_novo_com_os_problemas(vf01):
    ext, modelo = extrator(resposta_extrator(("Docker", "Docker", None, True)), resposta_extrator(*VALIDOS))
    assert len(ext.extrair(vf01)) == 4
    assert modelo.chamadas == 2 and not ext.usou_reserva


def test_resposta_fora_do_formato_tenta_de_novo(vf01):
    ext, modelo = extrator("isto não é JSON", resposta_extrator(*VALIDOS))
    assert len(ext.extrair(vf01)) == 4 and modelo.chamadas == 2


def test_sem_resposta_valida_usa_as_regras(vf01):
    ext, modelo = extrator(resposta_extrator(), resposta_extrator(("Docker", "Docker", None, True)))
    assert ext.extrair(vf01) == ExtratorRegras().extrair(vf01)
    assert modelo.chamadas == 2 and ext.usou_reserva and ext.vagas_na_reserva == ["vf01"]


def test_cache_guarda_llm_mas_nao_a_reserva(vf01, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_REQUISITOS", str(tmp_path / "cache.json"))
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    cfg = carregar_configuracao()
    modelo = ModeloRoteirizado(respostas=[resposta_extrator(*VALIDOS)])
    ext = criar_extrator_llm(cfg, modelo=modelo)
    assert ext.origem == "llm" and ext.versao.startswith("llm-prompt-")
    primeira = ext.extrair(vf01)
    assert ext.extrair(vf01) == primeira and modelo.chamadas == 1  # 2ª vez: veio do cache
    entrada = next(iter(json.loads((tmp_path / "cache.json").read_text(encoding="utf-8")).values()))
    assert set(entrada) == {"llm"}

    reserva = criar_extrator_llm(cfg, modelo=ModeloRoteirizado())  # sem respostas: cai nas regras
    outra = vf01.model_copy(update={"id_vaga": "vf99"})
    reserva.extrair(outra)
    assert "vf99" not in (tmp_path / "cache.json").read_text(encoding="utf-8")


def test_criar_sem_modelo_e_erro_de_configuracao(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELO_LLM", "")
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    with pytest.raises(ErroConfiguracao, match="MODELO_LLM"):
        criar_extrator_llm(carregar_configuracao())


def test_cli_extrator_llm_com_modelo_de_teste(tmp_path, monkeypatch):
    """--extrator llm de ponta a ponta. O modelo não responde nada válido, então todas as
    vagas caem nas regras: o resultado precisa sair igual (e o comando não quebra)."""
    import radar_vagas.extrator_llm as mod

    monkeypatch.setenv("CACHE_REQUISITOS", str(tmp_path / "cache.json"))
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    original = mod.criar_extrator_llm
    monkeypatch.setattr(mod, "criar_extrator_llm", lambda cfg: original(cfg, modelo=ModeloRoteirizado()))
    args = ["executar", "--curriculo", str(EXEMPLOS / "f01" / "curriculo.json"),
            "--vagas", str(INSUMOS / "conjunto_vagas.json"), "--perfil", str(EXEMPLOS / "f01" / "perfil_carreira.json")]
    assert main(args + ["--extrator", "llm", "--saida-dir", str(tmp_path / "llm")]) == 0
    assert main(args + ["--saida-dir", str(tmp_path / "regras")]) == 0
    llm = json.loads((tmp_path / "llm" / "relatorio_aderencia.json").read_text(encoding="utf-8"))
    regras = json.loads((tmp_path / "regras" / "relatorio_aderencia.json").read_text(encoding="utf-8"))
    assert llm["avaliacoes"] == regras["avaliacoes"]


def test_modelo_indisponivel_usa_regras_sem_insistir(conjunto_exemplo):
    """Sem chave, o Agno devolve o erro como conteúdo (status error): o extrator cai nas regras
    e não chama o modelo de novo nas vagas seguintes."""

    class ModeloSemChave(ModeloRoteirizado):
        def invoke(self, *args, **kwargs):
            self.chamadas += 1
            raise RuntimeError("GROQ_API_KEY not set")

    modelo = ModeloSemChave()
    ext = ExtratorLLM(modelo)
    ext.agente.retries = 0  # no uso real o Agno tenta 3 vezes, com espera; aqui não precisa esperar
    for vaga in conjunto_exemplo.vagas:
        assert ext.extrair(vaga) == ExtratorRegras().extrair(vaga)
    assert ext.modelo_indisponivel and ext.vagas_na_reserva == ["vf01", "vx01", "vx02"]
    assert modelo.chamadas == 1  # só a primeira vaga tentou o modelo


def test_sem_chave_do_provedor_e_erro_de_configuracao(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELO_LLM", "groq:openai/gpt-oss-120b")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("BANCO_SQLITE", str(tmp_path / "radar.db"))
    with pytest.raises(ErroConfiguracao, match="GROQ_API_KEY"):
        criar_extrator_llm(carregar_configuracao())
