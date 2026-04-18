# AGENTS.md

## Purpose

This document defines the operating rules and engineering practices for code agents working on **Hoop Higher**.

The goal is to keep the repository consistent, predictable, and easy to evolve, with focus on:

- code quality
- clear separation of responsibilities
- disciplined issue, branch, and pull request flow
- low coupling
- maintainability
- a good developer experience with the chosen stack

---

## Official Stack

Agents should treat this stack as the project default.

### Language
- **Python 3.13+**

### Interface
- **Textual** for the TUI

### Database
- **SQLite**
- **SQLModel** for modeling and persistence

### HTTP
- **httpx**

### Tests
- **pytest**

### Configuration
- **pydantic-settings**

### Project structure
- `src/` layout
- layered organization: `tui`, `domain`, `services`, `data`

Agents must not introduce alternative frameworks without explicit justification and a documented issue and PR.

---

## General Principles

1. **Prefer clarity over cleverness.**
2. **Avoid coupling UI, business rules, persistence, and external integrations.**
3. **Implement in small, reviewable steps.**
4. **Never change core architecture without a dedicated issue and PR.**
5. **Every feature must be testable.**
6. **Any decision affecting product behavior or game rules must respect the current specification.**
7. **Do not invent undefined behavior without documenting the decision.**

---

## Architecture Rules

### Required layer separation

#### `domain/`
Contains only business rules and domain models.

Examples:
- game mode enums
- run, round, and question models
- scoring rules
- difficulty heuristics
- question generation

Must not contain:
- Textual code
- SQLModel persistence models
- HTTP calls
- `.env` loading

#### `services/`
Orchestrates use cases.

Examples:
- start a run
- play a round
- load a historical game
- calculate aggregated stats

May use: domain + repositories + providers

Must not contain: widgets, visual styles, or rendering-specific details.

#### `data/`
Database, cache, and external API access.

Examples:
- `BallDontLieProvider`
- `MockProvider`
- SQLite repositories
- external payload mapping into internal models

Must not contain: high-level game rules.

#### `tui/`
Everything related to the Textual interface.

Examples:
- screens
- widgets
- `.tcss` styles
- navigation
- keyboard shortcuts
- mouse handling

Must not contain:
- inline scoring rules
- direct SQL
- API parsing

---

## Implementation Rules

### 1. Typing
Agents must use type hints in all relevant new code.

### 2. Small functions
Prefer short functions with a single responsibility.

### 3. Clear names
Use descriptive and predictable names.

### 4. No scattered magic constants
Scoring values, difficulty thresholds, question limits, and cache TTL values must be centralized.

### 5. No duplicated logic
If behavior is reusable, extract it into a service, helper, or domain rule.

### 6. Comments only when needed
Do not comment the obvious. Use comments to:
- explain a non-trivial decision
- record a trade-off
- justify a technical workaround

### 7. Explicit errors
Failures should be handled with clear messages. Do not silently swallow exceptions.

### 8. Incremental evolution
Agents should prefer small, functional PRs instead of large, sweeping changes.

---

## Stack-Specific Rules

### Python
- follow PEP 8
- use `pathlib` where it makes sense
- prefer explicit models and pure functions
- avoid unnecessary classes

### Textual
- separate reusable screens and widgets
- avoid putting domain logic inside UI callbacks
- keep keyboard shortcuts centralized and visible
- treat mouse support as complementary, not required
- visual feedback should be predictable: loading, success, error, reveal

### SQLite / SQLModel
- keep the schema simple
- avoid premature optimization
- use clean DB bootstrap on startup
- persist data in a predictable, easy-to-inspect format
- maintain minimum integrity between tables linked by IDs

### httpx
- wrap HTTP calls in dedicated providers
- use explicit timeouts
- handle network failures and invalid responses
- never spread HTTP calls directly across the UI

### pytest
- every new domain module should ship with tests
- test the rule, not accidental implementation details
- avoid fragile UI tests when a lower layer already covers the core rule

---

## Game Data Rules

### Mock source first
Agents should start with **MockProvider** to validate UX, gameplay flow, and persistence.

### Real API later
The real integration should be implemented behind a stable interface such as `StatsProvider`.

