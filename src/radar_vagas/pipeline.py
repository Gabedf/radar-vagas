"""Pipeline do radar de vagas: as cinco etapas, em ordem, como funções simples.

    1. extração     — requisitos de cada vaga (extrator de regras, LLM ou cache)
    2. normalização — nomes canônicos, nível conferido no texto, sem repetições
    3. comparação   — filtros (R5) + motor de regras (R1–R4) para cada vaga
    4. ranqueamento — ordem, recomendação e competências mais pedidas (R6–R7)
    5. consolidação — lacunas (R8), documentos do contrato e relatório Markdown

Cada etapa recebe e devolve dados explícitos (sem estado escondido), então
pode ser testada sozinha e embrulhada, uma a uma, como passo de um Workflow
do Agno. `executar_radar` só encadeia as cinco.
"""

from __future__ import annotations

import os
from typing import Optional

from carreira_contratos import ConjuntoVagas, Curriculo, PerfilCarreira, Requisito, Vaga

from .cache import CAMINHO_PADRAO, ExtratorComCache
from .documentos import montar_lacunas, montar_relatorio
from .extrator_regras import Extrator, ExtratorRegras, deduplicar
from .lacunas import checar_invariantes, consolidar_lacunas
from .modelos import AvaliacaoInterna, Filtros, Ranking, ResultadoRadar
from .motor import avaliar_vaga, mapa_habilidades
from .normalizacao import Dicionario, detectar_nivel, dicionario_padrao
from .ranking import combinar_filtros, filtros_do_perfil, motivos_exclusao, ranquear
from .relatorio_md import gerar_markdown


def extrator_padrao() -> Extrator:
    """Extrator por regras com cache em dados/cache_requisitos.json (ou CACHE_REQUISITOS)."""
    return ExtratorComCache(ExtratorRegras(), os.getenv("CACHE_REQUISITOS", str(CAMINHO_PADRAO)))


def criar_extrator(tipo: str, cfg) -> Extrator:
    """'regras' (padrão, sem LLM) ou 'llm' (agente Agno), sempre com cache.

    O extrator LLM é importado só aqui: o modo 'regras' não depende de modelo.
    `cfg` é a `config.Configuracao`.
    """
    if tipo == "regras":
        return ExtratorComCache(ExtratorRegras(), cfg.cache_requisitos)
    if tipo == "llm":
        from .extrator_llm import criar_extrator_llm
        return criar_extrator_llm(cfg)
    raise ValueError(f"extrator desconhecido: {tipo!r} (use 'regras' ou 'llm')")


# ------------------------------------------------------------------ etapa 1

def etapa_extracao(conjunto: ConjuntoVagas, extrator: Extrator) -> list[Vaga]:
    """Devolve as vagas com `requisitos` preenchidos.

    Se a vaga JÁ trouxer requisitos na entrada, eles são mantidos (o contrato
    diz que o radar preenche a lista quando ela vem vazia).
    """
    vagas = []
    for vaga in conjunto.vagas:
        requisitos = vaga.requisitos or extrator.extrair(vaga)
        vagas.append(vaga.model_copy(update={"requisitos": list(requisitos)}))
    return vagas


# ------------------------------------------------------------------ etapa 2

def normalizar_requisitos(requisitos: list[Requisito], dicionario: Dicionario) -> tuple[list[Requisito], list[str]]:
    """Canoniza os nomes, completa o nível pelo texto e remove repetições.

    É também a "rede de segurança" do extrator LLM: o nome que o modelo
    devolver passa pelo dicionário, e o nível é conferido no próprio texto.
    """
    nao_mapeadas = []
    saida = []
    for r in requisitos:
        canonico, mapeado = dicionario.canonizar(r.habilidade)
        if not mapeado:
            nao_mapeadas.append(canonico)
        nivel = r.nivel_minimo or detectar_nivel(r.descricao)
        saida.append(r.model_copy(update={"habilidade": canonico, "nivel_minimo": nivel}))
    return deduplicar(saida), nao_mapeadas


def etapa_normalizacao(vagas: list[Vaga], dicionario: Dicionario | None = None) -> tuple[list[Vaga], list[str], list[str]]:
    """Devolve (vagas normalizadas, habilidades não mapeadas, avisos)."""
    dic = dicionario or dicionario_padrao()
    normalizadas, nao_mapeadas, avisos = [], [], []
    for vaga in vagas:
        requisitos, faltam = normalizar_requisitos(vaga.requisitos, dic)
        nao_mapeadas += [f"{n} (vaga {vaga.id_vaga})" for n in faltam]
        if not requisitos:
            avisos.append(f"vaga {vaga.id_vaga} ficou sem requisitos extraídos (o verificador reprova)")
        normalizadas.append(vaga.model_copy(update={"requisitos": requisitos}))
    return normalizadas, nao_mapeadas, avisos


