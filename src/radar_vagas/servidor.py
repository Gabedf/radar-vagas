"""Servidor AgentOS do radar de vagas, com as rotas do contrato.

Rotas próprias (app FastAPI base):
    POST /contrato/executar        {curriculo, conjunto_vagas, perfil_carreira?}
                                   -> {relatorio_aderencia, lacunas}
    GET  /relatorio/{id_formando}  relatório em Markdown do último resultado

Rotas do AgentOS (acrescentadas pelo Agno): /config, /agents, /workflows,
/agents/{id}/runs ... usadas pelo painel os.agno.com e pela Agent UI.

O servidor sobe SEM chave de LLM: a rota do contrato usa o extrator por
regras (EXTRATOR=regras, o padrão). O agente explicador só é registrado
quando há MODELO_LLM configurado (e o pacote do provedor instalado).
"""

from __future__ import annotations

import logging
from typing import Optional, Union

from agno.db.sqlite import SqliteDb
from agno.models.base import Model
from agno.os import AgentOS
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ValidationError

from carreira_contratos import ConjuntoVagas, Curriculo, Lacunas, PerfilCarreira, RelatorioAderencia

from .config import Configuracao, ErroConfiguracao
from .documentos import ARQUIVO_MARKDOWN
from .explicador import RegistroResultados, criar_explicador
from .extrator_regras import Extrator
from .lacunas import ErroInvariante
from .pipeline import criar_extrator
from .workflow import criar_workflow, executar_workflow

log = logging.getLogger(__name__)

ID_OS = "radar-vagas"


class EntradaContrato(BaseModel):
    """Corpo de POST /contrato/executar (entradas do módulo 3 na ficha de contrato)."""

    curriculo: Curriculo
    conjunto_vagas: ConjuntoVagas
    perfil_carreira: Optional[PerfilCarreira] = None


class SaidaContrato(BaseModel):
    """Resposta de POST /contrato/executar: os dois documentos de saída do módulo."""

    relatorio_aderencia: RelatorioAderencia
    lacunas: Lacunas


def _extrator_da_rota(cfg: Configuracao) -> Extrator:
    """Extrator escolhido por EXTRATOR; se o LLM não estiver configurado, cai nas regras (com aviso)."""
    try:
        return criar_extrator(cfg.extrator, cfg)
    except ErroConfiguracao as e:
        log.warning("EXTRATOR=%s indisponível (%s); a rota usará o extrator por regras.", cfg.extrator, e)
        return criar_extrator("regras", cfg)


def criar_agent_os(cfg: Configuracao, modelo: Union[Model, str, None] = None,
                   registro: Optional[RegistroResultados] = None,
                   extrator: Optional[Extrator] = None) -> AgentOS:
    """Monta o AgentOS. `modelo`, `registro` e `extrator` permitem injetar dublês nos testes."""
    registro = registro or RegistroResultados(cfg.saidas_dir)
    extrator = extrator or _extrator_da_rota(cfg)
    base = FastAPI(title="Radar de vagas (módulo 3)", version="1.0.0",
                   description="Aderência do currículo às vagas, ranking e lacunas, calculados por um motor de regras.")

    @base.post("/contrato/executar", response_model=SaidaContrato, tags=["Contrato"])
    def executar(entrada: EntradaContrato) -> SaidaContrato:
        try:
            resultado = executar_workflow(entrada.curriculo, entrada.conjunto_vagas, entrada.perfil_carreira,
                                          extrator=extrator, telemetria=cfg.telemetria)
        except ErroInvariante as e:
            raise HTTPException(status_code=422, detail={"erro": "invariante das lacunas", "mensagem": str(e)})
        except (ValueError, ValidationError) as e:
            raise HTTPException(status_code=422, detail={"erro": "entrada inválida", "mensagem": str(e)})
        registro.registrar(resultado)  # o explicador passa a conversar sobre este resultado
        return SaidaContrato(relatorio_aderencia=resultado.relatorio, lacunas=resultado.lacunas)

    @base.get("/relatorio/{id_formando}", response_class=PlainTextResponse, tags=["Contrato"])
    def relatorio(id_formando: str) -> PlainTextResponse:
        """Relatório em Markdown: o último calculado pela rota ou o de saidas/<id_formando>/."""
        resultado = registro.obter(id_formando)
        if resultado is not None:
            texto = resultado.markdown
        else:
            arquivo = registro.pasta / id_formando / ARQUIVO_MARKDOWN
            if not arquivo.is_file():
                raise HTTPException(status_code=404, detail=f"sem resultado para o formando '{id_formando}'")
            texto = arquivo.read_text(encoding="utf-8")
        return PlainTextResponse(texto, media_type="text/markdown; charset=utf-8")

    agentes = []
    modelo = modelo or cfg.modelo_llm
    if modelo is None:
        log.warning("MODELO_LLM não configurado: o agente explicador não foi registrado "
                    "(as rotas do contrato funcionam normalmente).")
    else:
        try:
            db = SqliteDb(db_file=str(cfg.banco_sqlite))
            agentes.append(criar_explicador(modelo, db, registro, telemetria=cfg.telemetria))
        except ImportError as e:  # ex.: groq:... sem o pacote groq
            log.warning("Agente explicador não registrado: %s. Instale o extra do provedor (ex.: uv pip install -e \".[groq]\").", e)

    return AgentOS(
        id=ID_OS,
        name="Radar de vagas",
        description="Módulo 3 do ecossistema: radar de vagas.",
        agents=agentes,
        workflows=[criar_workflow(cfg.telemetria)],  # as cinco etapas, visíveis no painel
        base_app=base,
        telemetry=cfg.telemetria,
    )
