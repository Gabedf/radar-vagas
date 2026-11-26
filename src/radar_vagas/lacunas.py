"""R8 — Consolidação das lacunas (F7).

Uma lacuna é uma habilidade em que o formando está ABAIXO do nível pedido
(requisito parcial ou faltante) em pelo menos uma vaga considerada.

Vagas consideradas: as ELEGÍVEIS (que passam nos filtros do perfil); se
nenhuma for elegível, todas as vagas. Assim a lista de estudos fala das
vagas que o formando realmente quer.

Para cada habilidade com lacuna:
    vagas_relacionadas = vagas consideradas em que ela é lacuna (ordenadas)
    frequencia         = quantas são essas vagas
    obrigatoria        = é obrigatória em pelo menos uma delas
    nivel_necessario   = o MAIOR nível pedido entre elas
    nivel_atual        = o nível no currículo, ou "nenhum"
    habilidade         = o nome ORIGINAL do currículo, quando o formando tem a
                         habilidade (o verificador compara por esse nome);
                         senão, o nome canônico.

Prioridade:
    alta  = obrigatória na vaga recomendada, OU obrigatória em muitas vagas
            (lacuna OBRIGATÓRIA frequente);
    media = obrigatória em alguma vaga, OU lacuna frequente (contando também
            as vagas em que é só desejável);
    baixa = o resto.
    "frequente" = em pelo menos LIMIAR_FREQUENCIA (30%) das vagas
    consideradas E em pelo menos MIN_VAGAS_FREQUENTE (2) vagas — uma vaga
    isolada não caracteriza tendência do mercado.

Ordem: alta, media, baixa; dentro da mesma prioridade, primeiro as lacunas
obrigatórias da vaga recomendada (o que estudar para ela), depois maior
frequência, depois nome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from carreira_contratos import Curriculo, Lacuna

from .modelos import AvaliacaoInterna
from .motor import Mapa
from .normalizacao import NIVEIS, nivel_idioma

LIMIAR_FREQUENCIA = 0.3
MIN_VAGAS_FREQUENTE = 2
ORDEM_PRIORIDADE = {"alta": 0, "media": 1, "baixa": 2}


@dataclass
class _Acumulador:
    """O que já sabemos sobre uma habilidade enquanto percorremos as vagas."""

    canonico: str
    vagas: set[str] = field(default_factory=set)
    vagas_obrigatoria: set[str] = field(default_factory=set)  # vagas em que é lacuna OBRIGATÓRIA
    obrigatoria_na_recomendada: bool = False
    nivel_necessario: str = "basico"

    @property
    def obrigatoria(self) -> bool:
        return bool(self.vagas_obrigatoria)


def e_frequente(frequencia: int, total_vagas: int) -> bool:
    return frequencia >= MIN_VAGAS_FREQUENTE and frequencia >= LIMIAR_FREQUENCIA * total_vagas


def prioridade(acc: _Acumulador, total_vagas: int) -> str:
    if acc.obrigatoria_na_recomendada or e_frequente(len(acc.vagas_obrigatoria), total_vagas):
        return "alta"
    if acc.obrigatoria or e_frequente(len(acc.vagas), total_vagas):
        return "media"
    return "baixa"


def consolidar_lacunas(avaliacoes: list[AvaliacaoInterna], mapa: Mapa, id_recomendada: str) -> list[Lacuna]:
    """R8: junta as lacunas das vagas consideradas numa lista priorizada."""
    consideradas = [a for a in avaliacoes if a.elegivel] or list(avaliacoes)
    acumulado: dict[str, _Acumulador] = {}
    for aval in consideradas:
        for c in aval.classificacoes:
            if c.status == "atendido":
                continue
            acc = acumulado.setdefault(c.habilidade.casefold(), _Acumulador(c.habilidade))
            acc.vagas.add(aval.id_vaga)
            if c.requisito.obrigatorio:
                acc.vagas_obrigatoria.add(aval.id_vaga)
                if aval.id_vaga == id_recomendada:
                    acc.obrigatoria_na_recomendada = True
            if NIVEIS[c.nivel_pedido] > NIVEIS[acc.nivel_necessario]:
                acc.nivel_necessario = c.nivel_pedido

    itens = []
    na_recomendada = set()  # nomes das lacunas obrigatórias da vaga recomendada (para a ordem)
    for chave, acc in acumulado.items():
        tem = mapa.get(chave)
        nome = tem.nome_original if tem else acc.canonico
        if acc.obrigatoria_na_recomendada:
            na_recomendada.add(nome)
        itens.append(Lacuna(
            habilidade=nome,
            nivel_atual=tem.nivel if tem else "nenhum",
            nivel_necessario=acc.nivel_necessario,
            prioridade=prioridade(acc, len(consideradas)),
            obrigatoria=acc.obrigatoria,
            frequencia=len(acc.vagas),
            vagas_relacionadas=sorted(acc.vagas),
        ))
    itens.sort(key=lambda l: (ORDEM_PRIORIDADE[l.prioridade], l.habilidade not in na_recomendada,
                              -l.frequencia, l.habilidade.casefold()))
    return itens


class ErroInvariante(AssertionError):
    """Uma lacuna contradiz o currículo (seria reprovada pelo verificador)."""


def checar_invariantes(itens: list[Lacuna], cv: Curriculo) -> None:
    """Garante, antes de gravar, as mesmas regras que o verificador do kit confere.

    1. nivel_atual é exatamente o nível do currículo (comparando o nome sem
       diferenciar maiúsculas), ou "nenhum";
    2. nenhuma lacuna tem nível atual >= nível necessário.
    """
    niveis = {h.nome.casefold(): h.nivel for h in cv.habilidades}
    niveis |= {i.idioma.casefold(): nivel_idioma(i.nivel) for i in cv.idiomas}
    for l in itens:
        atual = niveis.get(l.habilidade.casefold(), "nenhum")
        if l.nivel_atual != atual:
            raise ErroInvariante(f"lacuna {l.habilidade}: nivel_atual {l.nivel_atual}, mas o currículo indica {atual}")
        if atual != "nenhum" and NIVEIS[atual] >= NIVEIS[l.nivel_necessario]:
            raise ErroInvariante(f"{l.habilidade} não é lacuna: o currículo já tem o nível {atual}")
