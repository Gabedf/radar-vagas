"""Motor de regras — cálculo da aderência entre currículo e vaga (F4).

Todo o cálculo é CÓDIGO DETERMINÍSTICO: a mesma entrada dá sempre a mesma
nota, e cada número pode ser explicado passo a passo. O modelo de linguagem
não participa daqui (no máximo, ele extrai os requisitos antes).

R1. Mapa de habilidades do formando
    {nome canônico: (nível, nome original)} montado a partir de
    `curriculo.habilidades` e `curriculo.idiomas` (idioma "fluente" conta
    como "avancado"). Os nomes passam pelo MESMO dicionário usado nas vagas.
    As `tecnologias` de experiências e projetos NÃO contam: elas não têm
    nível, e o verificador do kit só considera habilidades e idiomas.

R2. Classificação de cada requisito
    nível pedido = nivel_minimo do requisito, ou "basico" se a vaga não disse.
    - o formando não tem a habilidade         -> faltante, crédito 0,0
    - nível do formando >= nível pedido        -> atendido, crédito 1,0
    - nível do formando <  nível pedido        -> parcial,  crédito 0,5
    Alternativas: se o texto do requisito oferece opções ("Python ou Java"),
    vale a MELHOR opção que o formando tiver.

R3. Nota de 0 a 100
    peso 2 para obrigatório, peso 1 para desejável;
    nota = arred( 100 * Σ(peso * crédito) / Σ(peso) ),
    com arred(x) = piso(x + 0,5) (meio para cima; o round() do Python
    arredonda 42,5 para 42, "para o par", e não queremos isso).
    Esta fórmula reproduz as notas do exemplo do kit: 82, 43 e 43.

R4. Justificativa
    Texto montado por MODELO (template) em código, só com os números
    calculados — não há como "alucinar" um motivo.
"""

from __future__ import annotations

import math
from typing import NamedTuple, Optional

from carreira_contratos import Curriculo, Requisito, Vaga

from .modelos import AvaliacaoInterna, Classificacao
from .normalizacao import NIVEIS, Dicionario, dicionario_padrao, nivel_idioma

# ----------------------------------------------------------- constantes (R2, R3)

PESO_OBRIGATORIO = 2  # um obrigatório vale o dobro de um desejável
PESO_DESEJAVEL = 1
CREDITO = {"atendido": 1.0, "parcial": 0.5, "faltante": 0.0}
NIVEL_PADRAO = "basico"  # nível pedido quando a vaga não indica nenhum

NOME_NIVEL = {"nenhum": "nenhum", "basico": "básico", "intermediario": "intermediário", "avancado": "avançado"}


# ----------------------------------------------------------------------- R1

class HabilidadeFormando(NamedTuple):
    canonico: str  # nome canônico (o mesmo usado nas vagas)
    nivel: str  # basico | intermediario | avancado
    nome_original: str  # como está escrito no currículo (usado nas lacunas)


Mapa = dict[str, HabilidadeFormando]  # chave: nome canônico em minúsculas


def mapa_habilidades(cv: Curriculo, dicionario: Dicionario | None = None) -> Mapa:
    """R1: o que o formando TEM, com nível, indexado pelo nome canônico.

    Se duas entradas do currículo levam ao mesmo canônico (ex.: "SQL" e
    "PostgreSQL"), fica a de MAIOR nível.
    """
    dic = dicionario or dicionario_padrao()
    entradas = [(h.nome, h.nivel) for h in cv.habilidades]
    entradas += [(i.idioma, nivel_idioma(i.nivel)) for i in cv.idiomas]
    mapa: Mapa = {}
    for nome, nivel in entradas:
        canonico, _ = dic.canonizar(nome)
        chave = canonico.casefold()
        atual = mapa.get(chave)
        if atual is None or NIVEIS[nivel] > NIVEIS[atual.nivel]:
            mapa[chave] = HabilidadeFormando(canonico, nivel, nome)
    return mapa


# ----------------------------------------------------------------------- R2

def alternativas(requisito: Requisito, dicionario: Dicionario | None = None) -> list[str]:
    """Habilidades que satisfazem o requisito: a própria e as alternativas do texto.

    Ex.: descricao "Python ou R para análise de dados", habilidade "Python"
    -> ["Python", "R"]. Sem "ou" no texto -> só a própria habilidade.
    """
    dic = dicionario or dicionario_padrao()
    canonico, _ = dic.canonizar(requisito.habilidade)
    for grupo in dic.grupos_alternativos(requisito.descricao):
        if canonico in grupo:
            return [canonico] + [h for h in grupo if h != canonico]
    return [canonico]


