"""F1 — Leitura das vagas (JSON do contrato ou arquivos de texto) e das demais entradas.

Formato dos arquivos de texto (vagas_texto/v01.txt ...):

    linha 1: título da vaga
    linha 2: Empresa — Cidade        (separados por travessão)
    linha 3: em branco
    resto:   descrição completa

O id da vaga é o nome do arquivo sem extensão ("v01"). Regime e nível NÃO
aparecem explicitamente no texto, então são deduzidos por palavras-chave
(heurística), com valores padrão configuráveis:
    nível:  "estágio", "trainee", "júnior", "pleno", "sênior" (título primeiro)
    regime: "híbrido", "remoto"/"home office", "presencial"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from carreira_contratos import ConjuntoVagas, Curriculo, PerfilCarreira, Vaga, carregar, novo_cabecalho

from .extrator_regras import dividir_itens, dividir_secoes
from .normalizacao import dobrar

MODULO = "radar_vagas"
NIVEL_PADRAO = "junior"
REGIME_PADRAO = "presencial"

# Palavras-chave (sem acento) -> nível da vaga. Procuradas primeiro no título.
_PALAVRAS_NIVEL = [
    ("estagio", r"\b(estagio|estagiari[oa])\b"),
    ("trainee", r"\btrainee\b"),
    ("senior", r"\b(senior|sr)\b"),
    ("pleno", r"\bpleno\b"),
    ("junior", r"\b(junior|jr)\b"),
]
# Ordem importa: "dois dias de trabalho remoto" é híbrido, não remoto.
_PALAVRAS_REGIME = [
    ("hibrido", r"\bhibrid[oa]\b|\bdias? (de trabalho )?remoto|remoto \w+ vezes"),
    ("remoto", r"\b(remot[oa]|home office|100% remoto|teletrabalho)\b"),
    ("presencial", r"\bpresencial\b"),
]


def deduzir_nivel(titulo: str, descricao: str, padrao: str = NIVEL_PADRAO) -> str:
    for texto in (titulo, descricao):
        t = dobrar(texto)
        for nivel, padrao_re in _PALAVRAS_NIVEL:
            if re.search(padrao_re, t):
                return nivel
    return padrao


def deduzir_regime(titulo: str, descricao: str, padrao: str = REGIME_PADRAO) -> str:
    t = dobrar(titulo + " " + descricao)
    for regime, padrao_re in _PALAVRAS_REGIME:
        if re.search(padrao_re, t):
            return regime
    return padrao


def secoes_listas(descricao: str) -> tuple[list[str], list[str]]:
    """Responsabilidades e benefícios lidos das seções da descrição."""
    resp, benef = [], []
    for s in dividir_secoes(descricao):
        if s.tipo == "atividades":
            resp += [i[:1].upper() + i[1:] for i in dividir_itens(s.texto)]
        elif s.tipo == "beneficios":
            benef += [i[:1].upper() + i[1:] for i in dividir_itens(s.texto)]
    return resp, benef


def vaga_de_texto(texto: str, id_vaga: str, nivel_padrao: str = NIVEL_PADRAO,
                  regime_padrao: str = REGIME_PADRAO) -> Vaga:
    """Converte o conteúdo de um arquivo de texto numa `Vaga` do contrato."""
    linhas = [l.strip() for l in texto.strip().splitlines()]
    if len(linhas) < 3:
        raise ValueError(f"vaga {id_vaga}: esperado título, 'Empresa — Cidade' e descrição")
    titulo = linhas[0]
    partes = re.split(r"\s+[—–]\s+", linhas[1], maxsplit=1)
    if len(partes) != 2:
        raise ValueError(f"vaga {id_vaga}: a 2ª linha deve ser 'Empresa — Cidade' (com travessão)")
    empresa, cidade = partes[0].strip(), partes[1].strip()
    descricao = " ".join(l for l in linhas[2:] if l)
    resp, benef = secoes_listas(descricao)
    return Vaga(
        id_vaga=id_vaga,
        titulo=titulo,
        empresa=empresa,
        cidade=cidade,
        regime=deduzir_regime(titulo, descricao, regime_padrao),
        nivel=deduzir_nivel(titulo, descricao, nivel_padrao),
        descricao=descricao,
        requisitos=[],
        responsabilidades=resp,
        beneficios=benef,
    )


def ler_vaga_texto(caminho: str | Path, **padroes) -> Vaga:
    caminho = Path(caminho)
    return vaga_de_texto(caminho.read_text(encoding="utf-8"), caminho.stem, **padroes)


def carregar_pasta_texto(pasta: str | Path, id_formando: str = "kit", **padroes) -> ConjuntoVagas:
    """Todas as vagas .txt de uma pasta, em ordem de nome, num ConjuntoVagas."""
    arquivos = sorted(Path(pasta).glob("*.txt"))
    if not arquivos:
        raise ValueError(f"nenhum arquivo .txt em {pasta}")
    return ConjuntoVagas(
        cabecalho=novo_cabecalho(MODULO, id_formando),
        vagas=[ler_vaga_texto(a, **padroes) for a in arquivos],
    )


def carregar_vagas(caminho: str | Path, **padroes) -> ConjuntoVagas:
    """Aceita um ConjuntoVagas .json, uma pasta de .txt ou um único .txt."""
    caminho = Path(caminho)
    if caminho.is_dir():
        return carregar_pasta_texto(caminho, **padroes)
    if caminho.suffix.lower() == ".txt":
        return ConjuntoVagas(cabecalho=novo_cabecalho(MODULO, "kit"), vagas=[ler_vaga_texto(caminho, **padroes)])
    return carregar(caminho, ConjuntoVagas)


def carregar_curriculo(caminho: str | Path) -> Curriculo:
    return carregar(caminho, Curriculo)


def carregar_perfil(caminho: Optional[str | Path]) -> Optional[PerfilCarreira]:
    return carregar(caminho, PerfilCarreira) if caminho else None
