"""F2 — Extração de requisitos com um agente do Agno (modo "llm").

O agente "Extrator de requisitos" lê a descrição de UMA vaga e devolve, em
saída estruturada (`RequisitosExtraidos`), a lista de requisitos com o trecho
do texto de onde cada um saiu.

O modelo de linguagem NÃO é confiável sozinho, então a saída passa por
"guardas" em código antes de virar `Requisito` do contrato:

1. trecho literal: o `trecho` precisa existir na descrição (comparação sem
   acentos/maiúsculas/pontuação). Trecho inventado = item descartado;
2. formação e tempo de experiência são descartados (mesma regra do extrator
   por regras, `motivo_ignorar`);
3. obrigatório x desejável: se o trecho está numa seção "Desejável:" /
   "Diferenciais:", o requisito é desejável, diga o modelo o que disser;
4. nível: vale o que está ESCRITO no trecho (`detectar_nivel`); se o texto
   não diz o nível, fica None (o modelo não pode inventar nível);
5. nome da habilidade: passa pelo dicionário (`normalizar_requisitos`), que
   também remove repetições.

Se, depois das guardas, nada sobrar, o agente recebe UMA nova tentativa com a
lista de problemas (como o `_gerar_verificado` do módulo de exemplo). Se ainda
assim nada sobrar (ou o modelo falhar), a vaga é extraída pelas REGRAS e o
fato é registrado no log. O HTTP 429 (limite de requisições) é tratado pelo
próprio Agno: `retries=3` com espera exponencial.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Union

from agno.agent import Agent
from agno.models.base import Model
from agno.run.base import RunStatus
from pydantic import BaseModel, Field, ValidationError

from carreira_contratos import Requisito, Vaga

from .cache import ExtratorComCache
from .config import Configuracao, ErroConfiguracao
from .extrator_regras import ExtratorRegras, dividir_secoes, motivo_ignorar
from .modelos import RequisitoBruto
from .normalizacao import Dicionario, detectar_nivel, dicionario_padrao, normalizar_texto
from .pipeline import normalizar_requisitos

log = logging.getLogger(__name__)

# Mude quando alterar as instruções: a versão entra na chave do cache.
VERSAO_PROMPT = "1"

INSTRUCOES = [
    "Você extrai os requisitos de habilidade de UMA vaga de emprego escrita em português.",
    "Cada requisito é uma habilidade técnica, ferramenta, idioma ou competência comportamental pedida ao candidato.",
    "Requisitos que aparecem depois de 'Requisitos:', 'Precisamos que você tenha:' ou 'O que buscamos:' são obrigatórios (obrigatorio = true).",
    "Requisitos que aparecem depois de 'Diferenciais:', 'Desejável:' ou 'Será um diferencial:', ou marcados como '(desejável)', são desejáveis (obrigatorio = false).",
    "Preencha nivel_minimo apenas quando o texto disser o nível: 'noções' ou 'básico' = basico; 'intermediário' = intermediario; 'avançado', 'sólido' ou 'domínio' = avancado. Se o texto não disser, deixe nivel_minimo vazio (null).",
    "NÃO transforme em requisito: formação ('Cursando ...', 'graduação em ...') nem tempo de experiência ('dois anos de experiência'); coloque esses trechos em 'ignorados'.",
    "Ignore responsabilidades, atividades e benefícios: eles não são requisitos.",
    "O campo 'trecho' deve ser COPIADO LITERALMENTE da descrição (o item inteiro, por exemplo 'Python básico para tratamento de dados'); nunca resuma nem reescreva.",
    "O campo 'habilidade' é o nome curto da habilidade (ex.: 'SQL', 'Power BI', 'Inglês', 'Apache Airflow').",
    "Quando um item listar várias habilidades ligadas por 'e' ou vírgula, crie um requisito para cada uma, todas com o mesmo trecho. Para alternativas ('Python ou R'), crie um só requisito com a primeira.",
]


class ErroModelo(RuntimeError):
    """O modelo não respondeu (chave ausente ou inválida, rede, 429 depois das novas tentativas)."""


class RequisitosExtraidos(BaseModel):
    """Saída estruturada pedida ao modelo para uma vaga."""

    requisitos: list[RequisitoBruto] = Field(
        default_factory=list, description="Requisitos de habilidade encontrados na vaga.")
    ignorados: list[str] = Field(
        default_factory=list, description="Trechos deixados de fora (formação, tempo de experiência).")


def _contem(texto: str, trecho: str) -> bool:
    """O trecho aparece no texto, palavra por palavra (sem acentos, maiúsculas e pontuação)?

    Os espaços nas pontas evitam casar pedaço de palavra ("git" dentro de "digital").
    """
    return f" {normalizar_texto(trecho)} " in f" {normalizar_texto(texto)} "


def _prompt(vaga: Vaga) -> str:
    return f"Vaga {vaga.id_vaga}: {vaga.titulo}\n\nDescrição:\n{vaga.descricao}"


class ExtratorLLM:
    """Extrator que usa um agente do Agno e confere a resposta em código.

    Segue o protocolo `Extrator` (`extrair(vaga) -> list[Requisito]`) e tem
    `origem`/`versao`, que o cache usa para separar as entradas.
    """

    origem = "llm"
    versao = f"llm-prompt-{VERSAO_PROMPT}"

    def __init__(self, modelo: Union[Model, str], dicionario: Dicionario | None = None,
                 telemetria: bool = False, tentativas: int = 2):
        self.dicionario = dicionario or dicionario_padrao()
        self.tentativas = tentativas
        self.reserva = ExtratorRegras(self.dicionario)  # usado quando o LLM não entrega nada
        self.agente = Agent(
            name="Extrator de requisitos",
            instructions=INSTRUCOES,
            output_schema=RequisitosExtraidos,
            # retries + backoff: o Agno espera e tenta de novo em erros como o HTTP 429.
            retries=3, delay_between_retries=5, exponential_backoff=True,
            model=modelo, telemetry=telemetria,
        )
        self.usou_reserva = False  # True quando a ÚLTIMA vaga caiu no extrator por regras
        self.vagas_na_reserva: list[str] = []
        self.modelo_indisponivel = False  # vira True na primeira falha de chamada ao modelo

    # ------------------------------------------------------------ guardas

    def conferir(self, vaga: Vaga, saida: RequisitosExtraidos) -> tuple[list[Requisito], list[str]]:
        """Aplica as guardas e devolve (requisitos aprovados, problemas encontrados)."""
        secoes = [s for s in dividir_secoes(vaga.descricao) if s.tipo in ("obrigatorio", "desejavel")]
        aprovados, problemas = [], []
        for bruto in saida.requisitos:
            trecho = bruto.trecho.strip()
            if not _contem(vaga.descricao, trecho):
                problemas.append(f"o trecho '{trecho}' não existe na descrição; copie o texto literalmente")
                continue
            motivo = motivo_ignorar(trecho)
            if motivo:
                problemas.append(f"'{trecho}' não é requisito de habilidade ({motivo})")
                continue
            tipos = {s.tipo for s in secoes if _contem(s.texto, trecho)}
            # A seção só rebaixa, nunca promove: trecho que está apenas em "Desejável:" é desejável.
            obrigatorio = bruto.obrigatorio and tipos != {"desejavel"}
            aprovados.append(Requisito(
                descricao=trecho,
                habilidade=bruto.habilidade.strip(),
                nivel_minimo=detectar_nivel(trecho),  # o nível vem do texto, não do modelo
                obrigatorio=obrigatorio,
            ))
        # Nome canônico pelo dicionário e uma habilidade por vaga.
        requisitos, nao_mapeadas = normalizar_requisitos(aprovados, self.dicionario)
        if nao_mapeadas:
            log.info("vaga %s: habilidades fora do dicionário: %s", vaga.id_vaga, ", ".join(nao_mapeadas))
        return requisitos, problemas

    # ------------------------------------------------------------ extração

    def _chamar(self, prompt: str) -> RequisitosExtraidos:
        saida = self.agente.run(prompt)
        conteudo = saida.content
        if saida.status == RunStatus.error:
            # O Agno não lança exceção: devolve a mensagem de erro como conteúdo (ex.: chave ausente).
            raise ErroModelo(str(conteudo))
        if isinstance(conteudo, RequisitosExtraidos):
            return conteudo
        return RequisitosExtraidos.model_validate_json(str(conteudo))

    def extrair(self, vaga: Vaga) -> list[Requisito]:
        self.usou_reserva = False
        if self.modelo_indisponivel:  # já falhou antes: não insiste em cada uma das vagas
            return self._reserva(vaga)
        prompt = _prompt(vaga)
        problemas: list[str] = []
        for _ in range(self.tentativas):
            entrada = prompt if not problemas else (
                prompt + "\n\nSua resposta anterior não trouxe nenhum requisito válido. Corrija:\n- "
                + "\n- ".join(problemas)
            )
            try:
                saida = self._chamar(entrada)
            except ValidationError as e:
                problemas = [f"a resposta não segue o formato pedido ({e.error_count()} erro(s))"]
                continue
            except Exception as e:  # rede, chave inválida, 429 esgotado...: não adianta repetir
                log.warning("falha ao chamar o modelo (%s); as próximas vagas usarão o extrator por regras", e)
                self.modelo_indisponivel = True
                break
            requisitos, problemas = self.conferir(vaga, saida)
            if requisitos:
                return requisitos
            problemas = problemas or ["nenhum requisito foi encontrado; procure as seções 'Requisitos:' e 'Desejável:'"]
        log.warning("vaga %s: o LLM não entregou requisitos válidos; usando o extrator por regras", vaga.id_vaga)
        return self._reserva(vaga)

    def _reserva(self, vaga: Vaga) -> list[Requisito]:
        """Extração por regras, registrada (o cache não guarda este resultado como "llm")."""
        self.usou_reserva = True
        self.vagas_na_reserva.append(vaga.id_vaga)
        return self.reserva.extrair(vaga)


# Variável da chave de cada provedor, para avisar ANTES de começar (sem chave, o Agno
# só descobre na chamada, depois de 3 novas tentativas com espera).
CHAVE_DO_PROVEDOR = {"groq": "GROQ_API_KEY", "google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY"}


def checar_chave(modelo: str) -> None:
    variavel = CHAVE_DO_PROVEDOR.get(modelo.split(":", 1)[0])
    if variavel and not os.getenv(variavel):
        raise ErroConfiguracao(f"defina {variavel} no .env para usar o modelo {modelo} (ou use --extrator regras)")


def criar_extrator_llm(cfg: Configuracao, modelo: Optional[Union[Model, str]] = None) -> ExtratorComCache:
    """Extrator LLM com cache (origem "llm"). `modelo` permite injetar um modelo de teste."""
    if modelo is None:
        modelo = cfg.exigir_modelo()
        checar_chave(modelo)
    try:
        extrator = ExtratorLLM(modelo, telemetria=cfg.telemetria)
    except ImportError as e:  # ex.: MODELO_LLM=groq:... sem o pacote groq instalado
        raise ErroConfiguracao(f"{e}. Instale o extra do provedor, por exemplo: uv pip install -e \".[groq]\"") from e
    return ExtratorComCache(extrator, cfg.cache_requisitos, origem="llm")
