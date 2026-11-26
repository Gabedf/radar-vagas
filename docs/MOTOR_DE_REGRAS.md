# O motor de regras do radar de vagas

O radar compara o currículo de um formando com cada vaga e responde três perguntas: **quanto o formando combina com cada vaga** (nota de 0 a 100), **qual vaga recomendar** e **o que falta estudar** (lacunas).

Todas as respostas saem de **regras escritas em código**, numeradas de R1 a R8. Não há modelo de linguagem nesse cálculo. Por isso:

- a mesma entrada dá sempre o mesmo resultado (é reprodutível);
- cada número pode ser explicado passo a passo (é auditável);
- o resultado não pode inventar uma habilidade que o formando não tem (é fiel ao currículo).

O caminho dos dados é sempre o mesmo, em cinco etapas (`pipeline.py`):

```
extração -> normalização -> comparação -> ranqueamento -> consolidação
 (F2)         (F3)          (R1–R5)         (R6–R7)          (R8, F9)
```

---

## Antes do motor: extração e normalização

As 30 vagas do kit chegam com `requisitos: []`. Os requisitos estão escritos no texto da `descricao`, por exemplo:

> ... Requisitos: SQL intermediário; Python básico para tratamento de dados; Power BI intermediário; conhecimentos de estatística descritiva. Desejável: Git; noções de Apache Airflow; inglês intermediário para leitura. Benefícios: ...

O **extrator por regras** (`extrator_regras.py`) faz o seguinte:

1. Corta o texto nos marcadores. "Requisitos:", "Precisamos que você tenha:" e "O que buscamos:" abrem a parte **obrigatória**. "Desejável:", "Diferenciais:" e "Será um diferencial:" abrem a parte **desejável**. "Benefícios:", "Atividades:" e "Você vai:" fecham a seção.
2. Quebra cada seção em itens, por `;`, ou por `,` quando a frase não tem `;`.
3. Descarta os itens de formação ("Cursando ...") e de tempo de experiência ("três anos").
4. Acha as habilidades de cada item no **dicionário** (`dicionario_habilidades.yaml`). Exemplos: "PostgreSQL" vira SQL, "Redes" vira Redes de computadores e "pytest" vira Testes automatizados.
5. Lê o nível no próprio item: "noções" e "básico" dão `basico`, "intermediário" dá `intermediario`, "avançado", "sólido" e "domínio" dão `avancado`.

O **nome canônico** do dicionário é o mesmo usado nos currículos. É isso que permite comparar a vaga com o currículo.

---

## R1 — O que o formando tem

O motor monta um mapa `{habilidade canônica: (nível, nome no currículo)}` com duas fontes:

- `curriculo.habilidades`: cada uma tem `nivel` (basico, intermediario ou avancado);
- `curriculo.idiomas`: o nível `fluente` conta como `avancado`.

**As `tecnologias` de projetos e experiências não contam.** Há dois motivos:

1. Elas não têm nível. Não dá para saber se "PostgreSQL" num projeto quer dizer básico ou avançado.
2. O verificador do kit considera apenas `habilidades` e `idiomas`. Se o radar desse crédito por uma tecnologia, poderia gerar lacunas incoerentes com o que o verificador vê no currículo.

Exemplo (f01): SQL intermediário, Python intermediário, pandas intermediário, Estatística intermediário, Power BI básico, Git básico, Comunicação intermediário e Inglês intermediário. "Matplotlib" aparece só em `tecnologias`, então não entra no mapa.

## R2 — Classificação de cada requisito

O **nível pedido** é o `nivel_minimo` do requisito. Quando a vaga não diz o nível, vale `basico`.

| Situação | Classificação | Crédito |
|---|---|---|
| O formando não tem a habilidade | faltante | 0,0 |
| O formando tem, em nível maior ou igual ao pedido | atendido | 1,0 |
| O formando tem, mas em nível menor que o pedido | parcial | 0,5 |

A escala dos níveis é básico = 1, intermediário = 2 e avançado = 3, a mesma do verificador.