def classificar(requisito: Requisito, mapa: Mapa, rotulo: Optional[str] = None,
                dicionario: Dicionario | None = None) -> Classificacao:
    """R2: atendido (1,0), parcial (0,5) ou faltante (0,0)."""
    pedido = requisito.nivel_minimo or NIVEL_PADRAO
    peso = PESO_OBRIGATORIO if requisito.obrigatorio else PESO_DESEJAVEL
    candidatas = alternativas(requisito, dicionario)

    # Procura, entre as alternativas que o formando tem, a de MAIOR nível.
    melhor: Optional[HabilidadeFormando] = None
    for nome in candidatas:
        h = mapa.get(nome.casefold())
        if h and (melhor is None or NIVEIS[h.nivel] > NIVEIS[melhor.nivel]):
            melhor = h

    if melhor is None:
        status, habilidade, atual = "faltante", candidatas[0], "nenhum"
    elif NIVEIS[melhor.nivel] >= NIVEIS[pedido]:
        status, habilidade, atual = "atendido", melhor.canonico, melhor.nivel
    else:
        status, habilidade, atual = "parcial", melhor.canonico, melhor.nivel

    return Classificacao(
        requisito=requisito,
        rotulo=rotulo or requisito.descricao,
        habilidade=habilidade,
        nivel_pedido=pedido,
        nivel_atual=atual,
        status=status,
        credito=CREDITO[status],
        peso=peso,
    )


# ----------------------------------------------------------------------- R3

def arredondar(x: float) -> int:
    """Arredondamento "meio para cima": 42,5 -> 43 (o round() daria 42)."""
    return math.floor(x + 0.5)


def calcular_nota(classificacoes: list[Classificacao]) -> int:
    """R3: nota = arred(100 * Σ(peso*crédito) / Σ peso). Sem requisitos -> 0."""
    soma_pesos = sum(c.peso for c in classificacoes)
    if soma_pesos == 0:
        return 0
    pontos = sum(c.peso * c.credito for c in classificacoes)
    return arredondar(100 * pontos / soma_pesos)


# ----------------------------------------------------------------------- R4

def _lista(itens: list[str]) -> str:
    return "; ".join(itens)


def justificar(classificacoes: list[Classificacao], motivos_filtro: list[str] | None = None) -> str:
    """R4: justificativa por template, só com fatos calculados.

    Ex.: "Atende a 3 de 4 requisitos obrigatórios e a 2 de 3 desejáveis.
    Parcial: Power BI (pede intermediário, tem básico). Falta: Apache Airflow
    (desejável)."
    """
    obr = [c for c in classificacoes if c.requisito.obrigatorio]
    des = [c for c in classificacoes if not c.requisito.obrigatorio]
    obr_ok = sum(c.status == "atendido" for c in obr)
    des_ok = sum(c.status == "atendido" for c in des)

    partes = []
    if des:
        partes.append(f"Atende a {obr_ok} de {len(obr)} requisitos obrigatórios e a {des_ok} de {len(des)} desejáveis.")
    else:
        partes.append(f"Atende a {obr_ok} de {len(obr)} requisitos obrigatórios (a vaga não lista desejáveis).")

    parciais = [
        f"{c.habilidade} (pede {NOME_NIVEL[c.nivel_pedido]}, tem {NOME_NIVEL[c.nivel_atual]})"
        for c in classificacoes if c.status == "parcial"
    ]
    if parciais:
        partes.append(f"Parcial: {_lista(parciais)}.")

    faltas = [
        f"{c.habilidade} ({'obrigatório' if c.requisito.obrigatorio else 'desejável'})"
        for c in classificacoes if c.status == "faltante"
    ]
    if faltas:
        partes.append(f"Falta: {_lista(faltas)}.")
    if not parciais and not faltas:
        partes.append("Nenhuma lacuna nesta vaga.")

    if motivos_filtro:
        partes.append(f"Fora dos filtros do perfil: {_lista(motivos_filtro)}; por isso não pode ser recomendada.")
    return " ".join(partes)


# ------------------------------------------------------------ avaliação completa

def rotulos(requisitos: list[Requisito]) -> list[str]:
    """Texto de cada requisito nas listas atendidos/parciais/faltantes.

    Normalmente é a própria `descricao`. Quando um item da vaga gerou mais de
    um requisito ("Windows e Linux"), a descrição se repetiria; nesse caso o
    rótulo vira "Windows (Windows e Linux)" para as listas não ficarem ambíguas.
    """
    contagem: dict[str, int] = {}
    for r in requisitos:
        contagem[r.descricao] = contagem.get(r.descricao, 0) + 1
    return [r.descricao if contagem[r.descricao] == 1 else f"{r.habilidade} ({r.descricao})" for r in requisitos]


def avaliar_vaga(vaga: Vaga, mapa: Mapa, motivos_filtro: list[str] | None = None,
                 dicionario: Dicionario | None = None) -> AvaliacaoInterna:
    """Aplica R2, R3 e R4 a todos os requisitos de uma vaga."""
    classificacoes = [
        classificar(r, mapa, rotulo, dicionario)
        for r, rotulo in zip(vaga.requisitos, rotulos(vaga.requisitos))
    ]
    obr = [c for c in classificacoes if c.requisito.obrigatorio]
    des = [c for c in classificacoes if not c.requisito.obrigatorio]
    motivos = list(motivos_filtro or [])
    return AvaliacaoInterna(
        id_vaga=vaga.id_vaga,
        nota=calcular_nota(classificacoes),
        classificacoes=classificacoes,
        elegivel=not motivos,
        motivos_filtro=motivos,
        obrigatorios_total=len(obr),
        obrigatorios_atendidos=sum(c.status == "atendido" for c in obr),
        desejaveis_total=len(des),
        desejaveis_atendidos=sum(c.status == "atendido" for c in des),
        justificativa=justificar(classificacoes, motivos),
    )
