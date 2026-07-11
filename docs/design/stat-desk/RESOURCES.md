# STAT DESK — Textual Resources & API Map

Research notes mapping Textual 8.x capabilities onto the phases in
[PLAN.md](PLAN.md). Verified against the official docs on 2026-07-11.

## Version status

- **Installed:** textual 8.2.1 · **Latest:** 8.2.8 (2026-06-30).
- Recommended: bump to 8.2.8 in Phase 0 (`uv lock --upgrade-package textual`).
  Patch-only releases, but two matter here:
  - **8.2.2 / 8.2.3** — resize-handling performance fixes (fewer style
    recomputes, timer-based resize). Directly relevant to Phase 11's
    breakpoint classes.
  - **8.2.5** — new built-in `ansi-dark` / `ansi-light` themes + `ansi` theme
    config value: the framework-level answer to the handoff's 16-color
    fallback requirement.
  - **8.2.6** — a snapshot-breaking rendering fix; regenerate snapshots once
    right after the bump, *before* any visual work, so the redesign diffs
    stay clean.
- Changelog: <https://github.com/Textualize/textual/blob/main/CHANGELOG.md>

## Phase 0 — Theming

Docs: <https://textual.textualize.io/guide/design/>

- `textual.theme.Theme(name=..., primary=..., accent=..., success=...,
  warning=..., error=..., surface=..., panel=..., background=...,
  foreground=..., dark=True, variables={...})`. Only `primary` is required;
  Textual derives shades automatically.
- **Role mapping** (handoff role → Theme field): `accent`→`primary`+`accent`,
  `success`→`success`, `danger`→`error`, `highlight`→`warning`,
  `screen`→`background`, `panel`→`panel`, `raised`→`surface`,
  `text`→`foreground`. The remaining roles (`void`, `muted`, `dim`,
  `border`) and all extra surface fills (card fill, footer strip,
  success/danger/loading/accent card fills, disabled text, hidden-points
  glyph) go in `variables={...}` as custom tokens (`$muted`, `$card-fill`,
  `$verdict-danger-fill`, …).
- Auto-generated variants come free: `$primary-darken-2`, `$error-muted`,
  `$text-primary`, `$border`, etc. — prefer these before minting new tokens.
- Register + activate in `App.on_mount`: `self.register_theme(theme)` then
  `self.theme = "stat-desk-dark"`. Defaults for custom variables:
  override `App.get_theme_variable_defaults()`.
- **Persistence:** subscribe to `App.theme_changed_signal` and write the
  chosen name to local settings; restore on startup.
- Preview all tokens live: `uv run textual colors`.
- Dev loop: `textual run --dev` gives live TCSS editing;
  `textual console` for logs (no `print()` in TUI code).

## Phase 3 — Loading / cancellation

Docs: <https://textual.textualize.io/guide/workers/>

- Fetch as `@work(exclusive=True)` async worker; `exclusive` kills a stale
  fetch if the user re-triggers.
- Esc cancel: keep the `Worker` handle, call `worker.cancel()` (async workers
  get `CancelledError`; thread workers must poll `worker.is_cancelled` and
  UI-update via `call_from_thread`).
- React to SUCCESS / ERROR / CANCELLED in `on_worker_state_changed` — this is
  where the error toast (`self.notify(title=..., severity="error")`) and
  idle-state reset belong.
- Spinner + escalating message: one `set_interval(1, ...)` driving both, per
  the handoff.

## Phases 4, 5, 7 — Game hero numerals

Docs: <https://textual.textualize.io/widgets/digits/>

- Built-in **`Digits` widget**: 3-row-tall block numerals (0-9, A-F,
  `+ - ^ : ×`), styleable with normal CSS (`color: $warning`), `width: auto`,
  `.update()` to change value. This is the "figlet/ASCII-digit helper" the
  handoff mentions — zero extra dependency.
- Handoff default is still plain bold+color; treat `Digits` as the upgrade
  path for the matchup point totals and the Game Over hero score if lg-tier
  spacing allows (3 rows tall — check sm/xs tiers before committing).
