"""Fixtures comuns: caminhos do kit e documentos de exemplo.

O kit fica, por padrão, ao lado do repositório (../kit-ecossistema); para
outro lugar, defina a variável de ambiente KIT_ECOSSISTEMA.
Nenhum teste usa modelo de linguagem nem rede.
"""

import os
from pathlib import Path

import pytest

from carreira_contratos import ConjuntoVagas, Curriculo, PerfilCarreira, RelatorioAderencia, carregar

KIT = Path(os.getenv("KIT_ECOSSISTEMA", Path(__file__).resolve().parents[2] / "kit-ecossistema"))
EXEMPLOS = KIT / "exemplos"
INSUMOS = KIT / "insumos" / "m3_radar_vagas"

if not (EXEMPLOS / "f01").is_dir():
    pytest.exit(f"Kit não encontrado em {KIT}; defina KIT_ECOSSISTEMA", returncode=2)


def cv_de(idf: str) -> Curriculo:
    return carregar(EXEMPLOS / idf / "curriculo.json", Curriculo)


def perfil_de(idf: str) -> PerfilCarreira:
    return carregar(EXEMPLOS / idf / "perfil_carreira.json", PerfilCarreira)


@pytest.fixture
def cv_f01() -> Curriculo:
    return cv_de("f01")


@pytest.fixture
def perfil_f01() -> PerfilCarreira:
    return perfil_de("f01")


@pytest.fixture
def conjunto_30() -> ConjuntoVagas:
    """O conjunto completo da entrega (30 vagas, todas com requisitos vazios)."""
    return carregar(INSUMOS / "conjunto_vagas.json", ConjuntoVagas)


@pytest.fixture
def conjunto_exemplo() -> ConjuntoVagas:
    """As 3 vagas do exemplo f01 (vf01, vx01, vx02), com requisitos vazios."""
    return carregar(EXEMPLOS / "f01" / "conjunto_vagas.json", ConjuntoVagas)


@pytest.fixture
def relatorio_exemplo() -> RelatorioAderencia:
    """Gabarito do kit: relatório de aderência do f01 com as 3 vagas estruturadas."""
    return carregar(EXEMPLOS / "f01" / "relatorio_aderencia.json", RelatorioAderencia)


# ------------------------------------------------------------------ modelo de teste
# Copiado do módulo de exemplo do kit (modulo_exemplo/tests/conftest.py).

import json  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from agno.models.base import Model  # noqa: E402
from agno.models.response import ModelResponse  # noqa: E402


@dataclass
class ModeloRoteirizado(Model):
    """Modelo de linguagem roteirizado: devolve respostas predefinidas, sem acessar a rede.

    Cada chamada ao modelo consome a próxima resposta da lista.
    """

    id: str = "roteirizado"
    name: str = "ModeloRoteirizado"
    provider: str = "teste"
    respostas: list = field(default_factory=list)
    chamadas: int = 0

    def invoke(self, *args, **kwargs):
        self.chamadas += 1
        texto = self.respostas.pop(0) if self.respostas else "Sem resposta roteirizada."
        return ModelResponse(role="assistant", content=texto)

    async def ainvoke(self, *args, **kwargs):
        return self.invoke()

    def invoke_stream(self, *args, **kwargs):
        yield self.invoke()

    async def ainvoke_stream(self, *args, **kwargs):
        yield self.invoke()

    def _parse_provider_response(self, response, **kwargs):
        return response

    def _parse_provider_response_delta(self, response):
        return response


def resposta_extrator(*requisitos, ignorados=()) -> str:
    """JSON no formato RequisitosExtraidos. Cada requisito: (trecho, habilidade, nivel, obrigatorio)."""
    return json.dumps({
        "requisitos": [
            {"trecho": t, "habilidade": h, "nivel_minimo": n, "obrigatorio": o} for t, h, n, o in requisitos
        ],
        "ignorados": list(ignorados),
    }, ensure_ascii=False)
