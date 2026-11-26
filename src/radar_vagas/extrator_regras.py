"""F2 — Extração de requisitos por REGRAS (modo "regras", sem LLM).

As 30 vagas do kit chegam com `requisitos: []`; os requisitos estão escritos
dentro da `descricao`. Este extrator determinístico funciona assim:

1. Seções: a descrição é cortada nos marcadores conhecidos.
   - obrigatórios: "Requisitos:", "Precisamos que você tenha:", "O que buscamos:"...
   - desejáveis:   "Diferenciais:", "Será um diferencial:", "Desejável:"...
   - fim da seção: "Benefícios:", "Oferecemos:", "Atividades:", "Você vai:"...
2. Itens: cada seção é quebrada em frases (". ") e depois em itens por ";"
   (ou por "," quando a frase não tem ";"), sem quebrar dentro de parênteses.
3. Filtro: itens de formação ("Cursando ...") e de tempo de experiência
   ("três anos") NÃO viram requisito — ficam registrados como ignorados.
4. Habilidades: cada item é varrido pelo dicionário (normalizacao.py). Cada
   GRUPO de alternativas ("Python ou Java") vira UM requisito, com a primeira
   alternativa como `habilidade`; habilidades ligadas por "e" ou vírgula viram
   requisitos separados. "(desejável)" no item torna-o desejável.
5. Nível: `detectar_nivel(item)` ("noções" -> basico, "avançado" -> avancado).
6. Deduplicação: uma habilidade aparece uma vez por vaga; se repetida,
   prevalece o obrigatório e, depois, o maior nível.

Sem nenhum marcador de seção, a descrição inteira é varrida como obrigatória.

Qualquer extrator (este ou o LLM) segue o protocolo `Extrator`: recebe uma
`Vaga` e devolve `list[Requisito]` do contrato.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from carreira_contratos import Requisito, Vaga

from .normalizacao import Dicionario, detectar_nivel, dicionario_padrao, dobrar, maior_nivel

# Versão das regras de extração. Mude quando alterar a lógica deste arquivo:
# ela entra na chave de versão do cache (junto com a versão do dicionário).
VERSAO_REGRAS = "1"


class Extrator(Protocol):
    """Interface comum dos extratores (regras e LLM)."""

    def extrair(self, vaga: Vaga) -> list[Requisito]: ...


# ------------------------------------------------------------------ seções

# Marcadores, já sem acento e em minúsculas, seguidos de ":" no texto.
MARCADORES: dict[str, list[str]] = {
    "obrigatorio": [
        "requisitos obrigatorios", "requisitos", "pre-requisitos", "precisamos que voce tenha",
        "o que buscamos", "o que esperamos de voce", "o que esperamos", "exigimos", "exigencias",
        "qualificacoes", "voce precisa ter", "e necessario", "necessario",
    ],
    "desejavel": [
        "requisitos desejaveis", "sera um diferencial", "serao diferenciais", "diferenciais",
        "diferencial", "desejaveis", "desejavel", "nice to have", "seria otimo se voce tivesse",
    ],
    "atividades": [
        "atividades", "responsabilidades", "voce vai", "principais atividades", "o que voce vai fazer",
    ],
    "beneficios": ["beneficios", "oferecemos", "o que oferecemos"],
    "outro": ["sobre a empresa", "sobre a vaga", "local de trabalho", "salario", "remuneracao", "horario"],
}

_TIPO_POR_MARCADOR = {m: tipo for tipo, ms in MARCADORES.items() for m in ms}
_RE_MARCADOR = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(re.escape(m) for m in sorted(_TIPO_POR_MARCADOR, key=len, reverse=True))
    + r")\s*:"
)


@dataclass
class Secao:
    tipo: str  # obrigatorio | desejavel | atividades | beneficios | outro
    texto: str  # texto original (com acentos) da seção, sem o marcador


def dividir_secoes(descricao: str) -> list[Secao]:
    """Corta a descrição nos marcadores. O texto antes do 1º marcador é descartado."""
    dobrado = dobrar(descricao)
    marcas = list(_RE_MARCADOR.finditer(dobrado))
    secoes = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(descricao)
        secoes.append(Secao(_TIPO_POR_MARCADOR[m.group(1)], descricao[m.end():fim].strip()))
    return secoes


def _dividir_fora_de_parenteses(texto: str, separador: str) -> list[str]:
    """split() que ignora separadores dentro de parênteses: "nuvem (AWS, Azure)"."""
    partes, atual, profundidade = [], [], 0
    for c in texto:
        if c == "(":
            profundidade += 1
        elif c == ")":
            profundidade = max(0, profundidade - 1)
        if c == separador and profundidade == 0:
            partes.append("".join(atual))
            atual = []
        else:
            atual.append(c)
    partes.append("".join(atual))
    return partes


def dividir_itens(texto_secao: str) -> list[str]:
    """Quebra uma seção em itens: frases por '. ', depois ';' (ou ',' se não houver ';')."""
    itens = []
    # Ponto seguido de espaço termina frase; "Node.js" não é afetado.
    for frase in re.split(r"\.\s+", texto_secao.strip()):
        frase = frase.strip().rstrip(".").strip()
        if not frase:
            continue
        sep = ";" if ";" in frase else ","
        for parte in _dividir_fora_de_parenteses(frase, sep):
            parte = parte.strip().rstrip(".").strip()
            if parte:
                itens.append(parte)
    return itens


# ------------------------------------------------------- filtros de itens

_RE_DESEJAVEL_INLINE = re.compile(r"\(\s*(desejavel|desejaveis|diferencial|opcional)\s*\)")
_RE_FORMACAO = re.compile(
    r"^(cursando|graduad|graduacao|formad|formacao|bacharel|tecnolog|ensino (medio|superior|tecnico)|estudante)"
    r"|\b(graduacao|bacharelado|curso superior|ensino superior|curso tecnico) (em|completo|completa|cursando)\b"
)
_RE_ANOS = re.compile(r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+anos?\b")
_RE_CERTIFICACAO = re.compile(r"^(certificacao|certificado)")


def motivo_ignorar(item: str) -> Optional[str]:
    """Diz por que um item não vira requisito (ou None se ele deve ser analisado)."""
    t = dobrar(item)
    if _RE_FORMACAO.search(t):
        return "formação"
    if _RE_ANOS.search(t):
        return "tempo de experiência"
    if _RE_CERTIFICACAO.search(t):
        return "certificação"
    return None


def _limpar_descricao(item: str) -> str:
    """Tira o "(desejável)" e põe a 1ª letra maiúscula: 'noções de X' -> 'Noções de X'."""
    dobrado = dobrar(item)
    m = _RE_DESEJAVEL_INLINE.search(dobrado)
    if m:
        item = item[: m.start()] + item[m.end():]
    item = re.sub(r"\s+", " ", item).strip(" .;,")
    return item[:1].upper() + item[1:]


# ------------------------------------------------------------------ extrator

@dataclass
class ExtracaoDetalhada:
    """Requisitos + diagnóstico (o que foi ignorado e o que ficou sem habilidade)."""

    requisitos: list[Requisito] = field(default_factory=list)
    ignorados: list[tuple[str, str]] = field(default_factory=list)  # (item, motivo)
    sem_habilidade: list[str] = field(default_factory=list)  # itens sem habilidade conhecida


def deduplicar(requisitos: list[Requisito]) -> list[Requisito]:
    """Uma habilidade por vaga: obrigatório vence desejável; depois, o maior nível vence.

    A ordem de primeira aparição é preservada.
    """
    escolhidos: dict[str, Requisito] = {}
    for r in requisitos:
        chave = r.habilidade.casefold()
        atual = escolhidos.get(chave)
        if atual is None:
            escolhidos[chave] = r
            continue
        if r.obrigatorio and not atual.obrigatorio:
            escolhidos[chave] = r
        elif r.obrigatorio == atual.obrigatorio and maior_nivel(atual.nivel_minimo, r.nivel_minimo) != atual.nivel_minimo:
            escolhidos[chave] = r
    return list(escolhidos.values())


class ExtratorRegras:
    """Extrator determinístico baseado em seções, itens e dicionário."""

    origem = "regras"

    def __init__(self, dicionario: Dicionario | None = None):
        self.dicionario = dicionario or dicionario_padrao()

    @property
    def versao(self) -> str:
        return f"regras-{VERSAO_REGRAS}-dic-{self.dicionario.versao}"

    def extrair(self, vaga: Vaga) -> list[Requisito]:
        return self.analisar(vaga).requisitos

    def analisar(self, vaga: Vaga) -> ExtracaoDetalhada:
        resultado = ExtracaoDetalhada()
        secoes = [s for s in dividir_secoes(vaga.descricao) if s.tipo in ("obrigatorio", "desejavel")]
        if not secoes:
            # Sem marcadores: a descrição inteira é tratada como lista de obrigatórios.
            secoes = [Secao("obrigatorio", vaga.descricao)]
        brutos: list[Requisito] = []
        for secao in secoes:
            for item in dividir_itens(secao.texto):
                brutos.extend(self._requisitos_do_item(item, secao.tipo == "obrigatorio", resultado))
        resultado.requisitos = deduplicar(brutos)
        return resultado

    def _requisitos_do_item(self, item: str, obrigatorio_secao: bool, diag: ExtracaoDetalhada) -> list[Requisito]:
        motivo = motivo_ignorar(item)
        if motivo:
            diag.ignorados.append((item, motivo))
            return []
        obrigatorio = obrigatorio_secao and not _RE_DESEJAVEL_INLINE.search(dobrar(item))
        descricao = _limpar_descricao(item)
        grupos = self.dicionario.grupos_alternativos(descricao)
        if not grupos:
            diag.sem_habilidade.append(descricao)
            return []
        nivel = detectar_nivel(descricao)
        # Um requisito por GRUPO de alternativas; a 1ª alternativa dá o nome.
        # As demais continuam no texto da descrição, e o motor as reconhece (R2).
        return [
            Requisito(descricao=descricao, habilidade=grupo[0], nivel_minimo=nivel, obrigatorio=obrigatorio)
            for grupo in grupos
        ]


__all__ = [
    "Extrator", "ExtratorRegras", "ExtracaoDetalhada", "Secao", "VERSAO_REGRAS",
    "dividir_secoes", "dividir_itens", "deduplicar", "motivo_ignorar",
]
