"""Linha de comando do radar de vagas: `executar`, `servir` e `conversar`.

Exemplos:
    radar-vagas executar --curriculo cv.json --vagas conjunto_vagas.json \\
        --perfil perfil_carreira.json --saida-dir saidas/f01
    radar-vagas executar --curriculo cv.json --vagas pasta_com_txt/ --regime remoto hibrido
    radar-vagas servir --porta 7777
    radar-vagas conversar --formando f01      (precisa de MODELO_LLM e da chave)

`executar` roda as cinco etapas pelo Workflow do Agno (workflow.py), que dá o
mesmo resultado de pipeline.executar_radar.

Códigos de saída: 0 = ok; 2 = erro de configuração ou de entrada; 3 = resultado
incoerente com o currículo (invariante das lacunas violada).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .config import ErroConfiguracao, carregar_configuracao
from .documentos import salvar_resultado
from .entradas import NIVEL_PADRAO, REGIME_PADRAO, carregar_curriculo, carregar_perfil, carregar_vagas
from .lacunas import ErroInvariante
from .modelos import Filtros
from .pipeline import criar_extrator
from .workflow import executar_workflow

REGIMES = ["presencial", "hibrido", "remoto"]
NIVEIS_PRETENDIDOS = ["estagio", "trainee", "junior", "pleno", "senior"]


def cmd_executar(args) -> int:
    cfg = carregar_configuracao()
    cv = carregar_curriculo(args.curriculo)
    conjunto = carregar_vagas(args.vagas, nivel_padrao=args.nivel_padrao, regime_padrao=args.regime_padrao)
    perfil = carregar_perfil(args.perfil)
    filtros = Filtros(regimes=args.regime or [], cidades=args.cidade or [], niveis=args.nivel or [])
    extrator = criar_extrator(args.extrator, cfg)
    resultado = executar_workflow(cv, conjunto, perfil, filtros, extrator, telemetria=cfg.telemetria)
    caminhos = salvar_resultado(resultado, args.saida_dir)

    rel = resultado.relatorio
    print(f"Vagas analisadas: {len(rel.vagas_estruturadas)} (elegíveis: {len(resultado.elegiveis)})")
    print("Top 5:")
    for a in resultado.avaliacoes[:5]:
        marca = "" if a.elegivel else "  [fora dos filtros]"
        print(f"  {a.id_vaga:>5}  nota {a.nota:>3}{marca}")
    print(f"Recomendada: {rel.id_vaga_recomendada}")
    print(f"Lacunas: {', '.join(f'{l.habilidade} ({l.prioridade})' for l in resultado.lacunas.itens) or 'nenhuma'}")
    print(f"Extração: {resultado.origem_extracao} ({getattr(extrator, 'acertos', 0)} do cache, "
          f"{getattr(extrator, 'extraidas', 0)} extraídas agora)")
    reserva = getattr(getattr(extrator, "extrator", None), "vagas_na_reserva", [])
    if reserva:
        print(f"Aviso: o LLM não entregou requisitos válidos para {', '.join(reserva)}; usadas as regras")
    for aviso in resultado.avisos:
        print(f"Aviso: {aviso}")
    print("Arquivos gravados:")
    for caminho in caminhos.values():
        print(f"  {caminho}")
    return 0


def cmd_servir(args) -> int:
    from .servidor import criar_agent_os  # importado só aqui: só o servidor precisa do AgentOS

    cfg = carregar_configuracao()
    agent_os = criar_agent_os(cfg)
    agent_os.serve(app=agent_os.get_app(), port=args.porta or cfg.porta)
    return 0


def cmd_conversar(args, entrada=input) -> int:
    """Conversa no terminal com o agente explicador sobre as saídas de um formando."""
    from agno.db.sqlite import SqliteDb

    from .explicador import RegistroResultados, criar_explicador

    cfg = carregar_configuracao()
    registro = RegistroResultados(cfg.saidas_dir)
    if registro.obter(args.formando) is None:
        raise ErroConfiguracao(f"sem resultado de {args.formando} em {cfg.saidas_dir}/; rode `radar-vagas executar` antes")
    try:
        agente = criar_explicador(cfg.exigir_modelo(), SqliteDb(db_file=str(cfg.banco_sqlite)), registro, cfg.telemetria)
    except ImportError as e:
        raise ErroConfiguracao(f"{e}. Instale o extra do provedor (ex.: uv pip install -e \".[groq]\")") from e
    sessao = f"terminal-{args.formando}"
    print(f"Explicador do radar ({args.formando}). Digite /fim para sair.")
    while True:
        texto = entrada("\nVocê: ").strip()
        if texto in ("/fim", "/sair"):
            return 0
        if texto:
            pergunta = f"[formando {args.formando}] {texto}"
            print("\n" + str(agente.run(pergunta, session_id=sessao).content))


def main(argv=None) -> int:
    try:  # acentos no terminal do Windows
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="radar-vagas", description="Radar de vagas: aderência, ranking e lacunas.")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("executar", help="analisa as vagas e grava relatorio_aderencia.json, lacunas.json e relatorio.md")
    p.add_argument("--curriculo", type=Path, required=True, help="arquivo Curriculo (JSON)")
    p.add_argument("--vagas", type=Path, required=True, help="ConjuntoVagas (JSON), pasta com vagas .txt ou um .txt")
    p.add_argument("--perfil", type=Path, help="arquivo PerfilCarreira (JSON), fonte dos filtros")
    p.add_argument("--regime", nargs="+", choices=REGIMES, help="substitui os regimes do perfil")
    p.add_argument("--cidade", nargs="+", help="substitui as cidades do perfil")
    p.add_argument("--nivel", nargs="+", choices=NIVEIS_PRETENDIDOS, help="substitui o nível pretendido do perfil")
    p.add_argument("--extrator", choices=["regras", "llm"], default="regras", help="como extrair os requisitos (padrão: regras)")
    p.add_argument("--nivel-padrao", default=NIVEL_PADRAO, choices=NIVEIS_PRETENDIDOS, help="nível das vagas .txt sem indicação")
    p.add_argument("--regime-padrao", default=REGIME_PADRAO, choices=REGIMES, help="regime das vagas .txt sem indicação")
    p.add_argument("--saida-dir", type=Path, required=True, help="pasta onde gravar as saídas")

    p = sub.add_parser("servir", help="inicia o servidor AgentOS (rota POST /contrato/executar)")
    p.add_argument("--porta", type=int, default=None)

    p = sub.add_parser("conversar", help="conversa no terminal com o agente explicador (precisa de MODELO_LLM)")
    p.add_argument("--formando", required=True, help="id do formando com saídas em saidas/<id>/ (ex.: f01)")

    args = parser.parse_args(argv)
    comandos = {"executar": cmd_executar, "servir": cmd_servir, "conversar": cmd_conversar}
    try:
        return comandos[args.comando](args)
    except (ErroConfiguracao, ValueError, ValidationError, OSError) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 2
    except ErroInvariante as e:
        print(f"Erro: resultado incoerente com o currículo: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
