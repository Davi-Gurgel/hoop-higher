# Open issue audit — 2026-07-20

## Conclusion

The backlog is mostly sound, but not every open issue should continue unchanged. At the
audited `main` commit (`42743ff`), the repository had 12 open issues:

- **Keep 9:** #60, #61, #62, #70, #71, #94, #95, #96, and #97.
- **Reframe 1:** #93 discloses information derived from the hidden Player Line before the
  Guess and can sometimes reveal the correct direction.
- **Close 2:** #63 is superseded by #97, and #67 was already completed by merged PR #91.

Two retained issues are already at the finish line: [PR #99](https://github.com/Davi-Gurgel/hoop-higher/pull/99)
closes #60 and [PR #98](https://github.com/Davi-Gurgel/hoop-higher/pull/98) closes #61. Both
were open, non-draft, mergeable, and green when this audit was performed.

## Audit criteria

An issue is valid when its requested outcome is still absent from `main`, fits the product
language and architectural decisions, is not duplicated or superseded, and is specific enough
to guide implementation. The audit used the live issue and PR records, the source at
[`42743ff`](https://github.com/Davi-Gurgel/hoop-higher/tree/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f),
the root [domain language](../../CONTEXT.md), and the repository's ADRs as primary sources.

## Per-issue verdicts

| Issue | Verdict | Evidence and recommendation |
| --- | --- | --- |
| [#60 — Extract NBA API payload parsing](https://github.com/Davi-Gurgel/hoop-higher/issues/60) | **Keep until PR merges** | On audited `main`, fetching, caching, retry behavior, and V2/V3 parsing still share the large [`nba_api_stats_source.py`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/data/stats_sources/nba_api_stats_source.py). [PR #99](https://github.com/Davi-Gurgel/hoop-higher/pull/99) implements the extraction, has green CI, and contains `Closes #60`; merge it and let GitHub close the issue. The body blocker #57 is already closed. |
| [#61 — Simplify Playable NBA Game fetching and historical resolution loops](https://github.com/Davi-Gurgel/hoop-higher/issues/61) | **Keep until PR merges** | The requested simplification is consistent with the resolver seam introduced by closed issue #59. [PR #98](https://github.com/Davi-Gurgel/hoop-higher/pull/98) implements it with coverage for bounded concurrency, ordering, early exit, and shared probing; it has green CI and contains `Closes #61`. Merge it and let GitHub close the issue. |
| [#62 — Move mock Source Date knowledge behind the Stats Source boundary](https://github.com/Davi-Gurgel/hoop-higher/issues/62) | **Keep, but tighten the design choice** | The leak is real: [`app.py`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/app.py#L141-L184) imports the mock adapter, checks it with `isinstance`, supplies mock-only dates, and builds untyped kwargs bags. That conflicts with the Stats Source seam and with [ADR-0003](../adr/0003-layer-boundaries-for-gameplay.md). Before agent work, choose one of the issue's two proposed designs instead of leaving “hints or normal recent-date path” open-ended. Its #59 blocker is closed. |
| [#63 — Return Round completion aggregates from the service](https://github.com/Davi-Gurgel/hoop-higher/issues/63) | **Close as superseded by #97** | The underlying problem is genuine, but [#97](https://github.com/Davi-Gurgel/hoop-higher/issues/97) contains every #63 outcome and goes further by returning the post-turn snapshot and Run-finished state. Implementing both would duplicate the same interface transition. Close #63 with a pointer to #97. |
| [#67 — Replace scoring mode ladders with a scoring policy table](https://github.com/Davi-Gurgel/hoop-higher/issues/67) | **Close as completed** | [Merged PR #91](https://github.com/Davi-Gurgel/hoop-higher/pull/91) added the immutable [`SCORING_POLICIES`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/domain/scoring.py#L9-L64) table and per-mode tests while preserving the scoring economy. The PR referred to the issue but did not use a closing keyword, so the tracker stayed open. |
| [#70 — Add a configurable Round question count](https://github.com/Davi-Gurgel/hoop-higher/issues/70) | **Keep, lower priority** | The domain and Gameplay Service already accept 5–10 Questions, but [`Settings`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/config.py#L9-L35) has no question-count setting and [`app.py`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/app.py#L171-L184) hardcodes five. The feature is coherent, though larger counts can reduce how many NBA Games qualify as Playable NBA Games. Its #64 blocker is closed. |
| [#71 — Decide whether Question Difficulty should affect scoring](https://github.com/Davi-Gurgel/hoop-higher/issues/71) | **Keep as a human decision** | [ADR-0001](../adr/0001-initial-scoring-economy.md) explicitly requires future scoring changes to account for persisted Leaderboard and Player Stats comparability, while the persisted [`RunRecord`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/data/schema.py#L12-L23) has no scoring-ruleset version. The issue asks for exactly the missing product decision and is correctly human-owned. Prefer defer/reject unless score versioning or Leaderboard partitioning is also accepted. Its #67 blocker is functionally complete. |
| [#93 — Show Question Difficulty on the game screen](https://github.com/Davi-Gurgel/hoop-higher/issues/93) | **Reframe before implementation** | Question Difficulty is calculated from the absolute difference involving the hidden Player Line: hard is 1–4, medium 5–9, and easy 10+ ([difficulty rules](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/domain/difficulty.py#L4-L15)). Showing it before the Guess leaks hidden information and can disclose the direction outright: if the known line is below 10 and the chip says “easy,” the hidden line cannot be 10+ points lower. [ADR-0002](../adr/0002-round-difficulty-ramp.md) requires a ramp, not pre-Guess disclosure. Show difficulty after reveal/in Run History, or explicitly approve it as an intentional hint mechanic with gameplay tests. |
| [#94 — Label Run end reason in Run History](https://github.com/Davi-Gurgel/hoop-higher/issues/94) | **Keep** | [`RunRecord.end_reason`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/data/schema.py#L12-L23) is persisted, but [`RunHistoryRow`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/services/run_history_service.py#L14-L23) and the [Run History rendering](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/tui/screens/run_history.py#L42-L46) omit it. This adds useful context to an existing player-facing feature. Map the persisted compatibility value `wrong_answer` to the domain wording “Wrong guess,” and render `None` explicitly, such as “Interrupted.” |
| [#95 — Deepen Question Result into a single domain transition](https://github.com/Davi-Gurgel/hoop-higher/issues/95) | **Keep, high priority** | [`GameplayService.submit_guess`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/services/gameplay_service.py#L164-L202) must call three helpers in order, construct `QuestionResult`, then mutate `RunState`. A single pure domain transition makes that module deeper: callers learn less ordering knowledge, behavior becomes local, and tests can use the same interface. This fits ADR-0003 and is the real blocker for #97. |
| [#96 — Deepen Run persistence behind a gameplay write module](https://github.com/Davi-Gurgel/hoop-higher/issues/96) | **Keep, high priority** | The Gameplay Service imports session scope, three repositories, and SQLModel records, then owns mapping, transactions, and write order throughout [`gameplay_service.py`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/services/gameplay_service.py#L8-L15). A gameplay write module has a small domain-facing interface while hiding substantial local SQLite implementation, so it passes the deletion test and respects [ADR-0004](../adr/0004-local-persistence-boundary.md). |
| [#97 — Deepen the Run turn transition](https://github.com/Davi-Gurgel/hoop-higher/issues/97) | **Keep, blocked by #95** | The service returns only `QuestionResult`, while [`GameScreen`](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/tui/screens/game.py#L47-L58) keeps a parallel `RoundTally` and its [Guess flow](https://github.com/Davi-Gurgel/hoop-higher/blob/42743ff5a2aa5a52a6ba2268fb8e989606c7cb6f/src/hoophigher/tui/screens/game.py#L182-L250) captures pre-turn state, computes last-question state, and requests a second snapshot. A complete turn outcome removes two clocks tracking one Run. It also supersedes #63. |

## Recommended order

1. Merge PR #98/#61 and PR #99/#60.
2. Close #67 as completed and #63 as superseded.
3. Implement #95, then #96, then #97 sequentially because all three touch the Gameplay
   Service; this progresses from the domain module through persistence to the TUI-facing
   interface.
4. Implement #62 after #61 merges, then #70 to avoid overlapping app configuration work.
5. Implement #94 independently.
6. Decide #71, then rewrite #93 around post-reveal visibility or explicitly approve the
   pre-Guess hint mechanic.

Only #97's dependency on #95 remains live. The older blocker notes in #60, #61, #62, #70,
and #71 point to work that is already closed or implemented and should be cleaned up when
those issues are next edited.

## Scope and caveats

This audit recommends tracker actions but does not apply them. It evaluates issue validity
against the current product and architecture; it does not review the implementation quality
of PR #98 or PR #99 beyond their live merge/check status.
