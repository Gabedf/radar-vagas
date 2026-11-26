"""Configuração lida de variáveis de ambiente (e do arquivo .env, se existir).

Adaptado do módulo de exemplo do kit. Diferença importante: aqui o MODELO_LLM é
OPCIONAL. O núcleo do radar (extração por regras, nota, ranking e lacunas) é
100% código determinístico e roda sem nenhum modelo de linguagem; o LLM só é
necessário para o extrator LLM e para o agente que conversa sobre o resultado.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ErroConfiguracao(RuntimeError):
    """Configuração ausente ou inválida (a linha de comando devolve código 2)."""


@dataclass(frozen=True)
class Configuracao:
    modelo_llm: str | None  # "provedor:modelo"; None quando não configurado
    banco_sqlite: Path
    cache_requisitos: Path
    porta: int
    telemetria: bool
    extrator: str = "regras"  # extrator da rota POST /contrato/executar: "regras" ou "llm"
    saidas_dir: Path = Path("saidas")  # onde o agente explicador procura as saídas gravadas

    def exigir_modelo(self) -> str:
        """Devolve o modelo ou falha com mensagem clara (para quem precisa do LLM)."""
        if not self.modelo_llm:
            raise ErroConfiguracao(
                "Defina MODELO_LLM no formato provedor:modelo, por exemplo "
                "groq:openai/gpt-oss-120b (veja .env.exemplo)."
            )
        return self.modelo_llm


def carregar_configuracao() -> Configuracao:
    load_dotenv()
    modelo = os.getenv("MODELO_LLM", "").strip() or None
    banco = Path(os.getenv("BANCO_SQLITE", "dados/radar_vagas.db"))
    banco.parent.mkdir(parents=True, exist_ok=True)
    cache = Path(os.getenv("CACHE_REQUISITOS", "dados/cache_requisitos.json"))
    # A telemetria do Agno fica desligada, a menos que seja pedida explicitamente.
    telemetria = os.getenv("AGNO_TELEMETRY", "false").lower() == "true"
    os.environ["AGNO_TELEMETRY"] = "true" if telemetria else "false"
    extrator = os.getenv("EXTRATOR", "regras").strip().lower() or "regras"
    if extrator not in ("regras", "llm"):
        raise ErroConfiguracao(f"EXTRATOR deve ser 'regras' ou 'llm' (recebido: {extrator!r})")
    return Configuracao(
        extrator=extrator,
        saidas_dir=Path(os.getenv("SAIDAS_DIR", "saidas")),
        modelo_llm=modelo,
        banco_sqlite=banco,
        cache_requisitos=cache,
        porta=int(os.getenv("PORTA", "7777")),
        telemetria=telemetria,
    )