### Required cache
Whenever a real API integration exists:
- check cache before making the request
- persist raw or normalized payloads as defined
- differentiate cache by date and by game

---

## Game Rules

Agents must not change these rules without a dedicated issue:

- MVP main metric: **points**
- each round corresponds to **one game**
- each round contains **5 to 10 questions**
- use players with **minutes > 0**
- classic flow: player B becomes the next player A
- endless mode: a wrong answer continues the run and removes points
- arcade mode: a wrong answer ends the run
- historical mode: random date with at least **5 games**
- local leaderboard
- 1 local user
- SQLite persistence

If a rule needs to change, it must appear in:
1. an issue
2. a dedicated branch
3. a PR with justification

---

## Required Issue, Branch, and PR Flow Using `gh`

### 1. Create an issue before implementing
Every relevant change should start from an issue.

The issue should contain:
- a clear title
- context
- objective
- scope
- acceptance criteria
- out-of-scope notes when needed

### 2. Create a branch from the issue
Branch naming convention:

```text
feat/<issue-id>-short-description
fix/<issue-id>-short-description
refactor/<issue-id>-short-description
chore/<issue-id>-short-description
```

Examples:
- `feat/12-home-screen`
- `feat/18-mock-provider`
- `fix/27-score-bug-endless`
- `refactor/31-split-round-generator`

### 3. Keep scope small
One branch should solve **one logical unit of work**.

### 4. Open a PR
Every branch should become a PR before merge.

The PR should contain:
- what was done
- why it was done
- how to validate it
- risks or trade-offs
- a reference to the issue

### 5. Merge only when reviewable
Minimum conditions for merge:
- tests passing
- scope aligned with the issue
- no obvious dead code
- no hidden critical TODOs

---

## Recommended Backlog Strategy

1. project scaffold
2. domain models and enums
3. scoring engine
4. question generator
5. mock provider
6. SQLite persistence
7. home screen
8. game screen
9. leaderboard
10. stats screen
11. mock historical mode
12. real API integration
13. real cache
14. visual polish

---

## Commit Conventions

Prefer small commits with clear messages.

```text
feat: add mock provider for local game data
fix: correct endless mode score penalty
refactor: split score logic from game screen
test: add coverage for difficulty selection
chore: configure project dependencies
```

Avoid commits such as:
- `update`
- `fix stuff`
- `wip`
- `misc`

---

## What the Agent May Decide Alone

- internal class and function names
- fine-grained file organization
- utility helpers
- test structure
- small TUI visual details
- loading and error messages
- small technical abstractions

## What the Agent Must Not Decide Alone

Without a dedicated issue or explicit authorization, the agent must not:
- replace the main stack
- replace Textual with another framework
- change a core game rule
- add online multiplayer
- switch local persistence to another database
- add authentication
- couple the real provider directly to the UI
- expand the MVP beyond points as the main metric

---

## Definition of Done per PR

A PR is only ready when it:
- resolves a clearly defined issue
- preserves the layered architecture
- includes appropriate tests
- does not add unnecessary technical debt
- leaves the project runnable
- updates documentation when needed

---

## Skills and Plugins Policy

Skills and plugins are opt-in for this repository.

Rules:
- Do not use any skill or plugin workflow unless the user explicitly asks for it by name.
- Ignore `.agents/` skills unless explicitly requested.
- Ignore plugin-provided skills, including Superpowers skills, unless explicitly requested.
- Do not assume any skill applies implicitly from the task alone.
- Do not expand scope based on skill or plugin content alone.
- Repository instructions override generic skill-discovery or skill-enforcement workflows.
- If a prompt does not explicitly mention a skill or plugin, ignore them and follow the repository docs instead.

---

## Golden Rule

**Agents should optimize for organization, predictability, and small deliverables.**

Several short, clean issues and PRs are better than one large, coupled, hard-to-review implementation.

---

## Related Documents

In addition to this file, the repository should keep:
- `SPEC.md`
- `ARCHITECTURE.md`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/feature.md`
- `.github/ISSUE_TEMPLATE/bug.md`

If this document conflicts with the product specification, the specification wins.
