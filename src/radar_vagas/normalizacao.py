"""F3 — Normalização de habilidades e de níveis.

Problema: a mesma habilidade aparece escrita de vários jeitos ("PostgreSQL",
"consultas SQL", "bancos de dados relacionais"...), e o currículo usa um nome
só ("SQL"). Para comparar vaga e currículo, os dois lados passam pelo MESMO
dicionário (dados/dicionario_habilidades.yaml), que leva cada forma ao seu
nome canônico.

Peças deste arquivo:
- `normalizar_texto`: minúsculas, sem acento, sem pontuação (mantém + # . /
  dentro das palavras, para "c++", "c#", "node.js" e "ci/cd").
- `detectar_nivel`: lê o nível pedido num trecho ("noções de" -> basico).
- `Dicionario.canonizar`: nome solto -> (nome canônico, estava no dicionário?).
- `Dicionario.encontrar`: acha todas as habilidades num texto livre, com
  índice de aliases do MAIS LONGO para o mais curto e máscara de "consumido"
  (assim "SQL Server" casa uma vez só, e não também como "SQL").
- `Dicionario.grupos_alternativos`: descobre listas de alternativas
  ("Python ou Java", "AWS, Azure ou GCP") — usadas pelo extrator e pelo motor.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

CAMINHO_DICIONARIO = Path(__file__).parent / "dados" / "dicionario_habilidades.yaml"

# Escala ordinal dos níveis. É a mesma do verificador do kit.
NIVEIS: dict[str, int] = {"basico": 1, "intermediario": 2, "avancado": 3}

# Caracteres que fazem parte de uma "palavra" de habilidade.
_CHARS_PALAVRA = "a-z0-9+#"


# ------------------------------------------------------------------ texto

def _sem_acento(c: str) -> str:
    """Tira o acento de UM caractere, devolvendo sempre UM caractere."""
    return unicodedata.normalize("NFD", c)[0]


def dobrar(texto: str) -> str:
    """Minúsculas e sem acento, PRESERVANDO o comprimento do texto.

    Como cada caractere vira exatamente um caractere, uma posição encontrada
    no texto dobrado vale também no texto original. Isso permite buscar sem
    acento e recortar o trecho original (com acento) para a saída.
    """
    return "".join(_sem_acento(c.lower()[0]) for c in texto)


def normalizar_texto(texto: str) -> str:
    """Forma canônica de comparação: 'Power-BI Avançado!' -> 'power bi avancado'.

    - casefold e remoção de acentos;
    - o ponto só fica quando está entre letras/números ("node.js"); no fim de
      frase ("Spark.") ele vira separador;
    - mantém + # / (c++, c#, ci/cd, tcp/ip); o resto da pontuação vira espaço.
    """
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    t = re.sub(r"(?<![a-z0-9])\.|\.(?![a-z0-9])", " ", t)
    t = re.sub(r"(?<![a-z0-9])/|/(?![a-z0-9])", " ", t)
    t = re.sub(rf"[^{_CHARS_PALAVRA}./]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------------ níveis

# Palavras que indicam o nível pedido, já sem acento. A ordem importa:
# se um trecho citar mais de um nível, vale o MAIS ALTO.
_PADROES_NIVEL: list[tuple[str, re.Pattern]] = [
    ("avancado", re.compile(r"\b(avancad[oa]s?|solid[oa]s?|dominio|fluente|fluencia|profund[oa]s?)\b")),
    ("intermediario", re.compile(r"\bintermediari[oa]s?\b")),
    ("basico", re.compile(r"\b(basic[oa]s?|nocoes|nocao|fundamentos|introdutori[oa]s?|iniciante)\b")),
]


def detectar_nivel(trecho: str) -> Optional[str]:
    """'Noções de SQL' -> 'basico'; 'Excel intermediário' -> 'intermediario';
    'Experiência sólida em ML' -> 'avancado'; sem indicação -> None.

    None significa "a vaga não disse"; o motor trata None como 'basico' (R2).
    """
    t = dobrar(trecho)
    for nivel, padrao in _PADROES_NIVEL:
        if padrao.search(t):
            return nivel
    return None


def nivel_idioma(nivel: str) -> str:
    """Idiomas têm o nível extra 'fluente', que conta como 'avancado' (igual ao verificador)."""
    return "avancado" if nivel == "fluente" else nivel


def maior_nivel(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """O maior de dois níveis; None é tratado como 'abaixo de basico'."""
    if a is None:
        return b
    if b is None:
        return a
    return a if NIVEIS[a] >= NIVEIS[b] else b


# ------------------------------------------------------------- dicionário

@dataclass(frozen=True)
class Ocorrencia:
    """Uma habilidade encontrada num texto: nome canônico e posição."""

    canonico: str
    inicio: int
    fim: int
    trecho: str  # texto original (com acento) que casou


class Dicionario:
    """Dicionário de habilidades: nome canônico <- aliases."""

    def __init__(self, entradas: dict[str, dict], versao: str = "memoria"):
        self.versao = versao  # muda quando o arquivo do dicionário muda (invalida o cache)
        self.categorias: dict[str, str] = {}
        self._indice: dict[str, str] = {}  # forma normalizada -> nome canônico
        for canonico, info in entradas.items():
            info = info or {}
            self.categorias[canonico] = info.get("categoria", "tecnica")
            for forma in [canonico, *(info.get("aliases") or [])]:
                chave = normalizar_texto(str(forma))
                if chave:
                    self._indice.setdefault(chave, canonico)  # primeiro registro vence
        # Padrões de busca do MAIS LONGO para o mais curto: "sql server" antes de "sql".
        self._padroes = [
            (self._compilar(chave), canonico)
            for chave, canonico in sorted(self._indice.items(), key=lambda kv: (-len(kv[0]), kv[0]))
        ]

    @staticmethod
    def _compilar(chave: str) -> re.Pattern:
        # Entre as palavras do alias aceitamos espaço, hífen ou sublinhado
        # ("power-bi" casa com "power bi"). As bordas impedem casar pedaços de
        # palavra: "r" não casa dentro de "requisitos", "java" não casa em "javascript".
        corpo = r"[\s\-_]+".join(re.escape(p) for p in chave.split(" "))
        return re.compile(rf"(?<![{_CHARS_PALAVRA}]){corpo}(?![{_CHARS_PALAVRA}$]|\.[a-z0-9])")

    @classmethod
    def carregar(cls, caminho: Path = CAMINHO_DICIONARIO) -> "Dicionario":
        dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8")) or {}
        return cls(dados, versao=hashlib.sha256(Path(caminho).read_bytes()).hexdigest()[:8])

    @property
    def nomes(self) -> list[str]:
        return list(self.categorias)

    def canonizar(self, nome: str) -> tuple[str, bool]:
        """Nome solto -> (nome canônico, mapeado).

        'PostgreSQL' -> ('SQL', True); 'Redes' -> ('Redes de computadores', True).
        Nome fora do dicionário: devolve uma forma limpa do próprio nome e
        mapeado=False, para o pipeline reportar como "não mapeada".
        """
        chave = normalizar_texto(nome)
        if chave in self._indice:
            return self._indice[chave], True
        # Tentativa extra: o nome contém exatamente uma habilidade conhecida
        # e nada mais relevante (ex.: "conhecimento em Docker" -> Docker).
        achadas = {o.canonico for o in self.encontrar(nome)}
        if len(achadas) == 1 and detectar_nivel(nome) is None and len(chave.split()) <= 4:
            return achadas.pop(), True
        limpo = re.sub(r"\s+", " ", nome).strip(" .,;:-")
        if limpo and limpo == limpo.lower():
            limpo = limpo[0].upper() + limpo[1:]
        return limpo or nome, False

    def encontrar(self, texto: str) -> list[Ocorrencia]:
        """Todas as habilidades citadas em `texto`, em ordem de posição.

        Varre os aliases do mais longo para o mais curto e marca o trecho
        casado como "consumido": um alias menor não pode casar dentro dele.
        """
        dobrado = dobrar(texto)
        consumido = bytearray(len(dobrado))
        achadas: list[Ocorrencia] = []
        for padrao, canonico in self._padroes:
            for m in padrao.finditer(dobrado):
                ini, fim = m.span()
                if any(consumido[ini:fim]):
                    continue
                consumido[ini:fim] = b"\x01" * (fim - ini)
                achadas.append(Ocorrencia(canonico, ini, fim, texto[ini:fim]))
        return sorted(achadas, key=lambda o: o.inicio)

    def grupos_alternativos(self, texto: str) -> list[list[str]]:
        """Agrupa as habilidades do texto em listas de ALTERNATIVAS.

        Duas habilidades vizinhas são alternativas quando, entre elas, só há
        a palavra "ou" ("Python ou Java", "React ou Vue"). Vírgulas também
        ligam, mas só quando a enumeração termina num "ou"
        ("AWS, Azure ou GCP"); em "HTML, CSS e JavaScript" cada uma é exigida.
        Parênteses quebram a ligação: em "Python (pytest)" o pytest é detalhe.

        Devolve uma lista de grupos, cada um com nomes canônicos sem repetição:
        "Python com Django ou Node.js" -> [["Python"], ["Django", "Node.js"]].
        """
        ocs = self.encontrar(texto)
        if not ocs:
            return []
        dobrado = dobrar(texto)
        ligacoes: list[Optional[str]] = []
        for a, b in zip(ocs, ocs[1:]):
            vao = dobrado[a.fim:b.inicio]
            palavras = re.findall(r"[a-z0-9]+", vao)
            if palavras == ["ou"]:
                ligacoes.append("ou")
            elif not palavras and set(vao) <= set(" ,/"):
                ligacoes.append("virgula")  # provisória: só vale se a lista terminar em "ou"
            else:
                ligacoes.append(None)
        # Confirma as vírgulas provisórias que desembocam num "ou".
        for i, lig in enumerate(ligacoes):
            if lig == "virgula":
                j = i
                while j < len(ligacoes) and ligacoes[j] == "virgula":
                    j += 1
                ligacoes[i] = "ou" if j < len(ligacoes) and ligacoes[j] == "ou" else None
        grupos: list[list[str]] = [[ocs[0].canonico]]
        for lig, oc in zip(ligacoes, ocs[1:]):
            if lig == "ou":
                if oc.canonico not in grupos[-1]:
                    grupos[-1].append(oc.canonico)
            else:
                grupos.append([oc.canonico])
        return grupos


@lru_cache(maxsize=1)
def dicionario_padrao() -> Dicionario:
    """Dicionário carregado uma vez por processo."""
    return Dicionario.carregar()


# Atalhos com o dicionário padrão -------------------------------------------

def canonizar(nome: str) -> tuple[str, bool]:
    return dicionario_padrao().canonizar(nome)


def encontrar_habilidades(texto: str) -> list[Ocorrencia]:
    return dicionario_padrao().encontrar(texto)


def grupos_alternativos(texto: str) -> list[list[str]]:
    return dicionario_padrao().grupos_alternativos(texto)


def chave(nome: str) -> str:
    """Chave de comparação de um nome canônico (sem acento/maiúsculas)."""
    return normalizar_texto(nome)
