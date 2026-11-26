"""Filtros, ranking, recomendação e competências mais pedidas (F5, F6, F8).

R5. Filtros de elegibilidade
    - regime: o da vaga precisa estar entre os preferidos;
    - cidade: comparada sem acento, sem maiúsculas e sem o sufixo de estado
      ("Vitória - ES" == "vitória"); vaga REMOTA dispensa o filtro de cidade;
    - nível: compatível pela tabela COMPATIBILIDADE_NIVEL
      (quem pretende "junior" aceita vagas junior e trainee).
    Filtro vazio não restringe. A fonte é o PerfilCarreira; opções da linha de
    comando substituem o filtro correspondente. Vaga fora dos filtros continua
    avaliada (tem nota), mas não pode ser recomendada.

R6. Ranking e recomendação
    Ordem: maior nota; empate -> maior fração de obrigatórios atendidos;
    empate -> id_vaga (ordem alfabética, para o resultado ser estável).
    Recomendada = a 1ª vaga ELEGÍVEL do ranking. Se nenhuma for elegível,
    recomenda a 1ª do ranking geral e avisa isso na justificativa.

R7. Competências mais pedidas
    Para cada habilidade canônica, conta em quantas vagas do conjunto ela
    aparece (obrigatória ou desejável). Devolve as TOP_COMPETENCIAS mais
    frequentes; empate -> ordem alfabética.
"""

from __future__ import annotations

import re
from typing import Optional

from carreira_contratos import PerfilCarreira, Vaga

from .modelos import AvaliacaoInterna, Filtros, Ranking
from .normalizacao import normalizar_texto

# Nível pretendido pelo formando -> níveis de vaga que ele aceita.
COMPATIBILIDADE_NIVEL: dict[str, set[str]] = {
    "estagio": {"estagio"},
    "trainee": {"trainee", "junior"},
    "junior": {"junior", "trainee"},
}
REMOTO_DISPENSA_CIDADE = True  # numa vaga remota, a cidade da empresa não importa
TOP_COMPETENCIAS = 10


# ----------------------------------------------------------------------- R5

def normalizar_cidade(cidade: str) -> str:
    """'Vitória - ES' -> 'vitoria'; 'Vila Velha/ES' -> 'vila velha'."""
    sem_uf = re.sub(r"\s*[-–—/,]\s*[A-Za-z]{2}\s*$", "", cidade.strip())
    return normalizar_texto(sem_uf)


def filtros_do_perfil(perfil: Optional[PerfilCarreira]) -> Filtros:
    if perfil is None:
        return Filtros()
    return Filtros(
        regimes=list(perfil.preferencias_regime),
        cidades=list(perfil.preferencias_cidades),
        niveis=[perfil.nivel_pretendido],
    )


def combinar_filtros(base: Filtros, sobrepor: Optional[Filtros]) -> Filtros:
    """Cada lista NÃO vazia de `sobrepor` (linha de comando) substitui a da base (perfil)."""
    if sobrepor is None:
        return base
    return Filtros(
        regimes=sobrepor.regimes or base.regimes,
        cidades=sobrepor.cidades or base.cidades,
        niveis=sobrepor.niveis or base.niveis,
    )


def niveis_aceitos(filtros: Filtros) -> set[str]:
    aceitos: set[str] = set()
    for n in filtros.niveis:
        aceitos |= COMPATIBILIDADE_NIVEL.get(n, {n})  # nível fora da tabela aceita só ele mesmo
    return aceitos


def motivos_exclusao(vaga: Vaga, filtros: Filtros) -> list[str]:
    """Lista os filtros em que a vaga NÃO passa (lista vazia = vaga elegível)."""
    motivos = []
    if filtros.regimes and vaga.regime not in filtros.regimes:
        motivos.append(f"regime {vaga.regime} fora das preferências ({', '.join(filtros.regimes)})")
    if filtros.cidades and not (REMOTO_DISPENSA_CIDADE and vaga.regime == "remoto"):
        if normalizar_cidade(vaga.cidade) not in {normalizar_cidade(c) for c in filtros.cidades}:
            motivos.append(f"cidade {vaga.cidade} fora das preferências ({', '.join(filtros.cidades)})")
    if filtros.niveis and vaga.nivel not in niveis_aceitos(filtros):
        motivos.append(f"nível {vaga.nivel} incompatível com o pretendido ({', '.join(filtros.niveis)})")
    return motivos


