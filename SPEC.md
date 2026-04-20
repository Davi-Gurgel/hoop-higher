# SPEC.md

## 1. Product Vision

**Hoop Higher** is a terminal arcade game inspired by **Higher or Lower**, using real NBA player point totals.

The core loop is simple:
- each **round** corresponds to **one NBA game**
- inside that round, the player answers **5 to 10 questions**
- each question compares the point totals of two players from that game
- the flow is continuous: player B becomes the next player A

The MVP should prioritize fast delivery, strong UX, and clear separation between UI, game logic, and data source.

---

## 2. MVP Goal

Deliver a playable TUI version with:
- a polished terminal interface
- mocked data first
- endless and arcade mode support
- a local leaderboard
- basic local stats
- SQLite persistence
- architecture ready for a real API later

---

## 3. MVP Functional Scope

### Included in the MVP
- **Endless** mode
- **Arcade** mode
- **Historical** mode with an initial mock implementation
- a single metric: **points**
- round generation per game
- 5 to 10 questions per round
- local leaderboard
- basic local stats
- local cache prepared for future real API integration
- keyboard and mouse support
- UI with boxes, panels, and light animations

### Out of scope for the MVP
- online multiplayer
- user accounts
- authentication
- server sync
- metrics beyond points
- advanced custom season selection
- social or co-op modes
- audio integration

---

## 4. Game Rules

### Main metric
In the MVP, every question is based on **points scored**.

### Player eligibility
Only players with:
- `minutes > 0`

### Round structure
- one round represents one NBA game
- each round contains **5 to 10 questions**
- all eligible players may be used

### Question structure
Example:
- Player A: Stephen Curry - 31 points
- Player B: LeBron James - ?
- Prompt: Higher or Lower?

### Classic flow
After the answer:
- player B's points are revealed
- player B becomes the new player A for the next question

---

## 5. Game Modes

### Endless
- the run continues until the user exits
- a wrong answer does **not** end the run
- a wrong answer makes the player **lose points**

### Arcade
- the run continues until the first mistake
- a wrong answer ends the match immediately

### Historical
- uses a random historical date in the configured window (default: 2010 to 2020)
- the chosen date must have at least one playable game
- MVP historical scoring is explicit: correct `+100`, wrong `-60`
- a wrong answer does **not** end the run
- the run samples up to `HOOPHIGHER_HISTORICAL_ROUNDS` playable games from that date and goes through them once each (default maximum: **5**)
- if fewer playable games are available, the number of rounds adapts to the available games
- after all sampled games are consumed, the run ends with `no_more_games`
- it may start mocked and later move to real data

### Yesterday
It may exist in the architecture from the start, but does not need to be fully wired to the real API in the first functional increment.

---

## 6. Scoring Rules

### Endless
Suggested MVP default:
- correct: `+100`
- wrong: `-60`
- streak bonuses may be added incrementally later

### Arcade
Suggested MVP default:
- correct: `+150`
- wrong: game over

### Historical
Suggested MVP default:
- correct: `+100`
- wrong: `-60`
- a wrong answer does not end the run
- the run ends when there are no more games for the selected historical date

### Note
Score values must live in centralized domain constants or configuration, never hardcoded inside UI callbacks.

---

## 7. Difficulty

Difficulty should be inferred from the point difference between player A and player B.

### Bands
- **easy**: difference `>= 10`
- **medium**: difference between `5` and `9`
- **hard**: difference between `1` and `4`

### Suggested progression
Inside a round:
- early questions tend to be easy or medium
- later questions tend to be medium or hard

### Fallback rule
If there are not enough pairs in a given band, the generator may use another available band to keep the round playable.

---

## 8. Local Persistence

The project should use SQLite to store:
- runs
- rounds
- questions
- derived leaderboard data
- basic stats
- cached games and box scores

### Minimum stats
- total runs
- total answered questions
- total correct answers
- accuracy rate
- best score
- best streak
- distribution by mode

---

## 9. Data Source

### Phase 1
Use **mocked** data to validate:
- game loop
- UX
- persistence
- leaderboard
- stats screen

### Phase 2+
Integrate a real provider, preferably behind an interface such as `StatsProvider`.

### Suggested API
- `NBAApiProvider` (`nba_api`) as the first real implementation

### Architectural rule
The UI must not depend directly on the external provider.

---

## 10. Cache

The system should be prepared to cache:
- games by date
- box score by `game_id`

### General rules
- check cache before calling the API
- persist raw or normalized responses consistently
- differentiate historical cache from recent cache
- for historical mode, persist and reuse an eligible-date index for the configured year window to avoid repeated full scans

---

## 11. UX and Interface

Desired visual identity:
- arcade terminal
- polished interface
- use of boxes and panels
- light animations
- visible keyboard shortcuts
- mouse support

### Main screen requirements
- header with score, streak, mode, and date
- main panel with the current matchup
- clickable action buttons
- side history of recent answers
- footer with hotkeys

### Navigation
- keyboard remains the primary navigation method
- mouse is additional support

---

## 12. Minimum Screen Set

- Home
- Mode Select
- Game Screen
- Round Summary
- Leaderboard
- Stats
- Settings (optional in the initial MVP)
- Quit Confirm

---

## 13. User and Local Scope

In the MVP:
- there is only **1 local user**
- there is no login
- there is no online sync

In the future, the project may evolve toward server-backed play and friend comparison, but that is out of scope for now.

---

## 14. Technical Requirements

### Language and libraries
- Python 3.13+
- Textual
- SQLite
- SQLModel
- httpx
- pytest
- pydantic-settings

### Structure
The project should follow a `src/` layout and be organized in layers:
- `tui`
- `domain`
- `services`
- `data`

---

## 15. Quality Requirements

The MVP should preserve:
- typed code
- tests for domain rules
- low coupling
- swappable providers
- simple, inspectable persistence
- responsive UI with clear loading and error states

---

## 16. Suggested Roadmap

### MVP 0
- project scaffold
- mock provider
- basic game loop
- functional scoring
- simple leaderboard

### MVP 1
- complete endless mode
- complete arcade mode
- complete persistence
- mock historical mode
- stats screen
- initial TUI polish

### MVP 2
- real API integration
- real cache
- real yesterday mode
- real historical mode

### MVP 3
- advanced visual polish
- difficulty calibration
- reproducible seeds
- daily challenge

---

## 17. MVP Success Criteria

The MVP is successful when:
- the TUI is pleasant to use
- the gameplay loop is fun with mocked data
- persistence works without friction
- the codebase is ready to swap the mock provider for a real provider without major structural rework