**Alternativas.** Quando o texto do requisito dá opções ("Python ou R para análise de dados", "React ou Vue"), vale a melhor opção que o formando tiver. Habilidades ligadas por "e" ou por vírgula ("HTML, CSS e JavaScript") são exigidas todas, e cada uma vira um requisito.

## R3 — A nota

```
peso = 2 se o requisito é obrigatório, 1 se é desejável

nota = arred( 100 × Σ(peso × crédito) / Σ peso )

arred(x) = piso(x + 0,5)      (meio para cima)
```

O obrigatório pesa o dobro porque é o que filtra os candidatos de verdade. O desejável só desempata.

O arredondamento é feito à mão porque o `round()` do Python arredonda empates "para o par": `round(42.5)` dá 42. Aqui, 42,5 vira 43.

### Exemplo resolvido: f01 × vf01 = 82

| Requisito | Tipo | Peso | Pede | Tem | Classificação | Crédito | Peso × crédito |
|---|---|---|---|---|---|---|---|
| SQL intermediário | obrigatório | 2 | intermediário | intermediário | atendido | 1,0 | 2 |
| Python básico para tratamento de dados | obrigatório | 2 | básico | intermediário | atendido | 1,0 | 2 |
| Power BI intermediário | obrigatório | 2 | intermediário | básico | **parcial** | 0,5 | 1 |
| Conhecimentos de estatística descritiva | obrigatório | 2 | básico (não indicado) | intermediário | atendido | 1,0 | 2 |
| Git | desejável | 1 | básico (não indicado) | básico | atendido | 1,0 | 1 |
| Noções de Apache Airflow | desejável | 1 | básico | — | **faltante** | 0,0 | 0 |
| Inglês intermediário para leitura | desejável | 1 | intermediário | intermediário | atendido | 1,0 | 1 |
| **Total** | | **11** | | | | | **9** |

```
nota = arred(100 × 9 / 11) = arred(81,82) = 82
```

Com a mesma regra, as outras duas vagas do exemplo do kit dão:

- vx01: SQL atendido (2), Power BI avançado parcial (1), Excel faltante (0) e DAX desejável faltante (0). Fica 3 de 7, ou 42,86, que arredonda para **43**.
- vx02: Python avançado parcial (1), Machine Learning faltante (0), SQL atendido (2) e Spark desejável faltante (0). Fica 3 de 7, que arredonda para **43**.

São exatamente as notas do arquivo `exemplos/f01/relatorio_aderencia.json`. O teste `tests/test_motor.py::test_ancora_notas_e_listas_do_exemplo_do_kit` confere isso a cada execução.

## R4 — A justificativa

A justificativa é montada por um **modelo de texto (template) em código**, usando apenas os números calculados:

> Atende a 3 de 4 requisitos obrigatórios e a 2 de 3 desejáveis. Parcial: Power BI (pede intermediário, tem básico). Falta: Apache Airflow (desejável).

Quando a vaga está fora dos filtros, o motivo é acrescentado: "Fora dos filtros do perfil: nível pleno incompatível com o pretendido (junior); por isso não pode ser recomendada."

---

## R5 — Filtros de elegibilidade

Os filtros vêm do `PerfilCarreira`: `preferencias_regime`, `preferencias_cidades` e `nivel_pretendido`. As opções `--regime`, `--cidade` e `--nivel` da linha de comando substituem o filtro correspondente. Um filtro vazio não restringe nada.

| Filtro | Regra |
|---|---|
| Regime | O regime da vaga precisa estar entre os preferidos. |
| Cidade | A comparação ignora acentos, maiúsculas e o sufixo do estado ("Vitória - ES" = "Vitória"). Uma vaga **remota** dispensa este filtro. |
| Nível | Compatibilidade pela tabela abaixo. |

| Nível pretendido | Níveis de vaga aceitos |
|---|---|
| estagio | estagio |
| trainee | trainee, junior |
| junior | junior, trainee |

A vaga fora dos filtros **continua avaliada** e aparece no ranking com a sua nota, mas **não pode ser recomendada**.

Exemplo (f01: regimes híbrido e remoto; cidades Serra e Vitória; nível júnior):

- v04 tem nota 100, mas fica em Cariacica e não é remota, então está fora;
- v03 é pleno, então está fora;
- 7 vagas são elegíveis.

