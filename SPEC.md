# SPEC.md

## 1. Visão do produto

**Hoop Higher** é um jogo em terminal estilo arcade baseado em **Higher or Lower** usando dados reais de jogadores da NBA.

A proposta central é simples:
- cada **round** corresponde a **um jogo** da NBA
- dentro desse round, o jogador responde entre **5 e 10 perguntas**
- cada pergunta compara a pontuação de dois jogadores que atuaram naquela partida
- o fluxo é contínuo: o jogador B vira o próximo jogador A

O MVP deve priorizar velocidade de construção, qualidade de UX e desacoplamento entre interface, lógica do jogo e fonte de dados.

---

## 2. Objetivo do MVP

Entregar uma versão jogável em TUI com:
- interface refinada em terminal
- dados mockados no início
- suporte a modo endless e arcade
- leaderboard local
- estatísticas básicas locais
- persistência em SQLite
- arquitetura pronta para integrar uma API real depois

---

## 3. Escopo funcional do MVP

### Incluído no MVP
- modo **Endless**
- modo **Arcade**
- modo **Historical** com mock inicial
- métrica única: **points**
- geração de rounds por jogo
- 5 a 10 perguntas por round
- leaderboard local
- estatísticas básicas locais
- cache local preparado para integração futura com API real
- suporte a teclado e mouse
- interface com boxes, painéis e animações leves

### Fora de escopo do MVP
- multiplayer online
- contas de usuário
- autenticação
- sincronização com servidor
- métricas além de points
- temporadas customizáveis avançadas
- modos sociais ou coop
- integração com áudio

---

## 4. Regras do jogo

### Métrica principal
No MVP, todas as perguntas são baseadas em **pontos marcados**.

### Elegibilidade de jogadores
Participam apenas jogadores com:
- `minutes > 0`

### Estrutura de round
- um round representa um jogo da NBA
- cada round contém entre **5 e 10 perguntas**
- todos os jogadores elegíveis podem ser usados

### Estrutura da pergunta
Exemplo:
- Jogador A: Stephen Curry — 31 pontos
- Jogador B: LeBron James — ?
- Pergunta: Higher or Lower?

### Fluxo clássico
Após a resposta:
- os pontos do jogador B são revelados
- o jogador B passa a ser o novo jogador A da pergunta seguinte

---

## 5. Modos de jogo

### Endless
- a run continua indefinidamente até o usuário sair
- erro **não encerra** a run
- erro faz o jogador **perder pontos**

### Arcade
- a run continua até o primeiro erro
- erro encerra imediatamente a partida

### Historical
- usa uma data aleatória do passado
- a data escolhida precisa ter **pelo menos 5 jogos**
- no início pode ser mockado; depois será integrado a dados reais

### Yesterday
Pode existir no desenho da arquitetura desde o início, mas não precisa estar completamente integrado à API real no primeiro incremento funcional.

---

## 6. Regras de pontuação

### Endless
Sugestão padrão do MVP:
- acerto: `+100`
- erro: `-60`
- bônus por streak podem ser adicionados de forma incremental

### Arcade
Sugestão padrão do MVP:
- acerto: `+150`
- erro: game over

### Observação
Os valores de score devem ficar centralizados em constantes ou configuração de domínio, nunca hardcoded em callbacks de UI.

---

## 7. Dificuldade

A dificuldade deve ser inferida pela diferença de pontos entre o jogador A e o jogador B.

### Faixas
- **easy**: diferença `>= 10`
- **medium**: diferença entre `5` e `9`
- **hard**: diferença entre `1` e `4`

### Progressão sugerida
Dentro do round:
- primeiras perguntas tendem a easy/medium
- últimas perguntas tendem a medium/hard

### Regra de fallback
Se não houver pares suficientes em uma faixa, o gerador pode usar outra faixa disponível para manter o round jogável.

---

## 8. Persistência local

O projeto deve usar SQLite para salvar:
- runs
- rounds
- questions
- leaderboard derivado
- estatísticas básicas
- cache de jogos e box scores

### Estatísticas mínimas
- total de runs
- total de perguntas respondidas
- total de acertos
- percentual de acerto
- melhor score
- melhor streak
- distribuição por modo

---

## 9. Fonte de dados

### Fase 1
Dados **mockados** para validar:
- loop de jogo
- UX
- persistência
- ranking
- tela de stats

### Fase 2+
Integração com provider real, preferencialmente atrás de uma interface como `StatsProvider`.

### API sugerida
- `BallDontLieProvider` como primeira implementação real

### Regra arquitetural
A UI não pode depender diretamente do provider externo.

---

## 10. Cache

O sistema deve ser preparado para cachear:
- jogos por data
- box score por game_id

### Regras gerais
- checar cache antes de bater na API
- persistir resposta bruta ou normalizada de forma consistente
- diferenciar cache histórico de cache recente

---

## 11. UX e interface

A identidade visual desejada é:
- arcade terminal
- interface refinada
- uso de boxes e painéis
- animações leves
- atalhos de teclado visíveis
- suporte a mouse

### Requisitos da tela principal
- header com score, streak, modo e data
- painel principal com matchup atual
- botões de ação clicáveis
- histórico lateral das últimas respostas
- footer com hotkeys

### Navegação
- teclado continua sendo a navegação primária
- mouse é suporte adicional

---

## 12. Estrutura mínima de telas

- Home
- Mode Select
- Game Screen
- Round Summary
- Leaderboard
- Stats
- Settings (opcional no MVP inicial)
- Quit Confirm

---

## 13. Usuário e escopo local

No MVP:
- existe apenas **1 usuário local**
- não há login
- não há sincronização online

No futuro, o projeto pode evoluir para servidor e comparação com amigos, mas isso está fora do escopo atual.

---

## 14. Requisitos técnicos

### Linguagem e libs
- Python 3.13+
- Textual
- SQLite
- SQLModel
- httpx
- pytest
- pydantic-settings

### Estrutura
O projeto deve seguir layout com `src/` e ser organizado por camadas:
- `tui`
- `domain`
- `services`
- `data`

---

## 15. Requisitos de qualidade

O MVP deve preservar:
- código tipado
- testes para regras de domínio
- baixo acoplamento
- providers trocáveis
- persistência simples de inspecionar
- interface responsiva com estados de loading e erro claros

---

## 16. Roadmap sugerido

### MVP 0
- scaffold do projeto
- provider mock
- game loop básico
- score funcional
- leaderboard simples

### MVP 1
- endless completo
- arcade completo
- persistence completa
- historical mock
- stats screen
- polimento inicial da TUI

### MVP 2
- integração API real
- cache real
- yesterday mode real
- histórico real

### MVP 3
- polimento visual avançado
- calibração de dificuldade
- seeds reproduzíveis
- daily challenge

---

## 17. Critério de sucesso do MVP

O MVP é considerado bem-sucedido quando:
- a TUI é agradável de usar
- o loop de jogo é divertido com dados mockados
- a persistência funciona sem fricção
- o código está pronto para trocar mock por provider real sem retrabalho estrutural grande
