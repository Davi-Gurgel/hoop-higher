# ARCHITECTURE.md

## 1. Objetivo

Este documento descreve a arquitetura técnica do projeto **Hoop Higher**.

A prioridade é:
- desacoplamento entre UI, domínio, persistência e integrações externas
- facilidade de iteração por agentes de código
- suporte a dados mockados e provider real sem reescrever a aplicação
- base sólida para evoluir o jogo sem gerar dívida técnica cedo demais

---

## 2. Princípios arquiteturais

1. **UI não contém regra de negócio.**
2. **Domínio não conhece Textual, SQLite nem APIs externas.**
3. **Integrações externas entram por interfaces claras.**
4. **Persistência deve ser simples, explícita e local.**
5. **Cada camada deve poder ser testada isoladamente.**

---

## 3. Visão de camadas

```text
TUI (Textual screens/widgets)
        ↓
Services (casos de uso/orquestração)
        ↓
Domain (regras do jogo)
        ↓
Data (repositories, providers, cache)
```

### Dependências permitidas
- `tui -> services`
- `services -> domain`
- `services -> data`
- `data -> domain` apenas para mapear payloads em modelos internos

### Dependências proibidas
- `domain -> tui`
- `domain -> data`
- `tui -> sqlite direto`
- `tui -> api provider direto`

---

## 4. Estrutura de diretórios proposta

```text
src/
└── hoophigher/
    ├── main.py
    ├── app.py
    ├── config.py
    ├── tui/
    │   ├── screens/
    │   ├── widgets/
    │   └── styles.tcss
    ├── domain/
    │   ├── enums.py
    │   ├── models.py
    │   ├── scoring.py
    │   ├── difficulty.py
    │   ├── round_generator.py
    │   └── game_session.py
    ├── services/
    │   ├── play_endless.py
    │   ├── play_arcade.py
    │   ├── play_historical.py
    │   └── stats_service.py
    ├── data/
    │   ├── db.py
    │   ├── schema.py
    │   ├── repositories/
    │   ├── cache_repository.py
    │   └── api/
    │       ├── base.py
    │       ├── mock_provider.py
    │       └── balldontlie_provider.py
    └── utils/
```

---

## 5. Camada de domínio

## Responsabilidades
- representar os conceitos do jogo
- conter as regras centrais
- encapsular score, dificuldade e geração de perguntas

## Componentes esperados

### `enums.py`
- `GameMode`
- `Difficulty`
- `GuessDirection`
- `RunEndReason`

### `models.py`
Modelos puros do domínio, por exemplo:
- `PlayerLine`
- `GameBoxScore`
- `Question`
- `RoundDefinition`
- `RunState`

### `scoring.py`
Funções como:
- `calculate_endless_score_delta(...)`
- `calculate_arcade_score_delta(...)`

### `difficulty.py`
Funções como:
- `classify_question_difficulty(points_a, points_b)`
- `pick_target_difficulty(question_index, total_questions)`

### `round_generator.py`
Responsável por:
- filtrar jogadores elegíveis
- gerar 5 a 10 perguntas
- aplicar fallback de dificuldade
- evitar pares inválidos ou repetição excessiva

## Restrições
O domínio não deve:
- abrir conexão com banco
- fazer request HTTP
- renderizar widgets
- ler variáveis de ambiente

---

## 6. Camada de serviços

## Responsabilidades
- orquestrar casos de uso
- coordenar providers, repositories e regras de domínio
- preparar dados para consumo da UI

## Serviços sugeridos

### `play_endless.py`
- iniciar run endless
- carregar próximo round
- aplicar resposta
- persistir progresso

### `play_arcade.py`
- iniciar run arcade
- encerrar no primeiro erro

### `play_historical.py`
- selecionar data elegível
- carregar jogos da data
- escolher jogo para round

### `stats_service.py`
- calcular estatísticas agregadas
- fornecer leaderboard

## Regra
A camada de serviço pode depender de:
- domínio
- repositórios
- providers

Mas não deve conhecer detalhes de widget ou layout Textual.

---

## 7. Camada de dados

## Responsabilidades
- acesso a SQLite
- cache local
- integração com APIs externas
- mapeamento entre payload bruto e modelos internos

## Subdivisão

### `db.py`
- engine SQLite
- sessão
- bootstrap do banco

### `schema.py`
Modelos SQLModel:
- `RunRecord`
- `RoundRecord`
- `QuestionRecord`
- `CachedGameRecord`
- `CachedGameStatsRecord`

### `repositories/`
Repositórios para leitura e gravação:
- `RunRepository`
- `StatsRepository`
- `CacheRepository`

### `api/base.py`
Interface do provider, por exemplo:

