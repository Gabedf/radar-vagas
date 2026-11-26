"""Testes do extrator por regras (F2) e do cache."""

import json

from carreira_contratos import VagaAlvo, carregar

from radar_vagas.cache import ExtratorComCache, chave_vaga
from radar_vagas.extrator_regras import ExtratorRegras, dividir_itens, dividir_secoes, motivo_ignorar

from conftest import EXEMPLOS


def _por_habilidade(requisitos):
    return {r.habilidade: r for r in requisitos}


def test_todas_as_30_vagas_tem_requisitos(conjunto_30):
    extrator = ExtratorRegras()
    vazias = [v.id_vaga for v in conjunto_30.vagas if not extrator.extrair(v)]
    assert vazias == []


def test_v01(conjunto_30):
    v01 = next(v for v in conjunto_30.vagas if v.id_vaga == "v01")
    det = ExtratorRegras().analisar(v01)
    reqs = _por_habilidade(det.requisitos)
    assert set(reqs) == {"Excel", "SQL", "Power BI", "Python"}
    assert (reqs["Excel"].obrigatorio, reqs["Excel"].nivel_minimo) == (True, "intermediario")
    assert (reqs["SQL"].obrigatorio, reqs["SQL"].nivel_minimo, reqs["SQL"].descricao) == (True, "basico", "Noções de SQL")
    assert reqs["Power BI"].obrigatorio is False
    assert (reqs["Python"].obrigatorio, reqs["Python"].nivel_minimo) == (False, "basico")
    # A formação ("Cursando ..., Estatística ou áreas afins") não vira requisito.
    assert det.ignorados and det.ignorados[0][1] == "formação"
    assert "Estatística" not in reqs


def test_vf01_reproduz_os_requisitos_do_exemplo(conjunto_30, relatorio_exemplo):
    """As descrições extraídas de vf01 são exatamente as do gabarito do kit."""
    vf01 = next(v for v in conjunto_30.vagas if v.id_vaga == "vf01")
    extraidos = ExtratorRegras().extrair(vf01)
    gabarito = relatorio_exemplo.vagas_estruturadas[0].requisitos
    assert [(r.descricao, r.habilidade, r.obrigatorio) for r in extraidos] == \
           [(r.descricao, r.habilidade, r.obrigatorio) for r in gabarito]


def test_inline_desejavel_e_anos_de_experiencia(conjunto_30):
    v03 = next(v for v in conjunto_30.vagas if v.id_vaga == "v03")
    det = ExtratorRegras().analisar(v03)
    reqs = _por_habilidade(det.requisitos)
    assert reqs["Spark"].obrigatorio is False  # "Spark (desejável)"
    assert reqs["Machine Learning"].nivel_minimo == "avancado"  # "Experiência sólida em ..."
    assert any(m == "tempo de experiência" for _, m in det.ignorados)


def test_alternativas_viram_um_requisito(conjunto_30):
    por_id = {v.id_vaga: v for v in conjunto_30.vagas}
    v05 = _por_habilidade(ExtratorRegras().extrair(por_id["v05"]))
    assert "AWS" in v05 and "Azure" not in v05 and "GCP" not in v05  # "(AWS, Azure ou GCP)"
    v04 = ExtratorRegras().extrair(por_id["v04"])
    assert [r.habilidade for r in v04].count("SQL") == 1  # "PostgreSQL ou SQL Server"


def test_dividir_secoes_e_itens():
    secoes = dividir_secoes("Intro. Requisitos: A; B. Diferenciais: C, D. Benefícios: E.")
    assert [s.tipo for s in secoes] == ["obrigatorio", "desejavel", "beneficios"]
    assert dividir_itens("Power BI avançado, incluindo DAX, SQL intermediário.") == \
           ["Power BI avançado", "incluindo DAX", "SQL intermediário"]
    assert dividir_itens("nuvem (AWS, Azure ou GCP), Docker.") == ["nuvem (AWS, Azure ou GCP)", "Docker"]


def test_motivo_ignorar():
    assert motivo_ignorar("Cursando Ciência da Computação") == "formação"
    assert motivo_ignorar("Experiência de seis anos") == "tempo de experiência"
    assert motivo_ignorar("Experiência sólida em machine learning") is None


def _precisao_revocacao(extraidos, referencia):
    e, r = {x.habilidade for x in extraidos}, {x.habilidade for x in referencia}
    acertos = len(e & r)
    return acertos / len(e), acertos / len(r)


def test_comparacao_com_vaga_alvo_de_referencia(conjunto_30):
    """vf02 e vf03 têm requisitos estruturados no kit (vaga_alvo.json): mede precisão e revocação."""
    por_id = {v.id_vaga: v for v in conjunto_30.vagas}
    for idf in ("f02", "f03"):
        ref = carregar(EXEMPLOS / idf / "vaga_alvo.json", VagaAlvo).vaga
        extraidos = ExtratorRegras().extrair(por_id[ref.id_vaga])
        precisao, revocacao = _precisao_revocacao(extraidos, ref.requisitos)
        print(f"{ref.id_vaga}: precisão {precisao:.2f}, revocação {revocacao:.2f}")
        assert precisao >= 0.9 and revocacao >= 0.9
        # Obrigatoriedade e nível também batem com a referência.
        por_hab = _por_habilidade(extraidos)
        for r in ref.requisitos:
            assert por_hab[r.habilidade].obrigatorio == r.obrigatorio, r.habilidade
            assert (por_hab[r.habilidade].nivel_minimo or "basico") == (r.nivel_minimo or "basico"), r.habilidade


class _ExtratorContador:
    origem, versao = "teste", "1"

    def __init__(self):
        self.chamadas = 0

    def extrair(self, vaga):
        self.chamadas += 1
        return ExtratorRegras().extrair(vaga)


def test_cache_reaproveita_e_invalida_por_versao(tmp_path, conjunto_30):
    vaga = conjunto_30.vagas[0]
    caminho = tmp_path / "cache.json"
    base = _ExtratorContador()
    c1 = ExtratorComCache(base, caminho)
    primeiro = c1.extrair(vaga)
    assert base.chamadas == 1 and caminho.exists()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados[chave_vaga(vaga)]["teste"]["versao"] == "1"
    # Nova instância lê do arquivo, sem chamar o extrator.
    c2 = ExtratorComCache(base, caminho)
    assert c2.extrair(vaga) == primeiro and base.chamadas == 1 and c2.acertos == 1
    # Versão diferente -> extrai de novo.
    ExtratorComCache(base, caminho, versao="2").extrair(vaga)
    assert base.chamadas == 2
    # Descrição diferente -> chave diferente.
    assert chave_vaga(vaga) != chave_vaga(vaga.model_copy(update={"descricao": vaga.descricao + " "}))