- The hidden `— —` placeholder: `Digits` has no em-dash glyph — render the
  placeholder as a `Static` swapped for the `Digits` on reveal, or stay
  bold-text everywhere for consistency. Decide once in Phase 4 and reuse in
  Phase 7.

## Phases 6, 7 — Modals

Docs: <https://textual.textualize.io/guide/screens/#modal-screens>

- `ModalScreen[ResultType]` + `self.dismiss(result)`; push with a callback or
  `push_screen_wait` from a worker.
- The "game dimmed behind" effect = the modal screen's own `background` with
  alpha (e.g. `background: $void 60%`); anything not covered by the dialog
  shows the tinted screen below. No manual opacity work needed.
- Center the dialog with `align: center middle` on the screen; fixed dialog
  width (~64/66 cells) on the inner container.

## Phase 8 — Leaderboard table

Docs: <https://textual.textualize.io/widgets/data_table/>

- `DataTable` with `zebra_stripes = True` (`datatable--odd-row` /
  `datatable--even-row` component classes match the handoff's zebra).
- Style header via `datatable--header`; cursor via `datatable--cursor`;
  `cursor_type = "row"` (or `"none"` for a display-only board).
- Per-cell color/alignment: pass Rich `Text` objects —
  `Text("77.2%", style="bold green", justify="right")` — for right-aligned
  numbers and the accuracy ≥75% success coloring.
- Rank-1 row treatment: component classes can't target one row; use a Rich
  `Text` style per cell of row 1, or `add_row(..., label=...)` + styling.

## Phase 11 — Responsive breakpoints

Docs: <https://textual.textualize.io/api/app/> (also valid on `Screen`)

- **`HORIZONTAL_BREAKPOINTS` / `VERTICAL_BREAKPOINTS`** class attributes:
  list of `(min_size, "-class")` tuples; Textual toggles the class on resize
  automatically — no manual `on_resize` watching needed.
- Handoff tiers map directly:

  ```python
  HORIZONTAL_BREAKPOINTS = [(0, "-xs"), (72, "-sm"), (96, "-md"), (128, "-lg")]
  VERTICAL_BREAKPOINTS = [(0, "-h-xs"), (24, "-h-sm"), (32, "-h-md"), (40, "-h-lg")]
  ```

- Then pure TCSS per tier: `Screen.-xs .games-strip { display: none; }` etc.
  Content swaps that CSS can't express (abbreviated labels, stacked player
  rows) key off the same classes via `on_screen_resume`/watchers or
  `DOM.update_classes` (added 8.2.4).

## Phase 12 — Testing

Docs: <https://textual.textualize.io/guide/testing/>

- `app.run_test(size=(w, h))` → `Pilot` (`press`, `click`, `pause`) for
  behavior tests at exact tier sizes.
- `pytest-textual-snapshot` (installed, 1.0.0): `snap_compare(path,
  terminal_size=(w, h), press=[...], run_before=async_hook)` — use
  `terminal_size` for one snapshot per tier per key screen, and `run_before`
  to drive transient states (loading strip, reveal correct/wrong, modals).
- 16-color validation: run the app with the `ansi` theme config value /
  built-in `ansi-dark` theme (8.2.5+) to prove focus survives without RGB.

## General references

- Design guide (themes/tokens): <https://textual.textualize.io/guide/design/>
- CSS types & styles reference: <https://textual.textualize.io/styles/>
- Widget gallery: <https://textual.textualize.io/widgets/> — relevant here:
  `Digits`, `DataTable`, `ProgressBar`, `Rule` (Home's hairline rule),
  `Sparkline` (not needed, but adjacent), `Footer`.
- Workers: <https://textual.textualize.io/guide/workers/>
- Screens & modals: <https://textual.textualize.io/guide/screens/>
- Testing: <https://textual.textualize.io/guide/testing/>
- Devtools: <https://textual.textualize.io/guide/devtools/> (`textual run
  --dev` live-edits TCSS — fastest loop for this whole redesign)