# ----------------------------------------------------------------------- R6

def chave_ranking(a: AvaliacaoInterna) -> tuple:
    return (-a.nota, -a.fracao_obrigatorios, a.id_vaga)


def ordenar(avaliacoes: list[AvaliacaoInterna]) -> list[AvaliacaoInterna]:
    return sorted(avaliacoes, key=chave_ranking)


def _descrever_filtros(filtros: Filtros) -> str:
    partes = []
    if filtros.regimes:
        partes.append("regime " + ", ".join(filtros.regimes))
    if filtros.cidades:
        partes.append("cidades " + ", ".join(filtros.cidades))
    if filtros.niveis:
        partes.append("nível " + ", ".join(sorted(niveis_aceitos(filtros))))
    return "; ".join(partes) or "sem filtros"


def recomendar(ordenadas: list[AvaliacaoInterna], vagas: dict[str, Vaga], filtros: Filtros) -> tuple[str, str]:
    """Escolhe a vaga recomendada e monta a justificativa da recomendação."""
    elegiveis = [a for a in ordenadas if a.elegivel]
    if elegiveis:
        escolhida = elegiveis[0]
        abertura = (
            f"{escolhida.id_vaga} tem a maior nota ({escolhida.nota}) entre as {len(elegiveis)} vagas "
            f"elegíveis pelos filtros ({_descrever_filtros(filtros)})."
        )
    else:
        escolhida = ordenadas[0]
        abertura = (
            f"Atenção: nenhuma vaga passa nos filtros ({_descrever_filtros(filtros)}); "
            f"{escolhida.id_vaga} foi indicada por ter a maior nota geral ({escolhida.nota})."
        )
    vaga = vagas[escolhida.id_vaga]
    pendencias = [c.habilidade for c in escolhida.classificacoes if c.status != "atendido" and c.requisito.obrigatorio]
    detalhe = f" Vaga: {vaga.titulo} ({vaga.empresa}, {vaga.cidade}, {vaga.regime}, {vaga.nivel})."
    detalhe += f" Atende a {escolhida.obrigatorios_atendidos} de {escolhida.obrigatorios_total} obrigatórios"
    detalhe += f" e a {escolhida.desejaveis_atendidos} de {escolhida.desejaveis_total} desejáveis."
    if pendencias:
        detalhe += f" Obrigatórios a desenvolver: {', '.join(pendencias)}."
    else:
        detalhe += " Todos os obrigatórios estão atendidos."
    return escolhida.id_vaga, abertura + detalhe


# ----------------------------------------------------------------------- R7

def contar_competencias(vagas: list[Vaga]) -> dict[str, int]:
    """Em quantas vagas cada habilidade aparece (cada vaga conta uma vez)."""
    contagem: dict[str, int] = {}
    for v in vagas:
        for h in {r.habilidade for r in v.requisitos}:
            contagem[h] = contagem.get(h, 0) + 1
    return contagem


def competencias_mais_pedidas(vagas: list[Vaga], n: int = TOP_COMPETENCIAS) -> list[str]:
    contagem = contar_competencias(vagas)
    return [h for h, _ in sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0].casefold()))[:n]]


# ------------------------------------------------------------------- tudo junto

def ranquear(avaliacoes: list[AvaliacaoInterna], vagas: list[Vaga], filtros: Filtros) -> Ranking:
    """R6 + R7 sobre avaliações já calculadas (a elegibilidade de R5 já vem nelas)."""
    ordenadas = ordenar(avaliacoes)
    id_rec, justificativa = recomendar(ordenadas, {v.id_vaga: v for v in vagas}, filtros)
    return Ranking(
        avaliacoes=ordenadas,
        id_vaga_recomendada=id_rec,
        justificativa_recomendacao=justificativa,
        elegiveis=[a.id_vaga for a in ordenadas if a.elegivel],
        competencias_mais_pedidas=competencias_mais_pedidas(vagas),
        contagem_competencias=contar_competencias(vagas),
    )
