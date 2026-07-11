# STAT DESK Redesign — Implementation Plan

Full visual redesign of the Hoop Higher TUI per the design handoff in
`docs/design/stat-desk/handoff/` (`README.md` is the implementation contract;
`Hoop Higher TUI v2.dc.html` is the authoritative visual reference — open in a
browser). Behavior and state management are unchanged; only visuals, layout,
and transient-state presentation are redesigned.

**Branch:** `worktree-stat-desk-redesign`
**Textual:** 8.2.1 installed; latest is 8.2.8 — bump in Phase 0 (see
[RESOURCES.md](RESOURCES.md) for the per-phase Textual API map and why the
patch releases matter: resize perf for breakpoints, built-in ANSI themes for
the 16-color fallback, one snapshot-breaking render fix).

## Known gap vs. the handoff

The handoff covers 6 screens + 2 modals, but the codebase also has a **Run
History screen** (`tui/screens/run_history.py`, PR #85) that the design does
not mention. Phase 10 extends the STAT DESK visual language to it (header
band, table styling identical to Leaderboard, footer hints).

## Phases

Each phase should land as its own commit; run `uv run pytest` and
`uv run ruff check src tests` before committing. Snapshot updates
(`uv run pytest --snapshot-update`) only for intentional visual changes, per
repo guidelines.

### Phase 0 — Theme & design tokens (foundation, everything depends on it)
- Bump textual to 8.2.8 (`uv lock --upgrade-package textual`) and regenerate
  snapshots once *before* any visual change (8.2.6 contains a
  snapshot-breaking render fix) so redesign diffs stay clean.
- New `src/hoophigher/tui/theme.py`: two `Theme` objects — `stat-desk-dark`
  (default) and `stat-desk-light` — mapping the role table from the handoff
  (`void`, `screen`, `panel`, `raised`, `accent`, `success`, `danger`,
  `highlight`, `text`, `muted`, `dim`, `border`) onto Textual theme variables,
  plus the extra surface tokens (card fill, footer strip, success/danger/
  loading/accent card fills, disabled text, hidden-points glyph) as custom
  `variables={...}` entries (e.g. `$card-fill`, `$verdict-success-fill`).
- Register both themes in `app.py`; persist the chosen theme per machine
  (config/local settings, same mechanism as other persisted local data).
- Rule going forward: every widget references a role variable, never raw hex.
- Verify the 16/256-color fallback story: focus indication must pair accent
  fill with a style change (bold/reverse), never color alone. Textual 8.2.5+
  ships `ansi-dark`/`ansi-light` themes + an `ansi` config value — use them
  as the fallback validation harness.
- Theme persistence: subscribe to `App.theme_changed_signal`, store the name
  locally, restore on startup. Preview tokens with `uv run textual colors`.
- Files: `tui/theme.py` (new), `app.py`, `tui/styles.tcss`, `config.py`.

### Phase 1 — Global chrome widgets
- `Scorebug` widget (Game header): panel band, border-bottom; left =
  brand/mode/round/Q, right = score/streak/best; score flash on scoring events
  (`success ▲` / `danger ▼` for one beat, then settle to highlight).
- `HeaderBand` widget for non-Game screens: `‹ back  TITLE` pattern.
- `FooterHints` strip: dim bindings line, per-screen content, supports the
  highlight `esc CANCEL` state (Mode Select loading) and the blinking
  "reveal held" state (Game).
- Files: `tui/widgets/` (new modules), `tui/styles.tcss`.

### Phase 2 — Home screen
- Title (accent bold) → hairline rule → tagline (muted) → hype line
  (highlight) → 4 action rows (Play / Leaderboard `[L]` / Stats `[S]` /
  Quit `[Q]`), focused row = accent fill + near-black text + right-aligned
  shortcut; unfocused = border outline. Optional blinking `▍` cursor in footer.
- Keys unchanged: ↑/↓, Enter, L/S/Q. (Home currently also links Run History —
  keep it; style as a fifth action row, see Phase 10.)
- Files: `tui/screens/home.py`, `styles.tcss`.

### Phase 3 — Mode Select (idle / loading / error)
- Three stacked mode cards: `N NAME` + scoring right (`+100 / −60` etc. in
  success/danger), muted description; focused card = accent border + faint
  accent fill + `▸` marker.
- **Loading:** selected card shows `← starting` (highlight); other two cards
  disabled (dim text + border, non-focusable). Amber status strip
  (border-left 3-cell highlight): braille spinner `⣾⣽⣻⢿⡿⣟⣯⣷` + message
  escalating on a 1s `set_interval` (<5s / 5–15s / >15s per handoff). Fetch
  runs as a `@work(exclusive=True)` worker; Esc calls `worker.cancel()`;
  toast/idle-reset live in `on_worker_state_changed`. Back relabels to
  Cancel; footer shows `esc CANCEL`.
- **Error:** `notify(severity="error")` toast — `✗ Unable to start game` +
  friendly body; screen returns to idle with cards re-enabled.
- Files: `tui/screens/mode_select.py`, `styles.tcss`.

### Phase 4 — Game screen static layout
- Scorebug → context row (date bold + matchup dim left; last-guess line with
  accent `›over›` and verdict right) → games strip (chips; active = accent +
  full score, others = dim abbreviated) → matchup row (two cards + centered
  dim `VS` gutter) → centered prompt (`more`/`fewer` bold, number highlight)
  → HIGHER/LOWER buttons.
- Matchup card: dim uppercase label (`PLAYER A · LOCKED` / `PLAYER B ·
  HIDDEN` with HIDDEN in accent), bold name, muted team+minutes, hero point
  total (bold highlight) or dim `— —` placeholder + dim `PTS` unit. Consider
  Textual's built-in `Digits` widget (3-row block numerals) for the hero
  totals at lg tier — it's the "ASCII-digit helper" the handoff allows, with
  no dependency; decide here and reuse the choice in Game Over (Phase 7).
  See RESOURCES.md for the placeholder caveat.
- **Key fix from old design:** neither button is green/red at rest — focused =
  accent fill + black text + bold; unfocused = neutral outline.
- Keys unchanged: H/L, ←/→, Enter, Esc, Q.
- Files: `tui/screens/game.py`, `tui/widgets/gameplay.py`, `styles.tcss`.

### Phase 5 — Reveal flow (correct / wrong, 1.2s hold)
- On guess: disable both buttons instantly; flip B's `— —` to the real
  number; recolor B's card (success or danger: border + number + fill);
  label → `B · REVEALED`; `▲`/`▼` beside the number.
- Verdict strip (border-left 3-cell, matching fill): `CALLED IT.` /
  `ICE COLD.` + sentence + right-aligned signed delta.
- Wrong guess additionally: losing button gets danger outline + `✗`; scorebug
  score/streak flash danger, streak resets.
- Footer: `reveal held · next question in 1.2s…` (blinking highlight);
  `set_timer(1.2, ...)` then advance or push modal. Nothing clickable during
  the hold.
- Files: `tui/screens/game.py`, `tui/widgets/gameplay.py`, `styles.tcss`.

### Phase 6 — Round Summary modal
- Accent border, dark fill, centered ~64 cells: header (`ROUND N · COMPLETE`
  accent bold + matchup muted right), rule, right/wrong row + signed round
  delta, flavor line, single accent-filled `▸ Continue [enter]` button.
  Background dimmed heavily.
- Files: `tui/screens/round_summary.py`, `styles.tcss`.

### Phase 7 — Game Over modal
- Danger border, centered ~66 cells, centered text: header (`GAME OVER ·
  mode` + end reason right), dim `final score` label, hero number
  (highlight), stat row (✓ right · ✗ wrong · best streak), highlight flavor
  line, **outline** (not accent-filled) `▸ Return home [enter / esc]` button.
- Files: `tui/screens/game_over` logic currently lives in game flow /
  `tests/test_tui_game_over.py` — locate the modal (check `tui/widgets/
  dialog.py`) and restyle.

### Phase 8 — Leaderboard
- Header band `‹ back  LEADERBOARD · top 10 · this machine`; DataTable-style
  grid: dim uppercase header row, rank-1 row highlighted (accent rank +
  faint fill), zebra rows, right-aligned numbers, accuracy success when ≥75%
  else muted. Empty state: `No runs recorded yet. The board's waiting.`
- Files: `tui/screens/leaderboard.py`, `styles.tcss`.

### Phase 9 — Stats
- Header band; 4-up stat card row (runs / questions / correct / accuracy —
  success values where specified); 2-up best row (highlight values); per-mode
  horizontal bars (`█`/`░` block chars or styled `ProgressBar`, accent over
  raised track) + counts. Empty state: `No runs yet — go make some
  regrettable guesses.`
- Files: `tui/screens/stats.py`, `styles.tcss`.

### Phase 10 — Run History screen (not in handoff)
- Apply the STAT DESK language: header band, table/detail styling consistent
  with Leaderboard, footer hints, role tokens throughout. Make judgment calls
  by analogy with the handoff; keep behavior identical.
- Files: `tui/screens/run_history.py`, `styles.tcss`.

### Phase 11 — Responsive tiers
- Breakpoints: width lg ≥128 / md 96–127 / sm 72–95 / xs <72; height
  xs <24 / sm 24–31 / md 32–39 / lg ≥40. Use Textual's built-in
  `HORIZONTAL_BREAKPOINTS` / `VERTICAL_BREAKPOINTS` (list of
  `(min_size, "-class")` tuples on App/Screen) — Textual toggles the classes
  on resize automatically; no manual `on_resize` watching. Tier styling is
  then plain TCSS (`Screen.-xs .games-strip { display: none; }`); content
  swaps CSS can't express key off the same classes.
- Game degradation order (matchup + both buttons NEVER drop):
  1. **sm:** games strip → `active + game N/total`; scorebug/footer
     abbreviate; `37 min` → `37m`.
  2. **xs:** games strip and last-guess line dropped; players stack
     vertically into compact rows; buttons → `▲ HI · H` / `▼ LO · L`.
  3. **short height:** body scrolls; scorebug, buttons, footer stay pinned.
- Verdict strip + both modals keep full priority at every size.
- Files: all screens, `styles.tcss`, `tests/test_tui_responsive.py`.

### Phase 12 — Snapshots, light theme, final pass
- Regenerate snapshots (`uv run pytest --snapshot-update`) and review each
  diff intentionally; extend `tests/test_tui_snapshots.py` to cover new
  states (loading strip, reveal correct/wrong, modals, light theme) using
  `snap_compare(..., terminal_size=(w, h), run_before=...)` — one snapshot
  per tier for the key screens, `run_before` to drive transient states.
- Verify light (paper) theme end-to-end; verify readability with color
  ignored (focus via fill/reverse, no red/green-only signals) — run under
  the built-in `ansi-dark` theme (Textual 8.2.5+) as the validation harness.
- `uv run ruff check src tests` + `uv run ruff format src tests`.
- Manual run-through: `HOOPHIGHER_STATS_PROVIDER=mock uv run hoop-higher`
  at lg/md/sm/xs terminal sizes, dark + light.

## Constraints (from the handoff — apply to every phase)

- Recreate in Textual primitives + TCSS; do **not** port HTML/CSS literally.
- Monospace character grid: spacing in whole cells; "font sizes" = bold/dim/
  color emphasis, never real scaling; big numerals = bold + color by default.
- No emoji; only the safe single-width glyphs `▲ ▼ ▸ ‹ ✓ ✗ ★ ›` + braille
  spinner frames. No shipped fonts or images.
- Domain/services untouched; scoring must keep matching `domain/scoring.py`.
- Spinner/blink are decorative — app must be fully readable without them.
