"""Montagem, validação e gravação dos documentos do contrato.

Saídas do módulo (ficha m3): RelatorioAderencia e Lacunas, sempre com
cabecalho.modulo = "radar_vagas" e o id_formando do currículo. Os modelos
Pydantic do contrato validam tudo na construção; `salvar` valida de novo
antes de gravar.
"""

from __future__ import annotations

from pathlib import Path

from carreira_contratos import Curriculo, Lacuna, Lacunas, RelatorioAderencia, Vaga, novo_cabecalho, salvar

from .modelos import Ranking, ResultadoRadar

MODULO = "radar_vagas"

ARQUIVO_RELATORIO = "relatorio_aderencia.json"
ARQUIVO_LACUNAS = "lacunas.json"
ARQUIVO_MARKDOWN = "relatorio.md"
# Rastro completo do cálculo (pesos, créditos, filtros): lido pelo agente explicador.
ARQUIVO_RASTRO = "rastro_calculo.json"


def montar_relatorio(cv: Curriculo, vagas_estruturadas: list[Vaga], ranking: Ranking) -> RelatorioAderencia:
    return RelatorioAderencia(
        cabecalho=novo_cabecalho(MODULO, cv.cabecalho.id_formando),
        vagas_estruturadas=vagas_estruturadas,
        avaliacoes=[a.para_contrato() for a in ranking.avaliacoes],  # já ordenadas (R6)
        id_vaga_recomendada=ranking.id_vaga_recomendada,
        justificativa_recomendacao=ranking.justificativa_recomendacao,
        competencias_mais_pedidas=ranking.competencias_mais_pedidas,
    )


def montar_lacunas(cv: Curriculo, id_vaga_alvo: str | None, itens: list[Lacuna]) -> Lacunas:
    return Lacunas(
        cabecalho=novo_cabecalho(MODULO, cv.cabecalho.id_formando),
        id_vaga_alvo=id_vaga_alvo,
        itens=itens,
    )


def salvar_resultado(resultado: ResultadoRadar, pasta: str | Path) -> dict[str, Path]:
    """Grava relatorio_aderencia.json, lacunas.json, relatorio.md e rastro_calculo.json na pasta."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = {
        "relatorio_aderencia": pasta / ARQUIVO_RELATORIO,
        "lacunas": pasta / ARQUIVO_LACUNAS,
        "markdown": pasta / ARQUIVO_MARKDOWN,
        "rastro": pasta / ARQUIVO_RASTRO,
    }
    salvar(resultado.relatorio, caminhos["relatorio_aderencia"])
    salvar(resultado.lacunas, caminhos["lacunas"])
    caminhos["markdown"].write_text(resultado.markdown, encoding="utf-8")
    caminhos["rastro"].write_text(resultado.model_dump_json(indent=2), encoding="utf-8")
    return caminhos
