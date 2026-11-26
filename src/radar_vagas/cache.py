"""Cache das extrações de requisitos (dados/cache_requisitos.json).

Por que existe: com o extrator LLM, extrair as 30 vagas custa chamadas ao
modelo (tempo, cota, HTTP 429) e o resultado pode variar entre execuções.
Guardando a extração, as saídas ficam REPRODUTÍVEIS e as próximas execuções
não chamam o modelo. O arquivo é versionado no repositório.

Chave de cada vaga: "<id_vaga>:<12 primeiros hex do sha256 da descrição>".
Se o texto da vaga mudar, a chave muda e a vaga é extraída de novo.

Formato do arquivo:
    {
      "v01:3fa2c1d0e9ab": {
        "regras": {"origem": "regras", "versao": "regras-1-dic-2c6ee102", "requisitos": [...]},
        "llm":    {"origem": "llm",    "versao": "llm-prompt-1",          "requisitos": [...]}
      },
      ...
    }
Cada origem tem sua própria entrada; uma entrada só é reaproveitada se a
`versao` for a mesma do extrator atual (mudou o dicionário/prompt -> refaz).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carreira_contratos import Requisito, Vaga

from .extrator_regras import Extrator

CAMINHO_PADRAO = Path("dados") / "cache_requisitos.json"


def chave_vaga(vaga: Vaga) -> str:
    resumo = hashlib.sha256(vaga.descricao.encode("utf-8")).hexdigest()[:12]
    return f"{vaga.id_vaga}:{resumo}"


class ExtratorComCache:
    """Envolve qualquer `Extrator` e guarda/reaproveita o resultado em JSON.

    Também segue o protocolo `Extrator` (tem `extrair(vaga)`), então o
    pipeline não precisa saber se há cache ou não.
    """

    def __init__(self, extrator: Extrator, caminho: str | Path = CAMINHO_PADRAO,
                 origem: str | None = None, versao: str | None = None):
        self.extrator = extrator
        self.caminho = Path(caminho)
        self.origem = origem or getattr(extrator, "origem", "desconhecida")
        self.versao = versao or getattr(extrator, "versao", "1")
        self._dados: dict | None = None
        self.acertos = 0  # quantas vagas vieram do cache (útil para relatar)
        self.extraidas = 0  # quantas precisaram ser extraídas agora

    def _carregar(self) -> dict:
        if self._dados is None:
            try:
                self._dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._dados = {}  # sem arquivo (ou arquivo inválido): começa vazio
        return self._dados

    def _gravar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = json.dumps(self._dados, ensure_ascii=False, indent=2, sort_keys=True)
        self.caminho.write_text(texto + "\n", encoding="utf-8")

    def obter(self, vaga: Vaga) -> list[Requisito] | None:
        """Requisitos em cache para esta vaga e versão, ou None."""
        entrada = self._carregar().get(chave_vaga(vaga), {}).get(self.origem)
        if entrada and entrada.get("versao") == self.versao:
            return [Requisito.model_validate(r) for r in entrada["requisitos"]]
        return None

    def extrair(self, vaga: Vaga) -> list[Requisito]:
        guardados = self.obter(vaga)
        if guardados is not None:
            self.acertos += 1
            return guardados
        requisitos = self.extrator.extrair(vaga)
        self.extraidas += 1
        if getattr(self.extrator, "usou_reserva", False):
            # O extrator LLM caiu nas regras para esta vaga: não grava como "llm",
            # para tentar o modelo de novo na próxima execução.
            return requisitos
        self._carregar().setdefault(chave_vaga(vaga), {})[self.origem] = {
            "origem": self.origem,
            "versao": self.versao,
            "requisitos": [r.model_dump() for r in requisitos],
        }
        self._gravar()
        return requisitos
