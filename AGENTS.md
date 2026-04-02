# AGENTS.md

## Objetivo

Este documento define as regras operacionais e de boas práticas para agentes de código trabalhando no projeto **Hoop Higher**.

O objetivo é manter o repositório consistente, previsível e fácil de evoluir, com foco em:

- qualidade de código
- separação clara de responsabilidades
- fluxo disciplinado com issues, branches e pull requests
- baixo acoplamento
- facilidade de manutenção
- boa experiência de desenvolvimento com a stack escolhida

---

## Stack oficial

O agente deve respeitar esta stack como padrão do projeto.

### Linguagem
- **Python 3.13+**

### Interface
- **Textual** para a TUI

### Banco de dados
- **SQLite**
- **SQLModel** para modelagem e persistência

### HTTP
- **httpx**

### Testes
- **pytest**

### Configuração
- **pydantic-settings**

### Estrutura do projeto
- layout com **src/**
- organização por camadas: `tui`, `domain`, `services`, `data`

O agente não deve introduzir frameworks alternativos sem justificativa explícita e sem registrar a mudança em issue e PR.

---

## Princípios gerais

1. **Preferir clareza a esperteza.**
2. **Evitar acoplamento entre UI, regras de negócio, persistência e integração externa.**
3. **Implementar em passos pequenos e revisáveis.**
4. **Nunca alterar arquitetura central sem issue e PR próprios.**
5. **Toda feature deve ser testável.**
6. **Toda decisão que afete produto ou regra de jogo deve respeitar a especificação vigente.**
7. **Não improvisar comportamento não definido sem documentar a decisão.**

---

## Regras de arquitetura

### Separação obrigatória de camadas

#### `domain/`
Contém apenas regras de negócio e modelos do domínio.

Exemplos:
- enums de modo de jogo
- modelos de run, round, question
- regras de score
- heurísticas de dificuldade
- gerador de perguntas

**Não pode conter:**
- código de Textual
- SQLModel de persistência
- chamadas HTTP
- leitura de `.env`

#### `services/`
Orquestra casos de uso.

Exemplos:
- iniciar run
- jogar round
- carregar jogo histórico
- calcular estatísticas agregadas

**Pode usar:** domínio + repositórios + providers

**Não deve conter:** widgets, estilos visuais ou detalhes específicos de renderização.

#### `data/`
Acesso a banco, cache e APIs externas.

Exemplos:
- `BallDontLieProvider`
- `MockProvider`
- repositórios SQLite
- mapeamento de payload externo para modelos internos

**Não deve conter:** regra de jogo de alto nível.

#### `tui/`
Tudo relacionado à interface em Textual.

Exemplos:
- screens
- widgets
- estilos `.tcss`
- navegação
- atalhos de teclado
- manipulação de mouse

**Não deve conter:**
- regras de score implementadas inline
- SQL direto
- parsing de API

---

## Regras de implementação

### 1. Tipagem
O agente deve usar type hints em todo código novo relevante.

### 2. Funções pequenas
Preferir funções curtas, com responsabilidade única.

### 3. Nomes claros
Usar nomes descritivos e previsíveis.

### 4. Sem constantes mágicas espalhadas
Valores de score, thresholds de dificuldade, limites de perguntas e TTL de cache devem ficar centralizados.

### 5. Sem lógica duplicada
Se o comportamento for reutilizável, extrair para serviço, helper ou regra de domínio.

### 6. Comentários só quando necessários
Não comentar o óbvio. Usar comentários para:
- explicar decisão não trivial
- registrar trade-off
- justificar workaround técnico

### 7. Erros explícitos
Falhas devem ser tratadas com mensagens claras. Não engolir exceções silenciosamente.

### 8. Evolução incremental
O agente deve preferir PRs pequenos e funcionais em vez de mudanças massivas.

---

## Regras específicas da stack

### Python
- seguir PEP 8
- usar `pathlib` quando fizer sentido
- preferir modelos explícitos e funções puras
- evitar classes desnecessárias

### Textual
- separar screens e widgets reutilizáveis
- evitar colocar lógica de domínio dentro de callbacks de UI
- manter atalhos de teclado centralizados e visíveis na interface
- mouse é complemento, não dependência
- feedback visual deve ser previsível: loading, success, error, reveal

### SQLite / SQLModel
- manter schema simples
- evitar otimizações prematuras
- usar bootstrap limpo do banco no início
- persistir dados em formato previsível e fácil de inspecionar
- garantir integridade mínima entre tabelas ligadas por IDs

### httpx
- encapsular chamadas em providers dedicados
- usar timeout explícito
- tratar erros de rede e resposta inválida
- nunca espalhar chamadas HTTP diretamente pela UI

### pytest
- todo módulo de domínio novo deve vir com testes
- testar regra, não implementação acidental
- evitar testes frágeis de UI quando uma camada inferior cobre a regra principal

---

## Regras para dados de jogo

### Fonte mock primeiro
O agente deve começar por **MockProvider** para validar UX, fluxo de jogo e persistência.

### API real depois
A integração real deve ser implementada atrás de uma interface estável, por exemplo `StatsProvider`.

### Cache obrigatório
Sempre que houver integração com API real:
- checar cache antes de requisitar
- persistir payload bruto ou normalizado conforme definido
- diferenciar cache por data e por jogo

---

## Regras para o jogo

O agente não deve alterar estas regras sem issue específica:

- métrica principal do MVP: **points**
- cada round corresponde a **um jogo**
- cada round contém **5 a 10 perguntas**
- usar jogadores com **minutes > 0**
- fluxo clássico: jogador B vira o próximo A
- modo endless: erro continua a run e remove pontos
- modo arcade: erro encerra a run
- modo histórico: data aleatória com pelo menos **5 jogos**
- leaderboard local
- 1 usuário local
- persistência em SQLite

Se houver necessidade de mudar regra, isso deve aparecer em:
1. issue
2. branch dedicada
3. PR com justificativa

---

## Fluxo obrigatório com Issues, Branches e PRs usando gh cli

### 1. Criar issue antes de implementar
Toda mudança relevante deve nascer de uma issue.

A issue deve conter:
- título claro
- contexto
- objetivo
- escopo
- critérios de aceite
- fora de escopo, se necessário

### 2. Criar branch a partir da issue
Padrão de branch:

```text
feat/<issue-id>-descricao-curta
fix/<issue-id>-descricao-curta
refactor/<issue-id>-descricao-curta
chore/<issue-id>-descricao-curta
```

Exemplos:
- `feat/12-home-screen`
- `feat/18-mock-provider`
- `fix/27-score-bug-endless`
- `refactor/31-split-round-generator`

### 3. Implementar escopo pequeno
Uma branch deve resolver **uma unidade lógica de trabalho**.

### 4. Abrir PR obrigatoriamente
Toda branch deve virar PR antes de merge.

A PR deve conter:
- o que foi feito
- por que foi feito
- como validar
- riscos ou trade-offs
- referência à issue

### 5. Só fazer merge quando estiver revisável
Condições mínimas para merge:
- testes passando
- escopo compatível com a issue
- sem código morto óbvio
- sem TODO crítico escondido

---

## Estratégia de backlog recomendada

1. scaffold do projeto
2. modelos de domínio e enums
3. motor de score
4. gerador de perguntas
5. mock provider
6. persistência SQLite
7. tela home
8. tela de jogo
9. leaderboard
10. stats screen
11. histórico mock
12. integração API real
13. cache real
14. polimento visual

---

## Convenções de commit

Preferir commits pequenos e com mensagem clara.

```text
feat: add mock provider for local game data
fix: correct endless mode score penalty
refactor: split score logic from game screen
test: add coverage for difficulty selection
chore: configure project dependencies
```

Evitar commits como:
- `update`
- `fix stuff`
- `wip`
- `misc`

---

## O que o agente pode decidir sozinho

- nomes internos de classes e funções
- organização fina entre arquivos
- helpers utilitários
- estrutura de testes
- detalhes visuais pequenos da TUI
- mensagens de erro e loading
- pequenas abstrações técnicas

## O que o agente não deve decidir sozinho

Sem issue específica ou autorização explícita, o agente não deve:
- trocar a stack principal
- trocar Textual por outro framework
- mudar a regra central do jogo
- adicionar multiplayer online
- alterar persistência local para outro banco
- adicionar autenticação
- misturar provider real e UI de forma acoplada
- expandir escopo para métricas além de pontos no MVP

---

## Definition of Done por PR

Uma PR só está pronta quando:
- resolve uma issue claramente definida
- mantém a arquitetura em camadas
- inclui testes apropriados
- não adiciona dívida técnica desnecessária
- deixa o projeto em estado executável
- atualiza documentação se necessário

---

## Regra de ouro

**O agente deve otimizar por organização, previsibilidade e entregas pequenas.**

É melhor abrir várias issues e PRs curtas e limpas do que uma implementação grande, acoplada e difícil de revisar.

---

## Documentos relacionados

Além deste arquivo, o repositório deve manter:
- `SPEC.md`
- `ARCHITECTURE.md`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/feature.md`
- `.github/ISSUE_TEMPLATE/bug.md`

Se houver conflito entre este documento e a especificação do produto, a especificação do produto prevalece.
