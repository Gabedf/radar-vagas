"""Agente "Explicador do radar": conversa sobre um resultado JÁ calculado.

O agente não calcula nada. Ele responde usando FERRAMENTAS (funções Python
comuns) que só LEEM o resultado do radar:

- os resultados calculados pela rota POST /contrato/executar (guardados em
  memória, por id_formando, no `RegistroResultados`);
- as saídas gravadas em saidas/<id_formando>/ (pasta configurável pela
  variável SAIDAS_DIR), em especial o rastro_calculo.json, que guarda a
  conta completa de cada vaga (pesos, créditos, filtros).

Assim, os números que o agente cita são sempre os do motor de regras.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Callable, Optional, Union

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.base import Model

from .documentos import ARQUIVO_RASTRO
from .lacunas import LIMIAR_FREQUENCIA, MIN_VAGAS_FREQUENTE
from .modelos import AvaliacaoInterna, ResultadoRadar
from .motor import CREDITO, NIVEL_PADRAO, NOME_NIVEL, PESO_DESEJAVEL, PESO_OBRIGATORIO
from .ranking import COMPATIBILIDADE_NIVEL, TOP_COMPETENCIAS

ID_EXPLICADOR = "radar-explicador"

INSTRUCOES = [
    "Responda sempre em português do Brasil, de forma clara e curta.",
    "Você explica o resultado do radar de vagas de um formando: notas, ranking, vaga recomendada, filtros e lacunas.",
    "SEMPRE use as ferramentas para obter os dados antes de responder; nunca responda de memória nem estime números.",
    "Se não souber qual formando, use listar_formandos e pergunte (ou use o único disponível).",
    "Cite os números exatos devolvidos pelas ferramentas (nota, pesos, créditos, contagens).",
    "Explique que a nota é calculada por código determinístico (motor de regras), não pelo modelo de linguagem; você só explica a conta.",
    "Para perguntas do tipo 'por que a vaga X ficou abaixo da Y', use comparar_vagas e explique pela diferença de pontos (peso × crédito) e pelos critérios de desempate.",
    "Nunca atribua ao formando uma habilidade ou um nível que não esteja no currículo; use apenas o 'tem' devolvido pelas ferramentas.",
    "Não invente vagas, requisitos nem regras; para dúvidas sobre o método, use explicar_regras.",
]


class RegistroResultados:
    """Onde o explicador encontra os resultados: memória (rota) e pasta de saídas."""

    def __init__(self, pasta_saidas: Union[str, Path, None] = None):
        self.pasta = Path(pasta_saidas or os.getenv("SAIDAS_DIR", "saidas"))
        self._memoria: dict[str, ResultadoRadar] = {}

    def registrar(self, resultado: ResultadoRadar) -> None:
        self._memoria[resultado.relatorio.cabecalho.id_formando] = resultado

    def ids(self) -> list[str]:
        no_disco = {p.parent.name for p in self.pasta.glob(f"*/{ARQUIVO_RASTRO}")} if self.pasta.is_dir() else set()
        return sorted(no_disco | set(self._memoria))

    def obter(self, id_formando: str) -> Optional[ResultadoRadar]:
        if id_formando in self._memoria:  # o mais recente (calculado pela rota) tem preferência
            return self._memoria[id_formando]
        arquivo = self.pasta / id_formando / ARQUIVO_RASTRO
        if arquivo.is_file():
            return ResultadoRadar.model_validate_json(arquivo.read_text(encoding="utf-8"))
        return None


# ------------------------------------------------------------ formatação

def _nivel(n: Optional[str]) -> str:
    return NOME_NIVEL.get(n or "", n or "não indicado")


def _num(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _filtros(r: ResultadoRadar) -> str:
    f = r.filtros
    if f.vazio():
        return "sem filtros (todas as vagas são elegíveis)"
    partes = []
    if f.regimes:
        partes.append("regime " + " ou ".join(f.regimes))
    if f.cidades:
        partes.append("cidade " + " ou ".join(f.cidades) + " (vaga remota dispensa a cidade)")
    if f.niveis:
        partes.append("nível pretendido " + ", ".join(f.niveis))
    return "; ".join(partes)


def _conta(a: AvaliacaoInterna) -> tuple[float, int]:
    """(Σ peso×crédito, Σ peso) lidos das classificações gravadas."""
    return sum(c.peso * c.credito for c in a.classificacoes), sum(c.peso for c in a.classificacoes)


def _detalhe_avaliacao(r: ResultadoRadar, a: AvaliacaoInterna) -> str:
    vaga = next(v for v in r.vagas_estruturadas if v.id_vaga == a.id_vaga)
    posicao = [x.id_vaga for x in r.avaliacoes].index(a.id_vaga) + 1
    pontos, pesos = _conta(a)
    linhas = [
        f"Vaga {a.id_vaga}: {vaga.titulo} — {vaga.empresa} ({vaga.cidade}, {vaga.regime}, nível {vaga.nivel})",
        f"Nota: {a.nota} (posição {posicao} de {len(r.avaliacoes)} no ranking)",
        "Elegível: sim" if a.elegivel else "Elegível: NÃO — " + "; ".join(a.motivos_filtro),
        f"Obrigatórios atendidos: {a.obrigatorios_atendidos} de {a.obrigatorios_total}; "
        f"desejáveis atendidos: {a.desejaveis_atendidos} de {a.desejaveis_total}",
        "Requisitos (tipo, peso, pede, tem, situação, crédito, peso×crédito):",
    ]
    for c in a.classificacoes:
        tipo = "obrigatório" if c.requisito.obrigatorio else "desejável"
        linhas.append(
            f"- {c.rotulo} [{c.habilidade}]: {tipo}, peso {c.peso}, pede {_nivel(c.nivel_pedido)}, "
            f"tem {_nivel(c.nivel_atual)}, {c.status}, crédito {_num(c.credito)}, contribui {_num(c.peso * c.credito)}"
        )
    if pesos:
        linhas.append(f"Conta: nota = arred(100 × {_num(pontos)} / {pesos}) = arred({_num(round(100 * pontos / pesos, 2))}) = {a.nota}")
    linhas.append(f"Justificativa: {a.justificativa}")
    return "\n".join(linhas)


# ------------------------------------------------------------ ferramentas

def _seguro(ferramenta: Callable) -> Callable:
    """Erros previsíveis (formando ou vaga inexistente) voltam como texto para o agente,
    que pode então pedir outro id em vez de a conversa quebrar."""

    @functools.wraps(ferramenta)
    def envolvida(*args, **kwargs):
        try:
            return ferramenta(*args, **kwargs)
        except ValueError as e:
            return f"Erro: {e}"

    return envolvida


def criar_ferramentas(registro: RegistroResultados) -> list[Callable]:
    """Funções que o agente pode chamar. Todas só leem o resultado já calculado."""

    def _resultado(id_formando: str) -> ResultadoRadar:
        r = registro.obter(id_formando)
        if r is None:
            raise ValueError(f"não há resultado para o formando '{id_formando}'; disponíveis: {', '.join(registro.ids()) or 'nenhum'}")
        return r

    def _avaliacao(r: ResultadoRadar, id_vaga: str) -> AvaliacaoInterna:
        for a in r.avaliacoes:
            if a.id_vaga == id_vaga:
                return a
        raise ValueError(f"a vaga '{id_vaga}' não está no resultado; vagas: {', '.join(a.id_vaga for a in r.avaliacoes)}")

    def listar_formandos() -> str:
        """Lista os formandos que têm resultado do radar disponível (ids como f01, f02...)."""
        linhas = []
        for idf in registro.ids():
            r = registro.obter(idf)
            linhas.append(f"{idf}: {len(r.avaliacoes)} vagas analisadas, recomendada {r.relatorio.id_vaga_recomendada}")
        return "\n".join(linhas) or "Nenhum resultado disponível. Rode `radar-vagas executar` ou a rota POST /contrato/executar."

    def resumo(id_formando: str) -> str:
        """Resumo do resultado de um formando: filtros, vaga recomendada, melhores notas e lacunas principais.

        Args:
            id_formando: identificador do formando, por exemplo "f01".
        """
        r = _resultado(id_formando)
        rel = r.relatorio
        top = [
            f"{a.id_vaga} nota {a.nota}" + ("" if a.elegivel else " (fora dos filtros)")
            for a in r.avaliacoes[:5]
        ]
        lacunas = [f"{l.habilidade} ({l.prioridade})" for l in r.lacunas.itens[:5]]
        return "\n".join([
            f"Formando {id_formando}: {len(r.avaliacoes)} vagas analisadas, {len(r.elegiveis)} elegíveis.",
            f"Filtros do perfil: {_filtros(r)}.",
            f"Vaga recomendada: {rel.id_vaga_recomendada}. {rel.justificativa_recomendacao}",
            "Cinco primeiras do ranking: " + "; ".join(top) + ".",
            "Competências mais pedidas: " + ", ".join(rel.competencias_mais_pedidas) + ".",
            f"Lacunas ({len(r.lacunas.itens)}), as primeiras: " + (", ".join(lacunas) or "nenhuma") + ".",
            f"Extração dos requisitos: {r.origem_extracao}.",
        ])

    def ver_avaliacao(id_formando: str, id_vaga: str) -> str:
        """Avaliação completa de uma vaga: nota, requisitos atendidos/parciais/faltantes, conta da nota, elegibilidade e justificativa.

        Args:
            id_formando: identificador do formando, por exemplo "f01".
            id_vaga: identificador da vaga, por exemplo "v05".
        """
        r = _resultado(id_formando)
        return _detalhe_avaliacao(r, _avaliacao(r, id_vaga))

    def comparar_vagas(id_formando: str, id_vaga_a: str, id_vaga_b: str) -> str:
        """Compara duas vagas lado a lado (notas, contribuição de cada requisito e posição no ranking) e diz por que uma ficou acima da outra.

        Args:
            id_formando: identificador do formando, por exemplo "f01".
            id_vaga_a: primeira vaga, por exemplo "v03".
            id_vaga_b: segunda vaga, por exemplo "v05".
        """
        r = _resultado(id_formando)
        a, b = _avaliacao(r, id_vaga_a), _avaliacao(r, id_vaga_b)
        ordem = [x.id_vaga for x in r.avaliacoes]
        acima, abaixo = (a, b) if ordem.index(a.id_vaga) < ordem.index(b.id_vaga) else (b, a)
        if acima.nota != abaixo.nota:
            motivo = f"{acima.id_vaga} tem nota maior ({acima.nota} contra {abaixo.nota})."
        elif acima.fracao_obrigatorios != abaixo.fracao_obrigatorios:
            motivo = (f"As notas empatam em {acima.nota}; o desempate é a fração de obrigatórios atendidos: "
                      f"{acima.obrigatorios_atendidos}/{acima.obrigatorios_total} em {acima.id_vaga} contra "
                      f"{abaixo.obrigatorios_atendidos}/{abaixo.obrigatorios_total} em {abaixo.id_vaga}.")
        else:
            motivo = f"Nota e fração de obrigatórios empatam; o último desempate é a ordem alfabética do id ({acima.id_vaga} vem antes)."
        recomendada = r.relatorio.id_vaga_recomendada
        extra = []
        for x in (a, b):
            if not x.elegivel:
                extra.append(f"{x.id_vaga} está fora dos filtros e não pode ser recomendada ({'; '.join(x.motivos_filtro)}).")
        return "\n\n".join([
            f"Ranking: {acima.id_vaga} na posição {ordem.index(acima.id_vaga) + 1}, "
            f"{abaixo.id_vaga} na posição {ordem.index(abaixo.id_vaga) + 1}. {motivo}",
            *extra,
            f"Vaga recomendada do formando: {recomendada}.",
            "=== " + _detalhe_avaliacao(r, a),
            "=== " + _detalhe_avaliacao(r, b),
        ])

    def ver_lacunas(id_formando: str) -> str:
        """Lacunas do formando (o que falta estudar), em ordem de prioridade, com nível atual e necessário.

        Args:
            id_formando: identificador do formando, por exemplo "f01".
        """
        r = _resultado(id_formando)
        if not r.lacunas.itens:
            return "Nenhuma lacuna: o formando atende a todos os requisitos das vagas consideradas."
        linhas = [f"Vaga-alvo (recomendada): {r.lacunas.id_vaga_alvo}. Lacunas, da mais para a menos prioritária:"]
        for l in r.lacunas.itens:
            linhas.append(
                f"- {l.habilidade}: prioridade {l.prioridade}; tem {_nivel(l.nivel_atual)}, precisa {_nivel(l.nivel_necessario)}; "
                f"{'obrigatória' if l.obrigatoria else 'só desejável'} em alguma vaga; aparece em {l.frequencia} vaga(s): "
                + ", ".join(l.vagas_relacionadas)
            )
        return "\n".join(linhas)

    def explicar_regras() -> str:
        """Resumo das regras do motor: pesos, créditos, nota, filtros, ranking e prioridade das lacunas."""
        compat = "; ".join(f"{k} aceita {', '.join(sorted(v))}" for k, v in COMPATIBILIDADE_NIVEL.items())
        return "\n".join([
            "A nota é calculada por código determinístico (motor de regras R1–R8), não pelo modelo de linguagem.",
            "R1: só contam as habilidades e os idiomas do currículo, com nível (fluente = avançado); tecnologias de projetos não contam.",
            f"R2: cada requisito é atendido (crédito {_num(CREDITO['atendido'])}) se o nível do formando >= o pedido, "
            f"parcial ({_num(CREDITO['parcial'])}) se tem abaixo do pedido, faltante ({_num(CREDITO['faltante'])}) se não tem. "
            f"Nível não indicado na vaga = {_nivel(NIVEL_PADRAO)}. Em alternativas ('Python ou R'), vale a melhor.",
            f"R3: peso {PESO_OBRIGATORIO} para obrigatório e {PESO_DESEJAVEL} para desejável; "
            "nota = arred(100 × Σ(peso × crédito) / Σ peso), arredondando meio para cima (42,5 -> 43).",
            "R4: a justificativa é um texto montado em código com esses números.",
            f"R5: filtros do perfil — regime; cidade (vaga remota dispensa); nível ({compat}). Vaga fora dos filtros tem nota, mas não pode ser recomendada.",
            "R6: ranking por maior nota; empate -> maior fração de obrigatórios atendidos; empate -> id da vaga. Recomendada = 1ª elegível.",
            f"R7: competências mais pedidas = as {TOP_COMPETENCIAS} habilidades que aparecem em mais vagas.",
            f"R8: lacuna = habilidade parcial ou faltante em alguma vaga elegível. Frequente = em >= {int(LIMIAR_FREQUENCIA * 100)}% "
            f"das vagas consideradas e em >= {MIN_VAGAS_FREQUENTE} vagas. Prioridade alta: obrigatória na recomendada ou obrigatória frequente; "
            "média: obrigatória em alguma vaga ou frequente; baixa: o resto.",
        ])

    return [_seguro(f) for f in (listar_formandos, resumo, ver_avaliacao, comparar_vagas, ver_lacunas, explicar_regras)]


def criar_explicador(modelo: Union[Model, str], db: SqliteDb, registro: RegistroResultados,
                     telemetria: bool = False) -> Agent:
    """Agente conversacional do AgentOS (aparece em os.agno.com / Agent UI)."""
    return Agent(
        id=ID_EXPLICADOR,
        name="Explicador do radar",
        description="Explica as notas, o ranking, a vaga recomendada e as lacunas calculadas pelo radar de vagas.",
        model=modelo,
        db=db,
        tools=criar_ferramentas(registro),
        instructions=INSTRUCOES,
        add_history_to_context=True,
        num_history_runs=10,
        markdown=True,
        retries=3, delay_between_retries=5, exponential_backoff=True,  # HTTP 429
        telemetry=telemetria,
    )