## R6 — Ranking e recomendação

As vagas são ordenadas pelos critérios abaixo, um depois do outro:

1. maior nota;
2. no empate, maior fração de obrigatórios totalmente atendidos;
3. no empate, `id_vaga` em ordem alfabética, para o resultado ser sempre o mesmo.

A **recomendada** é a primeira vaga **elegível** do ranking. Se nenhuma vaga for elegível, o radar recomenda a primeira do ranking geral e avisa isso na justificativa.

## R7 — Competências mais pedidas

Para cada habilidade, o radar conta em quantas vagas do conjunto ela aparece, como obrigatória ou desejável. Cada vaga conta uma vez. A lista traz as 10 mais frequentes; no empate, vale a ordem alfabética.

## R8 — Lacunas

**Quais vagas entram.** As elegíveis. Se nenhuma for elegível, todas.

**O que é lacuna.** Uma habilidade em que o formando está abaixo do nível pedido, como parcial ou faltante, em pelo menos uma dessas vagas.

| Campo | Regra |
|---|---|
| `vagas_relacionadas` | As vagas consideradas em que a habilidade é lacuna. |
| `frequencia` | Quantas são essas vagas. |
| `obrigatoria` | Verdadeiro se é obrigatória em pelo menos uma delas. |
| `nivel_necessario` | O maior nível pedido entre elas. |
| `nivel_atual` | O nível no currículo, ou `nenhum`. |
| `habilidade` | O nome como está no currículo, quando o formando tem a habilidade; senão, o nome canônico. |

**Prioridade.** Uma lacuna é "frequente" quando aparece em pelo menos 30% das vagas consideradas **e** em pelo menos 2 vagas, porque uma vaga isolada não indica tendência.

| Prioridade | Regra |
|---|---|
| alta | É obrigatória na vaga recomendada, **ou** é uma lacuna obrigatória frequente. |
| média | É obrigatória em alguma vaga, **ou** é uma lacuna frequente (contando também as vagas em que é só desejável). |
| baixa | Todos os outros casos. |

**Ordem.** Primeiro alta, depois média, depois baixa. Dentro de cada prioridade, vêm antes as lacunas obrigatórias da vaga recomendada, depois as de maior frequência e por fim a ordem alfabética.

Exemplo (f01, as 3 vagas do exemplo do kit). Só vf01 é elegível, porque vx01 é presencial e vx02 é pleno.

- Power BI: básico, e a vaga pede intermediário. É obrigatória na recomendada, então a prioridade é **alta**.
- Apache Airflow: o formando não tem, e a vaga pede básico. É desejável e aparece numa vaga só, então a prioridade é **baixa**.

É exatamente o `exemplos/f01/lacunas.json` do kit.

**Invariantes.** Antes de gravar, o código confere as mesmas regras do verificador (`lacunas.checar_invariantes`):

- o `nivel_atual` é igual ao do currículo;
- nenhuma lacuna tem nível atual maior ou igual ao necessário.

---

## Limitações conhecidas

- **Extração por regras.**
  - Depende dos marcadores de seção e do dicionário: uma habilidade fora do dicionário não vira requisito.
  - Itens como "Disponibilidade para o turno da tarde" são ignorados e aparecem no relatório como "item sem habilidade conhecida".
- **Formação e anos de experiência** não entram na nota.
- **Parcial fixo.** O crédito parcial é sempre 0,5, seja básico contra avançado, seja intermediário contra avançado. Uma variação possível é graduar o crédito pela distância entre os níveis.
- **Tecnologias sem nível** não contam. Um formando que usou Docker num projeto, mas não o listou em `habilidades`, aparece como "faltante" em Docker.
- **Lacunas de outras áreas.** As lacunas usam todas as vagas elegíveis, inclusive as de áreas diferentes da escolhida (por exemplo, front-end para uma formanda de dados). A prioridade põe na frente o que importa para a vaga recomendada.
- **Vagas em texto.** Regime e nível são deduzidos por palavras-chave. Sem pista no texto, valem os padrões configuráveis (`presencial` e `junior`).