# ------------------------------------------------------------------ etapa 3

def etapa_comparacao(cv: Curriculo, vagas: list[Vaga], filtros: Filtros,
                     dicionario: Dicionario | None = None) -> list[AvaliacaoInterna]:
    """R1 uma vez; depois R5 (filtros) e R2–R4 (motor) para cada vaga."""
    mapa = mapa_habilidades(cv, dicionario)
    return [avaliar_vaga(v, mapa, motivos_exclusao(v, filtros), dicionario) for v in vagas]


# ------------------------------------------------------------------ etapa 4

def etapa_ranqueamento(avaliacoes: list[AvaliacaoInterna], vagas: list[Vaga], filtros: Filtros) -> Ranking:
    return ranquear(avaliacoes, vagas, filtros)


# ------------------------------------------------------------------ etapa 5

def etapa_consolidacao(cv: Curriculo, vagas: list[Vaga], ranking: Ranking, filtros: Filtros,
                       nao_mapeadas: list[str] | None = None, avisos: list[str] | None = None,
                       origem_extracao: str = "regras", dicionario: Dicionario | None = None) -> ResultadoRadar:
    """R8 + documentos do contrato + Markdown."""
    mapa = mapa_habilidades(cv, dicionario)
    itens = consolidar_lacunas(ranking.avaliacoes, mapa, ranking.id_vaga_recomendada)
    checar_invariantes(itens, cv)  # falha aqui, e não no verificador, se algo estiver incoerente
    relatorio = montar_relatorio(cv, vagas, ranking)
    lacunas = montar_lacunas(cv, ranking.id_vaga_recomendada, itens)
    markdown = gerar_markdown(cv, vagas, ranking, lacunas, filtros, nao_mapeadas, avisos, origem_extracao)
    return ResultadoRadar(
        relatorio=relatorio,
        lacunas=lacunas,
        markdown=markdown,
        vagas_estruturadas=vagas,
        avaliacoes=ranking.avaliacoes,
        elegiveis=ranking.elegiveis,
        filtros=filtros,
        contagem_competencias=ranking.contagem_competencias,
        nao_mapeadas=list(nao_mapeadas or []),
        avisos=list(avisos or []),
        origem_extracao=origem_extracao,
    )


# ------------------------------------------------------------------ tudo junto

def executar_radar(curriculo: Curriculo, conjunto: ConjuntoVagas, perfil: Optional[PerfilCarreira] = None,
                   filtros: Optional[Filtros] = None, extrator: Optional[Extrator] = None) -> ResultadoRadar:
    """Executa as cinco etapas e devolve o resultado completo.

    - `perfil`: fonte dos filtros (regime, cidades, nível pretendido);
    - `filtros`: substituem, dimensão a dimensão, os do perfil (linha de comando);
    - `extrator`: qualquer objeto com `extrair(vaga) -> list[Requisito]`;
      padrão = regras + cache.
    """
    extrator = extrator or extrator_padrao()
    filtros_finais = combinar_filtros(filtros_do_perfil(perfil), filtros)
    dic = dicionario_padrao()

    vagas = etapa_extracao(conjunto, extrator)
    vagas, nao_mapeadas, avisos = etapa_normalizacao(vagas, dic)
    origem = getattr(extrator, "origem", "desconhecida")
    if origem == "regras":
        nao_mapeadas += itens_sem_habilidade(conjunto, dic)
    avaliacoes = etapa_comparacao(curriculo, vagas, filtros_finais, dic)
    ranking = etapa_ranqueamento(avaliacoes, vagas, filtros_finais)
    if not ranking.elegiveis:
        avisos.append("nenhuma vaga passa nos filtros; a recomendação e as lacunas usam todas as vagas")
    return etapa_consolidacao(curriculo, vagas, ranking, filtros_finais, nao_mapeadas, avisos, origem, dic)


def itens_sem_habilidade(conjunto: ConjuntoVagas, dicionario: Dicionario | None = None) -> list[str]:
    """Itens de requisito em que as regras não acharam habilidade do dicionário.

    Diagnóstico para melhorar o dicionário (ex.: "Disponibilidade para o turno da tarde").
    """
    extrator = ExtratorRegras(dicionario)
    return [
        f"item sem habilidade conhecida: {item} (vaga {v.id_vaga})"
        for v in conjunto.vagas if not v.requisitos
        for item in extrator.analisar(v).sem_habilidade
    ]
