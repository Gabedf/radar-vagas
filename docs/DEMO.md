# Roteiro da demonstração parcial (27/11)

Tempo alvo: 8 a 10 minutos. Todos os comandos partem da pasta `radar-vagas`, com o kit em `../kit-ecossistema`.
No Windows, use `.venv\Scripts\radar-vagas.exe` (ou ative o ambiente com `.venv\Scripts\activate` e use só `radar-vagas`).

**O que funciona sem internet e sem chave:** extração por regras, nota, ranking, filtros, lacunas, relatório em Markdown, linha de comando, servidor, rota do contrato, workflow e testes.
**O que precisa de `MODELO_LLM` + chave:** o extrator LLM (`--extrator llm` / `EXTRATOR=llm`) e a conversa com o agente explicador.

## 0. Antes de começar (5 min antes)

```bash
.venv/Scripts/python.exe -m pytest -q          # deve mostrar "127 passed"
```

Deixe abertos: este roteiro, `docs/MOTOR_DE_REGRAS.md` (exemplo resolvido f01 × vf01 = 82) e `saidas/f01/relatorio.md`.

## 1. O problema e a ideia (1 min)

- Entrada: currículo + 30 vagas (com `requisitos: []`) + perfil de carreira.
- Saída: `RelatorioAderencia` (nota 0–100, ranking, recomendada) e `Lacunas` (o que estudar).
- Mensagem principal: **a nota é calculada em código** (regras R1–R8). O LLM só entra para extrair requisitos (opcional, com guardas) e para conversar sobre o resultado.

## 2. Linha de comando (2 min)

```bash
.venv/Scripts/radar-vagas.exe executar \
  --curriculo ../kit-ecossistema/exemplos/f01/curriculo.json \
  --vagas ../kit-ecossistema/insumos/m3_radar_vagas/conjunto_vagas.json \
  --perfil ../kit-ecossistema/exemplos/f01/perfil_carreira.json \
  --saida-dir saidas/f01
```

Mostrar na saída: top 5 (v04 tem nota 100 mas está **fora dos filtros**: Cariacica, não remota), recomendada **vf01** (82), lacunas com Power BI em prioridade alta, "Extração: regras (30 do cache...)".

Abrir `saidas/f01/relatorio.md`: a tabela da conta da vf01 (9 de 11 pontos → 82).

Mostrar um filtro mudando o resultado:

```bash
.venv/Scripts/radar-vagas.exe executar --curriculo ../kit-ecossistema/exemplos/f01/curriculo.json \
  --vagas ../kit-ecossistema/insumos/m3_radar_vagas/conjunto_vagas.json \
  --perfil ../kit-ecossistema/exemplos/f01/perfil_carreira.json --regime presencial --saida-dir /tmp/f01_presencial
```

## 3. Verificador do kit (1 min)

```bash
for f in f01 f02 f03; do
  .venv/Scripts/carreira-verificar.exe radar_vagas \
    --entrada ../kit-ecossistema/exemplos/$f/curriculo.json ../kit-ecossistema/insumos/m3_radar_vagas/conjunto_vagas.json \
    --saida saidas/$f/relatorio_aderencia.json saidas/$f/lacunas.json
done
```

Esperado: três vezes "Aprovado".

## 4. Servidor e rota do contrato (2 min)

```bash
.venv/Scripts/radar-vagas.exe servir --porta 7777
```

1. Abrir <http://localhost:7777/docs> → `POST /contrato/executar` → *Try it out*. O corpo tem `curriculo`, `conjunto_vagas` e `perfil_carreira` (é grande; para colar rápido, gere o arquivo antes):

   ```bash
   .venv/Scripts/python.exe -c "import json;K='../kit-ecossistema/';l=lambda p:json.load(open(K+p,encoding='utf-8'));json.dump({'curriculo':l('exemplos/f01/curriculo.json'),'conjunto_vagas':l('insumos/m3_radar_vagas/conjunto_vagas.json'),'perfil_carreira':l('exemplos/f01/perfil_carreira.json')},open('corpo_f01.json','w',encoding='utf-8'),ensure_ascii=False)"
   curl -s -X POST http://localhost:7777/contrato/executar -H "Content-Type: application/json" --data-binary @corpo_f01.json | head -c 600
   ```

   Resposta: `{"relatorio_aderencia": ..., "lacunas": ...}` com `id_vaga_recomendada = "vf01"`.
2. Abrir <http://localhost:7777/relatorio/f01> (o Markdown do resultado).
3. Mostrar um erro tratado: enviar `{"curriculo": {}}` → **422** com o detalhe.

(Apague `corpo_f01.json` depois; ele não vai para o repositório.)

## 5. Agno: workflow, extrator LLM e explicador (2 min)

- `src/radar_vagas/workflow.py`: Workflow "Radar de vagas" com 5 Steps (extração → normalização → comparação → ranqueamento → consolidação). `tests/test_workflow.py` prova que dá o mesmo resultado do pipeline.
- `src/radar_vagas/extrator_llm.py`: agente com saída estruturada + **guardas em código** (trecho literal, nível escrito no texto, seção "Desejável:", dicionário), nova tentativa com os problemas e reserva por regras. 429: `retries=3` com espera exponencial.
- `src/radar_vagas/explicador.py`: agente com ferramentas que só **leem** o resultado.

**Com chave configurada** (`.env` com `MODELO_LLM` e `GROQ_API_KEY`, pacote `groq` instalado):

1. Reiniciar `radar-vagas servir`; o log não deve mais avisar "MODELO_LLM não configurado".
2. <https://os.agno.com> → *Add new OS* → *Local* → `http://localhost:7777` → *Chat* → "Explicador do radar".
3. Perguntas prontas:
   - "Resuma o resultado do f01."
   - "Por que a vaga v25 ficou abaixo da vf01?" (82 contra 80; a resposta deve citar os pontos de cada requisito)
   - "Por que a v04 tem nota 100 e não foi recomendada?" (fora dos filtros: cidade)
   - "O que a f01 deveria estudar primeiro?" (Power BI, prioridade alta)
4. Alternativa no terminal: `.venv/Scripts/radar-vagas.exe conversar --formando f01`.

## Plano B (sem internet ou sem chave)

- Tudo dos passos 2, 3 e 4 roda offline.
- Para o LLM, mostrar os testes com o modelo roteirizado, que simulam o modelo sem rede:

  ```bash
  .venv/Scripts/python.exe -m pytest -v tests/test_extrator_llm.py tests/test_explicador.py tests/test_servidor.py
  ```

  Destaques: `test_trecho_inventado_e_formacao_sao_descartados`, `test_resposta_vazia_tenta_de_novo_com_os_problemas`, `test_sem_resposta_valida_usa_as_regras`, `test_comparar_vagas_cita_as_duas_notas`.
- Mostrar a saída das ferramentas do explicador direto no Python (é exatamente o que o agente recebe):

  ```bash
  .venv/Scripts/python.exe -c "from radar_vagas.explicador import RegistroResultados, criar_ferramentas; f={x.__name__:x for x in criar_ferramentas(RegistroResultados('saidas'))}; print(f['comparar_vagas']('f01','v25','vf01'))"
  ```

## Perguntas prováveis

- *Por que não deixar o LLM dar a nota?* Reprodutível, auditável e fiel ao currículo; o verificador confere as invariantes.
- *E se o LLM inventar um requisito?* O trecho precisa existir literalmente na vaga; senão o item é descartado.
- *E o limite de requisições?* Retries do Agno com espera exponencial; depois, reserva por regras; e o cache evita chamar o modelo de novo.
