#import "modelo_ifes.typ": report, box-info, box-tip, box-warning, styled-table

#let figuras-prontas = false
#let provisoria(rotulo) = rect(width: 100%, height: 5cm, stroke: (dash: "dashed", paint: luma(150)), align(center + horizon, text(fill: luma(120))[Figura provisória: #rotulo]))

#show: report.with(
  title: "Ecossistema de Agentes: Módulo N — Nome do módulo",
  subtitle: "Relatório do trabalho prático",
  author: ("Aluno A", "Aluno B", "Aluno C"),
  cover-authors: [Nome Completo do Aluno A (matrícula) \ Nome Completo do Aluno B (matrícula) \ Nome Completo do Aluno C (matrícula)],
  professor: "Dr. Sérgio Nery Simões",
  course: "Inteligência Artificial",
)

= Como usar este modelo

#box-info(title: "Orientações gerais")[
  - Preencham a capa no início deste arquivo: `title` com o número e o nome do módulo, `author` com os nomes curtos (usados no cabeçalho) e `cover-authors` com os nomes completos e as matrículas.
  - O relatório tem no máximo 12 páginas, sem contar capa, sumário e referências.
  - Cada seção traz caixas com o que deve ser escrito. Apaguem as caixas à medida que escreverem e apaguem esta seção ao final.
  - As figuras aparecem como retângulos provisórios enquanto `figuras-prontas` for `false`; coloquem as imagens na pasta `figuras/` e troquem para `true`.
  - Para citar, escrevam `@` seguido da chave da obra em `referencias.bib`, por exemplo `@russell2022` ou `@agno`. A lista de referências é montada automaticamente apenas com as obras citadas no texto. Toda referência precisa corresponder a uma obra real, consultada pelo grupo.
]

= Introdução

#box-info(title: "O que escrever")[
  - O objetivo do módulo e o problema do formando que ele resolve.
  - O lugar do módulo no ecossistema: de quais documentos ele depende e quem usa as suas saídas.
  - Um resumo do que foi implementado e dos principais resultados da avaliação.
]

= Arquitetura do módulo

#box-info(title: "O que escrever")[
  - Os agentes, times e workflows do Agno usados, o papel de cada um e como eles se comunicam.
  - As tools escritas pelo grupo, a base de conhecimento, a memória e os guardrails, e por que foram escolhidos.
  - O que é feito por código determinístico e o que é feito pelo modelo de linguagem.
  - Um diagrama da arquitetura (Figura 1).
]

#figure(
  if figuras-prontas { image("figuras/arquitetura.png", width: 100%) } else { provisoria("arquitetura do módulo") },
  caption: [Arquitetura do módulo.],
) <fig-arquitetura>

#figure(
  kind: table,
  styled-table(
    col-widths: (auto, 1fr, 1fr, auto),
    headers: ([Agente], [Papel], [Tools e recursos], [Saída estruturada]),
    rows: (
      ([...], [...], [...], [...]),
      ([...], [...], [...], [...]),
    ),
  ),
  caption: [Agentes do módulo.],
) <tab-agentes>

= Contrato de entradas e saídas

#box-info(title: "O que escrever")[
  - Os documentos de entrada e de saída do módulo, conforme a ficha de contrato.
  - Como o módulo garante que as saídas obedecem ao contrato (validação antes de gravar, testes).
  - O resultado do `carreira-validar` e do `carreira-verificar` para os três formandos do kit.
]

#figure(
  kind: table,
  styled-table(
    col-widths: (auto, 1fr, auto, auto),
    headers: ([Formando], [Arquivos de entrada], [Validador], [Verificador]),
    rows: (
      ([f01], [...], [...], [...]),
      ([f02], [...], [...], [...]),
      ([f03], [...], [...], [...]),
    ),
  ),
  caption: [Conformidade das saídas com o contrato.],
) <tab-contrato>

= Funcionalidades implementadas

#box-info(title: "O que escrever")[
  Listem todas as funcionalidades da especificação do módulo (F1, F2, ...) com a situação de cada uma: completa, parcial ou não implementada. Para as parciais e as não implementadas, expliquem o que falta.
]

#figure(
  kind: table,
  styled-table(
    col-widths: (auto, 1fr, auto, 1fr),
    headers: ([Nº], [Funcionalidade], [Situação], [Observação]),
    rows: (
      ([F1], [...], [...], [...]),
      ([F2], [...], [...], [...]),
    ),
  ),
  caption: [Situação das funcionalidades.],
) <tab-funcionalidades>

= Avaliação experimental

#box-info(title: "O que escrever")[
  - Como os casos de teste foram construídos (insumos do kit e casos próprios) e como o resultado esperado de cada caso foi definido antes da execução.
  - As métricas usadas, com a definição de cada uma.
  - Os resultados, em tabela, e a sua interpretação.
  - Os modelos de linguagem usados (provedor e nome do modelo) e as condições de execução.
  - Opcionalmente, com bônus: a comparação dos resultados com dois modelos de linguagem diferentes, nos mesmos casos de teste.
]

#box-warning(title: "Erros comuns")[
  - Definir o resultado esperado depois de ver a saída do sistema.
  - Apresentar números sem dizer como foram calculados.
  - Relatar apenas os casos que deram certo.
]

#figure(
  kind: table,
  styled-table(
    col-widths: (1fr, auto, auto),
    headers: ([Métrica], [Casos], [Resultado]),
    rows: (
      ([...], [...], [...]),
      ([...], [...], [...]),
    ),
  ),
  caption: [Resultados da avaliação experimental.],
) <tab-resultados>

= Análise de falhas

#box-info(title: "O que escrever")[
  Descrevam os principais tipos de falha observados (por exemplo, alucinações, chamadas de tools incorretas, saídas fora do contrato, respostas incoerentes com o estado), com exemplos concretos, as causas prováveis e o que foi feito ou poderia ser feito para corrigi-las.
]

= Uso de ferramentas de IA no desenvolvimento

#box-info(title: "O que escrever")[
  Indiquem quais assistentes de IA o grupo usou, em que partes do trabalho e como o resultado foi conferido.
]

= Conclusão

#box-info(title: "O que escrever")[
  - O que o módulo faz bem e quais são as suas limitações.
  - O que o grupo aprendeu sobre o desenvolvimento de sistemas com agentes.
  - Melhorias e trabalhos futuros.
]

#bibliography("referencias.bib", style: "associacao-brasileira-de-normas-tecnicas", title: "Referências")
