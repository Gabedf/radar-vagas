# Checklist — Módulo 3: Radar de vagas

Marque cada item com `[x]` quando ele estiver pronto e escreva o nome do responsável. O GitHub mostra as caixas de marcar e o progresso do checklist.

## Fase 1 — Preparar o terreno — meta sugerida: 20/11/2026

- [ ] **Ler o enunciado geral**  
  Pronto quando: o grupo sabe as datas de 27/11 e de 11/12 e o que vai em cada entrega.  
  Responsável: 
- [ ] **Ler o caderno do módulo 3 e a ficha de contrato**  
  Pronto quando: o grupo sabe quais documentos o módulo recebe e produz.  
  Responsável: 
- [ ] **Dividir as tarefas entre os membros**  
  Pronto quando: cada item deste checklist tem um responsável.  
  Responsável: 
- [x] **Instalar o pacote de contratos do kit**  
  Pronto quando: o comando lista os 11 documentos.  
  Comando: `pip install -e caminho/do/kit/contratos && carreira-validar --listar`  
  Responsável: 
- [x] **Rodar o verificador com os exemplos do kit, a partir da pasta do kit**  
  Pronto quando: o resultado é "Aprovado".  
  Comando: `carreira-verificar radar_vagas --entrada exemplos/f01/curriculo.json exemplos/f01/conjunto_vagas.json --saida exemplos/f01/relatorio_aderencia.json exemplos/f01/lacunas.json`  
  Responsável: 
- [ ] **Criar uma conta num provedor de camada gratuita e gerar a chave (cada membro)**  
  Pronto quando: a chave está no .env de cada membro, e nunca no repositório.  
  Responsável: 
- [ ] **Executar o módulo de exemplo do kit**  
  Pronto quando: exemplo-pitch executar gera a saída e exemplo-pitch servir abre a documentação em http://localhost:7777/docs.  
  Responsável: 
- [ ] **Criar o repositório privado no GitHub e dar acesso ao professor**  
  Pronto quando: o professor aparece como colaborador do repositório.  
  Responsável: 
- [x] **Montar a estrutura do repositório a partir do módulo de exemplo**  
  Pronto quando: o repositório tem README.md, arquivo de dependências com o Agno fixado, .env.exemplo, .gitignore com .env e este CHECKLIST.md.  
  Responsável: 
- [ ] **Fazer o agente principal responder**  
  Pronto quando: o agente extrator devolve os requisitos de uma vaga em saída estruturada.  
  Responsável: 

## Fase 2 — Contrato e apresentação parcial — apresentação parcial: 27/11/2026

- [x] **Implementar o núcleo mínimo do módulo**  
  Pronto quando: o radar lê o conjunto de vagas, extrai os requisitos, calcula as notas e ordena as vagas.  
  Responsável: 
- [x] **Implementar as rotas do contrato**  
  Pronto quando: as rotas `POST /contrato/executar` funcionam na documentação em /docs.  
  Responsável: 
- [x] **Implementar a linha de comando**  
  Pronto quando: os comandos `executar` e `servir` funcionam.  
  Responsável: 
- [x] **Gerar as saídas do formando f01 e gravá-las em saidas/f01/**  
  Pronto quando: o verificador mostra "Aprovado" para os arquivos de saidas/f01/.  
  Comando: `carreira-verificar radar_vagas --entrada caminho/do/kit/exemplos/f01/curriculo.json caminho/do/kit/insumos/m3_radar_vagas/conjunto_vagas.json --saida saidas/f01/relatorio_aderencia.json saidas/f01/lacunas.json`  
  Responsável: 
- [ ] **Preparar a demonstração parcial**  
  Pronto quando: o módulo roda do início ao fim na frente de outra pessoa, sem ajustes de última hora.  
  Responsável: 
- [ ] **Apresentar no dia 27/11 e anotar as sugestões do professor**  
  Pronto quando: as sugestões estão anotadas no fim deste checklist ou como issues no GitHub.  
  Responsável: 

## Fase 3 — Funcionalidades e testes — meta sugerida: 04/12/2026

- [x] **F1. Leitura das vagas em JSON e em texto**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F2. Extração dos requisitos**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F3. Normalização das habilidades**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F4. Cálculo da aderência em código**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F5. Ranking e vaga recomendada**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F6. Filtros por regime, cidade e nível**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F7. Consolidação das lacunas**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F8. Competências mais pedidas**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [x] **F9. Relatório em Markdown**  
  Pronto quando: funciona pela linha de comando e pela interface gráfica, e aparece na tabela de funcionalidades do relatório.  
  Responsável: 
- [ ] **Conectar a interface gráfica do AgentOS**  
  Pronto quando: o painel os.agno.com ou a Agent UI permite conversar sobre o resultado.  
  Responsável: 
- [x] **Tratar o erro de limite de requisições (HTTP 429)**  
  Pronto quando: o módulo espera e tenta de novo, sem quebrar.  
  Responsável: 
- [x] **Escrever testes automatizados das partes feitas em código (cálculos, conversões, validações e rotas)**  
  Pronto quando: pytest passa, com testes que não dependem do modelo de linguagem.  
  Responsável: 
- [x] **Gerar as saídas dos formandos f02 e f03 e gravá-las em saidas/f02/ e saidas/f03/**  
  Pronto quando: o verificador mostra "Aprovado" para os três formandos.  
  Responsável: 

## Fase 4 — Avaliação, relatório e apresentação — entrega final: 11/12/2026

- [ ] **Montar pelo menos 20 casos de teste com o resultado esperado de cada um**  
  Pronto quando: os casos e os resultados esperados estão no repositório, registrados antes da execução.  
  Responsável: 
- [ ] **Executar os casos de teste e calcular as métricas do caderno**  
  Pronto quando: a tabela de resultados está preenchida no relatório.  
  Responsável: 
- [ ] **Analisar as falhas encontradas**  
  Pronto quando: a seção de análise de falhas tem exemplos concretos.  
  Responsável: 
- [ ] **Opcional, com bônus: comparar dois modelos de linguagem nos mesmos casos**  
  Pronto quando: a comparação está no relatório.  
  Responsável: 
- [ ] **Escrever o relatório a partir do modelo do kit**  
  Pronto quando: todas as seções estão preenchidas e as caixas de orientação foram apagadas.  
  Responsável: 
- [ ] **Escrever a seção sobre o uso de ferramentas de IA**  
  Pronto quando: a seção diz quais ferramentas foram usadas e como o resultado foi conferido.  
  Responsável: 
- [ ] **Compilar o relatório e gravar relatorio/relatorio.pdf no repositório**  
  Pronto quando: o PDF tem até 12 páginas, sem contar capa, sumário e referências.  
  Responsável: 
- [ ] **Preparar a apresentação de 15 minutos com demonstração**  
  Pronto quando: o grupo ensaiou e coube em 15 minutos.  
  Responsável: 
- [ ] **Garantir que todos os membros sabem explicar o código**  
  Pronto quando: cada membro explicou para o grupo uma parte que não foi ele quem escreveu.  
  Responsável: 
- [ ] **Rodar o conferidor de entrega**  
  Pronto quando: todos os itens aparecem com ✅.  
  Comando: `carreira-checar-entrega radar_vagas --kit caminho/do/kit`  
  Responsável: 
- [ ] **Enviar o último commit para o GitHub até 11/12**  
  Pronto quando: o último commit aparece no GitHub com a data correta.  
  Responsável: 

## Sugestões recebidas na apresentação parcial

- 
