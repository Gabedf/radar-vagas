"""F9 — Relatório legível em Markdown.

Só formata o que o motor já calculou; nenhum número é recalculado aqui.
"""

from __future__ import annotations

from carreira_contratos import Curriculo, Lacunas, Vaga

from .modelos import AvaliacaoInterna, Filtros, Ranking
from .motor import NOME_NIVEL, PESO_DESEJAVEL, PESO_OBRIGATORIO
from .ranking import niveis_aceitos

SITUACAO = {"atendido": "atendido", "parcial": "parcial", "faltante": "faltante"}


def _c(texto: object) -> str:
    """Escapa o caractere | para não quebrar as tabelas."""
    return str(texto).replace("|", "\\|")


def _num(x: float, casas: int | None = None) -> str:
    """Número no formato brasileiro: 0.5 -> '0,5'; 81.818 com 2 casas -> '81,82'."""
    texto = f"{x:.{casas}f}" if casas is not None else f"{x:g}"
    return texto.replace(".", ",")


def _filtros(filtros: Filtros) -> str:
    if filtros.vazio():
        return "nenhum (todas as vagas são elegíveis)"
    partes = []
    if filtros.regimes:
        partes.append("regime: " + ", ".join(filtros.regimes))
    if filtros.cidades:
        partes.append("cidades: " + ", ".join(filtros.cidades) + " (vaga remota dispensa a cidade)")
    if filtros.niveis:
        partes.append("nível: " + ", ".join(sorted(niveis_aceitos(filtros))))
    return "; ".join(partes)


def _tabela_requisitos(aval: AvaliacaoInterna) -> list[str]:
    linhas = [
        "| Requisito | Habilidade | Tipo | Pede | Tem | Situação | Pontos |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in aval.classificacoes:
        tipo = "obrigatório" if c.requisito.obrigatorio else "desejável"
        linhas.append(
            f"| {_c(c.rotulo)} | {_c(c.habilidade)} | {tipo} | {NOME_NIVEL[c.nivel_pedido]} | "
            f"{NOME_NIVEL[c.nivel_atual]} | {SITUACAO[c.status]} | {c.peso} × {_num(c.credito)} = {_num(c.peso * c.credito)} |"
        )
    pontos = sum(c.peso * c.credito for c in aval.classificacoes)
    pesos = sum(c.peso for c in aval.classificacoes)
    if pesos:
        linhas.append("")
        linhas.append(f"Nota = arred(100 × {_num(pontos)} / {pesos}) = arred({_num(100 * pontos / pesos, 2)}) = **{aval.nota}**")
    return linhas


def gerar_markdown(cv: Curriculo, vagas: list[Vaga], ranking: Ranking, lacunas: Lacunas, filtros: Filtros,
                   nao_mapeadas: list[str] | None = None, avisos: list[str] | None = None,
                   origem_extracao: str = "regras") -> str:
    por_id = {v.id_vaga: v for v in vagas}
    aval_por_id = {a.id_vaga: a for a in ranking.avaliacoes}
    rec = por_id[ranking.id_vaga_recomendada]
    aval_rec = aval_por_id[rec.id_vaga]
    md: list[str] = []

    md.append(f"# Radar de vagas — {_c(cv.dados_pessoais.nome)} ({cv.cabecalho.id_formando})")
    md.append("")
    md.append(f"- Vagas analisadas: **{len(vagas)}**; elegíveis pelos filtros: **{len(ranking.elegiveis)}**")
    md.append(f"- Filtros: {_filtros(filtros)}")
    md.append(f"- Extração dos requisitos: {origem_extracao}")
    md.append("")

    md.append("## Vaga recomendada")
    md.append("")
    md.append(f"**{rec.id_vaga} — {_c(rec.titulo)}** ({_c(rec.empresa)}, {_c(rec.cidade)}, {rec.regime}, {rec.nivel}) — nota **{aval_rec.nota}**")
    md.append("")
    md.append(ranking.justificativa_recomendacao)
    md.append("")
    md += _tabela_requisitos(aval_rec)
    md.append("")

    md.append("## Ranking das vagas")
    md.append("")
    md.append("| # | Vaga | Título | Empresa | Cidade | Regime | Nível | Nota | Obrigatórios | Desejáveis | Elegível |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for pos, a in enumerate(ranking.avaliacoes, start=1):
        v = por_id[a.id_vaga]
        elegivel = "✓" if a.elegivel else "✗"
        md.append(
            f"| {pos} | {v.id_vaga} | {_c(v.titulo)} | {_c(v.empresa)} | {_c(v.cidade)} | {v.regime} | {v.nivel} | "
            f"{a.nota} | {a.obrigatorios_atendidos}/{a.obrigatorios_total} | {a.desejaveis_atendidos}/{a.desejaveis_total} | {elegivel} |"
        )
    md.append("")
    md.append("Motivos de exclusão e justificativas:")
    md.append("")
    for a in ranking.avaliacoes:
        md.append(f"- **{a.id_vaga}** ({a.nota}): {a.justificativa}")
    md.append("")

    md.append("## Lacunas")
    md.append("")
    if lacunas.itens:
        md.append(f"Consideradas as vagas elegíveis; vaga-alvo: {lacunas.id_vaga_alvo}.")
        md.append("")
        md.append("| Prioridade | Habilidade | Nível atual | Nível necessário | Obrigatória | Frequência | Vagas |")
        md.append("|---|---|---|---|---|---|---|")
        for l in lacunas.itens:
            md.append(
                f"| {l.prioridade} | {_c(l.habilidade)} | {NOME_NIVEL[l.nivel_atual]} | {NOME_NIVEL[l.nivel_necessario]} | "
                f"{'sim' if l.obrigatoria else 'não'} | {l.frequencia} | {', '.join(l.vagas_relacionadas)} |"
            )
    else:
        md.append("Nenhuma lacuna nas vagas consideradas.")
    md.append("")

    md.append("## Competências mais pedidas")
    md.append("")
    md.append("| Competência | Vagas que pedem | % do conjunto |")
    md.append("|---|---|---|")
    for h in ranking.competencias_mais_pedidas:
        n = ranking.contagem_competencias.get(h, 0)
        md.append(f"| {_c(h)} | {n} | {100 * n / len(vagas):.0f}% |")
    md.append("")

    md.append("## Como a nota é calculada")
    md.append("")
    md.append(f"- Cada requisito vale **{PESO_OBRIGATORIO}** (obrigatório) ou **{PESO_DESEJAVEL}** (desejável).")
    md.append("- Crédito: **1** se o nível do formando é maior ou igual ao pedido; **0,5** se tem a habilidade em nível menor; **0** se não tem.")
    md.append("- Sem nível indicado na vaga, o nível pedido é básico. Idioma fluente conta como avançado.")
    md.append("- `nota = arred(100 × Σ(peso × crédito) / Σ peso)`, arredondando 0,5 para cima.")
    md.append("- Ranking: maior nota; empate → maior fração de obrigatórios atendidos; empate → id da vaga.")
    md.append("- Só contam as habilidades e os idiomas do currículo (as tecnologias de projetos e experiências não têm nível).")
    md.append("")

    if nao_mapeadas:
        md.append("## Habilidades e itens não mapeados no dicionário")
        md.append("")
        for n in nao_mapeadas:
            md.append(f"- {_c(n)}")
        md.append("")
    if avisos:
        md.append("## Avisos")
        md.append("")
        for a in avisos:
            md.append(f"- {_c(a)}")
        md.append("")
    return "\n".join(md)
