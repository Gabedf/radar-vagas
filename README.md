# Radar de vagas — Módulo 3 (`radar_vagas`)

Módulo do ecossistema "Do diploma ao primeiro emprego". Recebe o **currículo** do formando, um **conjunto de vagas** e, opcionalmente, o **perfil de carreira**, e produz:

- `relatorio_aderencia.json` (`RelatorioAderencia`): as vagas com os requisitos extraídos, a nota de aderência de 0 a 100 de cada uma, o ranking, a vaga recomendada e as competências mais pedidas;
- `lacunas.json` (`Lacunas`): as habilidades que faltam ao formando, priorizadas, para o tutor de estudos;
- `relatorio.md`: um relatório legível com o ranking, a conta da nota e as lacunas.

A nota, o ranking e as lacunas são calculados **em código** por um motor de regras determinístico (veja [docs/MOTOR_DE_REGRAS.md](docs/MOTOR_DE_REGRAS.md)). O modelo de linguagem só entra, opcionalmente, para extrair requisitos e conversar sobre o resultado.

## Instalação

Requer Python 3.10+ (recomendado 3.12) e o [uv](https://docs.astral.sh/uv/). O kit do trabalho deve estar ao lado deste repositório (`../kit-ecossistema`).

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -e "../kit-ecossistema/contratos[entrega]" -e ".[testes]"
# opcional, para usar um provedor de LLM: -e ".[groq]" ou -e ".[google]"
```

No Windows, os comandos ficam em `.venv\Scripts\` (por exemplo, `.venv\Scripts\radar-vagas.exe`); com o ambiente ativado (`.venv\Scripts\activate`), basta `radar-vagas`.

## Configuração

Copie `.env.exemplo` para `.env` e preencha. **Nenhuma variável é obrigatória** para o modo `regras`: a nota, o ranking, as lacunas, a linha de comando e a rota do contrato funcionam sem LLM e sem internet.

| Variável | Uso | Padrão |
|---|---|---|
| `MODELO_LLM` | `provedor:modelo`, só para o extrator LLM e o agente explicador | (vazio) |
| `GROQ_API_KEY` | chave do provedor (nunca vai para o repositório) | (vazio) |
| `EXTRATOR` | extrator da rota `POST /contrato/executar`: `regras` ou `llm` | `regras` |
| `SAIDAS_DIR` | pasta das saídas lidas pelo agente explicador | `saidas` |
| `BANCO_SQLITE` | banco das sessões do AgentOS | `dados/radar_vagas.db` |
| `CACHE_REQUISITOS` | cache das extrações de requisitos | `dados/cache_requisitos.json` |
| `PORTA` | porta do servidor | `7777` |

### Chave gratuita do Groq

1. Crie uma conta em <https://console.groq.com> e gere uma chave em *API Keys* (camada gratuita).
2. Instale o pacote do provedor: `uv pip install --python .venv -e ".[groq]"`.
3. No `.env`: `MODELO_LLM=groq:openai/gpt-oss-120b` e `GROQ_API_KEY=<sua chave>`.

O limite de requisições da camada gratuita (HTTP 429) é tratado pelo Agno: cada agente usa `retries=3` com espera exponencial (5 s, 10 s, 20 s). Se o modelo continuar indisponível, o extrator LLM usa as regras nas vagas restantes e avisa.

## Execução via linha de comando

```bash
# Saídas de um formando do kit (repita para f02 e f03)
radar-vagas executar \
  --curriculo ../kit-ecossistema/exemplos/f01/curriculo.json \
  --vagas ../kit-ecossistema/insumos/m3_radar_vagas/conjunto_vagas.json \
  --perfil ../kit-ecossistema/exemplos/f01/perfil_carreira.json \
  --saida-dir saidas/f01

# Conferência com o verificador do kit
carreira-verificar radar_vagas \
  --entrada ../kit-ecossistema/exemplos/f01/curriculo.json ../kit-ecossistema/insumos/m3_radar_vagas/conjunto_vagas.json \
  --saida saidas/f01/relatorio_aderencia.json saidas/f01/lacunas.json
```

`executar` roda as cinco etapas pelo **Workflow do Agno** "Radar de vagas" (`workflow.py`: extração → normalização → comparação → ranqueamento → consolidação) e grava em `--saida-dir`:
`relatorio_aderencia.json`, `lacunas.json`, `relatorio.md` e `rastro_calculo.json` (a conta completa de cada vaga, lida pelo agente explicador).

Outras opções de `executar`:

- `--vagas` aceita também uma **pasta de arquivos .txt** (formato de `insumos/m3_radar_vagas/vagas_texto/`) ou um único `.txt`;
- `--regime`, `--cidade` e `--nivel` substituem os filtros do perfil (ex.: `--regime remoto hibrido`);
- `--nivel-padrao` e `--regime-padrao` definem o que usar quando a vaga em texto não indica nível ou regime;
- `--extrator regras|llm` escolhe a extração dos requisitos (padrão: `regras`, sem LLM). Com `llm`, o agente "Extrator de requisitos" devolve saída estruturada e o código confere cada item: o trecho precisa estar literalmente na vaga, o nível vem do texto, a seção "Desejável:" torna o requisito desejável, o nome passa pelo dicionário. Se nada sobrar, há uma nova tentativa com os problemas; depois, as regras. O resultado fica no cache (`dados/cache_requisitos.json`), então as próximas execuções não chamam o modelo.

Conversa no terminal (precisa de `MODELO_LLM` e da chave): `radar-vagas conversar --formando f01`.

Testes (não usam LLM nem rede; o modelo é um dublê roteirizado): `python -m pytest`.

## Servidor e rota do contrato

```bash
radar-vagas servir            # ou: radar-vagas servir --porta 7777
```

- Documentação interativa: <http://localhost:7777/docs>.
- `POST /contrato/executar` — corpo `{"curriculo": Curriculo, "conjunto_vagas": ConjuntoVagas, "perfil_carreira": PerfilCarreira (opcional)}`; resposta `{"relatorio_aderencia": RelatorioAderencia, "lacunas": Lacunas}`. Entrada inválida → 422 com o detalhe.
- `GET /relatorio/{id_formando}` — o relatório em Markdown do último resultado (da rota ou de `saidas/<id>/`).
- Rotas do AgentOS (`/config`, `/agents`, `/workflows`...), usadas pela interface gráfica.

O servidor sobe **sem chave de LLM**: a rota usa o extrator por regras (ou o LLM, com `EXTRATOR=llm` e modelo configurado). O agente explicador só é registrado quando há `MODELO_LLM`; sem ele, o log avisa e o resto funciona.

## Conversa na interface gráfica (AgentOS)

O agente **"Explicador do radar"** (`radar-explicador`) responde perguntas como "por que a vaga v25 ficou abaixo da vf01?" ou "o que devo estudar primeiro?". Ele **não calcula nada**: usa ferramentas que leem o resultado já calculado (`listar_formandos`, `resumo`, `ver_avaliacao`, `comparar_vagas`, `ver_lacunas`, `explicar_regras`) — os resultados da rota `POST /contrato/executar` e as pastas `saidas/<id>/`.

1. Configure `MODELO_LLM` e a chave no `.env` e rode `radar-vagas servir`.
2. **os.agno.com**: entre em <https://os.agno.com>, clique em *Add new OS* → *Local*, use o endereço `http://localhost:7777` e um nome (ex.: "Radar de vagas"). Em *Chat*, escolha o agente "Explicador do radar".
3. **Agent UI** (alternativa local): `npx create-agent-ui@latest`, depois `npm run dev` na pasta criada; abra <http://localhost:3000> e aponte o endpoint para `http://localhost:7777`.
4. Pergunte, por exemplo: "Resuma o resultado do f01", "Por que a vaga v25 ficou abaixo da vf01?", "Por que a v04 tem nota 100 e não foi recomendada?".

O workflow "Radar de vagas" também aparece no painel, com as cinco etapas.

## Estrutura

```
src/radar_vagas/
  entradas.py        F1  leitura do ConjuntoVagas (JSON) e de vagas em texto
  extrator_regras.py F2  extração de requisitos por seções e dicionário
  extrator_llm.py    F2  extração com agente Agno + guardas em código (modo llm)
  normalizacao.py    F3  normalização de habilidades e níveis
  dados/dicionario_habilidades.yaml   nome canônico <- aliases
  motor.py           F4  R1–R4: classificação, nota e justificativa
  ranking.py         F5, F6, F8  R5–R7: filtros, ranking, recomendação, mais pedidas
  lacunas.py         F7  R8: consolidação e prioridade das lacunas
  relatorio_md.py    F9  relatório em Markdown
  cache.py           cache das extrações (dados/cache_requisitos.json)
  documentos.py      montagem e gravação dos documentos do contrato
  pipeline.py        as cinco etapas como funções (executar_radar)
  workflow.py        as cinco etapas como Workflow do Agno (executar_workflow)
  explicador.py      agente "Explicador do radar" e suas ferramentas de leitura
  servidor.py        AgentOS + rotas do contrato
  cli.py             linha de comando (executar, servir, conversar)
saidas/f01..f03/     saídas dos formandos do kit
casos_teste/         casos de teste com o resultado esperado
docs/                motor de regras (MOTOR_DE_REGRAS.md) e roteiro da demonstração (DEMO.md)
relatorio/           relatório em Typst (modelo do kit)
```

## Limitações

- A extração por regras depende dos marcadores das seções ("Requisitos:", "Diferenciais:"...) e do dicionário: habilidade fora do dicionário não vira requisito (aparece no relatório como "item sem habilidade conhecida").
- Formação ("Cursando ...") e tempo de experiência ("três anos") não viram requisitos, porque o currículo não tem um nível comparável.
- Só `habilidades` e `idiomas` do currículo contam; `tecnologias` de projetos e experiências não dão crédito, porque não têm nível.
- Nas vagas em texto, regime e nível são deduzidos por palavras-chave; quando o texto não diz, valem os padrões (`presencial`, `junior`).
- O crédito do requisito parcial é fixo (0,5), não importa a distância entre os níveis.
- As lacunas consideram todas as vagas elegíveis, inclusive de outras áreas que passam nos filtros; a prioridade (alta/média/baixa) separa o que importa para a vaga recomendada.
- O extrator LLM e o agente explicador foram testados com um modelo roteirizado (sem rede); com um modelo real, a qualidade da extração depende do modelo, mas as guardas em código descartam trechos inventados e níveis não escritos na vaga.