```python
class StatsProvider(Protocol):
    async def get_games_by_date(self, date: str) -> list[GameBoxScore]:
        ...

    async def get_game_boxscore(self, game_id: str) -> GameBoxScore:
        ...
```

### `api/mock_provider.py`
- entrega dados fixos/mockados
- deve ser a fonte inicial do projeto

### `api/balldontlie_provider.py`
- provider real futuro
- usa `httpx`
- respeita cache
- converte payload externo em modelos internos

---

## 8. Camada de TUI

## Responsabilidades
- renderizar telas e widgets
- capturar input do usuário
- despachar ações para serviços
- exibir estados de loading, error e success

## Estrutura sugerida

### `screens/`
- `home.py`
- `game.py`
- `leaderboard.py`
- `stats.py`
- `results.py`
- `settings.py`

### `widgets/`
- `score_panel.py`
- `matchup_card.py`
- `history_panel.py`
- `key_hints.py`
- `animated_reveal.py`

### `styles.tcss`
- tema visual
- bordas, layout, spacing, estados visuais

## Regra importante
A tela não calcula score nem gera perguntas sozinha. Ela apenas consome estado produzido por serviços/domínio.

---

## 9. Fluxo de dados do jogo

### Fluxo de inicialização
1. app inicia
2. banco é bootstrapado
3. configuração é carregada
4. TUI abre a Home Screen

### Fluxo de uma run
1. usuário escolhe modo
2. screen aciona serviço de início de run
3. serviço obtém jogo elegível via provider/repositório
4. round generator monta perguntas
5. estado é devolvido para a UI
6. usuário responde
7. UI chama serviço para aplicar resposta
8. serviço usa scoring + persistência
9. UI atualiza score, streak e histórico
10. ao fim do round, carrega próximo round

---

## 10. Fluxo de dados com cache

### Jogos por data
1. serviço pede jogos da data ao provider
2. provider consulta `CacheRepository`
3. se cache válido existir, retorna cache
4. se não existir, consulta API
5. salva resultado em cache
6. retorna modelos de domínio

### Box score por jogo
1. serviço pede box score por `game_id`
2. provider consulta cache local
3. em caso de miss, chama API
4. persiste payload
5. retorna `GameBoxScore`

---

## 11. Modelo de persistência

## Tabelas principais

### `runs`
Armazena a run como unidade agregada:
- modo
- data fonte
- score final
- acertos
- erros
- streak máxima
- motivo de encerramento

### `rounds`
Armazena cada jogo usado dentro da run:
- `run_id`
- `game_id`
- times
- total de perguntas
- acertos e erros no round
- score do round

### `questions`
Armazena cada comparação individual:
- jogador A
- jogador B
- pontos de ambos
- palpite
- acerto
- dificuldade
- tempo de resposta

### `cache_games`
Armazena jogos por data ou metadados relevantes.

### `cache_game_stats`
Armazena box score detalhado por jogo.

---

## 12. Testabilidade

## O que deve ser testado no domínio
- score
- classificação de dificuldade
- geração de perguntas
- regras de fallback
- encerramento de run arcade

## O que deve ser testado em dados
- repositories
- bootstrap do banco
- mapping de payload externo
- comportamento de cache hit/miss

## O que deve ser testado na UI
- smoke tests de telas principais
- navegação básica
- renderização de estados críticos

---

## 13. Estratégia de evolução

### Fase 1
- MockProvider
- UI funcional
- SQLite funcional
- loop jogável

### Fase 2
- provider real
- cache real
- historical real
- yesterday real

### Fase 3
- calibração de UX
- melhorias visuais
- daily challenge
- seeds reproduzíveis

---

## 14. Decisões técnicas intencionais

### Por que Python + Textual
- alta velocidade de iteração
- boa experiência para agentes de código
- TUI sofisticada sem custo excessivo de infraestrutura

### Por que SQLite
- excelente para single-user local
- simples de inspecionar e manter
- suficiente para leaderboard e cache no MVP

### Por que provider isolado
- mock e API real podem coexistir
- reduz retrabalho
- facilita testes

---

## 15. Anti-padrões proibidos

- lógica de score dentro de event handler da TUI
- SQL inline em screen/widget
- chamada HTTP dentro de widget
- dependência circular entre camadas
- regras do jogo espalhadas em vários arquivos sem centralização
- valores mágicos repetidos no código

---

## 16. Critério de arquitetura saudável

A arquitetura está saudável quando:
- trocar mock por provider real não exige reescrever a UI
- ajustes de score não exigem mexer em widgets
- leaderboard e stats podem ser recalculados pelo banco
- testes de domínio rodam sem subir a TUI
- o projeto cresce por camadas, não por acoplamento lateral
