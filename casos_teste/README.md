# Casos de teste do radar de vagas

Esta pasta guarda os casos de teste da avaliação do módulo (Fase 4 do checklist). A regra é: **o resultado esperado de cada caso é escrito ANTES de executar o módulo**, para a comparação ser honesta.

Serão registrados pelo menos 20 casos, divididos em três grupos:

| Grupo | O que mede | Métrica |
|---|---|---|
| Extração (F2) | Requisitos que um humano anotou numa vaga x requisitos extraídos | precisão e revocação por habilidade; acerto de obrigatório/desejável e de nível |
| Ranking (F4–F6) | Ordem das vagas que o grupo espera para um formando x ranking do módulo | acerto da vaga recomendada; concordância das 5 primeiras |
| Lacunas (F7) | Lacunas e prioridades esperadas x lacunas produzidas | acerto das lacunas de prioridade alta |

Arquivos (a preencher):

- `extracao/` — um arquivo por vaga anotada, com os requisitos esperados;
- `ranking_esperado.md` — ranking esperado de cada formando, escrito à mão;
- `resultados.md` — a tabela de resultados depois da execução.

Já existem testes automatizados com resultado conhecido em `tests/` (por exemplo, o teste-âncora que reproduz as notas 82/43/43 do exemplo do kit e a comparação com as vagas estruturadas de `exemplos/f02` e `exemplos/f03`).
