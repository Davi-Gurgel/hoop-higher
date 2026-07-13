# Theme toggle — Resources & API Map

Research notes for the light/dark theme toggle: a global `t` binding that
flips between the two registered themes, persisted via the existing
theme-settings file, with dark as the first-run default. Verified against the
official docs and this branch (`worktree-stat-desk-redesign`) on 2026-07-12.

## Decisions (2026-07-12)

1. **No auto-detection.** The original plan's OSC 11 → COLORFGBG terminal
   background detector is dropped. With persistence in place it would only
   ever run once per machine (the saved file wins afterwards), and it was
   the riskiest code in the feature. Research preserved in the appendix in
   case a future version revisits it.
2. **No `HOOPHIGHER_THEME` env var.** Toggle-only; can be added later if
   someone asks. `.env.example` and `config.py` stay untouched.
3. **Persistence stays** (already shipped on this branch). Precedence:
   saved theme file → `hoop-higher-dark` default.
4. **Themes are renamed** `stat-desk-*` → `hoop-higher-dark` /
   `hoop-higher-light`.

## Branch state

The STAT DESK redesign branch already ships the hard parts:

| Piece | Status |
| --- | --- |
| Dark + light themes with semantic variables | **Done** — `src/hoophigher/tui/theme.py` (as `stat-desk-*`; rename pending) |
| Zero hardcoded hex in TCSS / widgets | **Done** (verified by grep) |
| Custom-variable fallbacks for non-STAT-DESK themes | **Done** — `App.get_theme_variable_defaults()` (`src/hoophigher/app.py:99`) |
| Persistence: save on `theme_changed_signal`, restore on startup, headless guard | **Done** — `_restore_theme` / `_persist_theme_choice` (`src/hoophigher/app.py:102-114`), tested in `tests/test_tui_theme.py` |
| Light-theme snapshots, deterministic vs. developer terminal | **Done** — `NO_COLOR=1` autouse fixture + explicit `pilot.app.theme` in `tests/test_tui_snapshots.py` |

## Remaining work

### 1. Rename themes to `hoop-higher-*`

- `theme.py`: `DARK_THEME_NAME` / `LIGHT_THEME_NAME` constants (all other
  code already goes through the constants).
- Literal strings elsewhere: `tests/test_tui_snapshots.py:80,85`
  (`pilot.app.theme = "stat-desk-light"`) — switch to importing the constant.
- Names only, not colors — **snapshots must not change**; a diff here is a
  bug, not a `--snapshot-update` case.
- Previously persisted `stat-desk-*` files stop resolving and fall back to
  the dark default (existing `if saved_theme_name in self.available_themes`
  guard handles it). Acceptable one-time cost.

### 2. Global `t` toggle

Docs: [Input guide — priority bindings](https://textual.textualize.io/guide/input/#priority-bindings).

- App-level
  `BINDINGS = [Binding("t", "toggle_theme", "Theme", priority=True)]` —
  priority bindings are checked **before** the focused widget's bindings, so
  the toggle works on every screen, including gameplay and modals.
- Key collision audit (this branch): bound keys are `1 2 3`, `h`, `l`, `s`,
  `q`, arrows, `enter`, `escape`, `-`. **`t` is free**, and there are no
  `Input` widgets, so a priority binding can't steal typed text today. If a
  text `Input` ever lands (e.g. leaderboard name entry), a priority `t`
  fires *while typing* — guard the action or drop `priority` then.
- Action body: flip between the two theme names, then
  `self.notify("Theme: light", timeout=2)` (`App.notify` pattern already in
  `app.py`). The existing `theme_changed_signal` subscription persists the
  choice automatically — no extra save call in the action.
- Footer visibility: the binding's description shows in `Footer` on screens
  that render one; pass `show=False` if it would crowd the footer strip.

### 3. Docs

- `README.md`: add a short theming note (dark default, `t` toggles and
  remembers the choice) near the existing `HOOPHIGHER_*` mentions
  (lines ~62–68). No `.env.example` change (no new setting).

### 4. Tests

Extend `tests/test_tui_theme.py` (patterns already there):

| Case | Approach |
| --- | --- |
| `t` flips dark → light → dark | `run_test()` + `pilot.press("t")`, assert `app.theme` |
| Toggle works mid-gameplay and on modals | Navigate first (see `test_app_stays_usable_under_ansi_fallback_theme` for the navigation pattern), then press `t` |
| Toggle persists | Headless runs skip persistence — cover via `save_theme_name`/`load_saved_theme_name` round-trip (already tested) plus an app test asserting `_persist_theme_choice` is subscribed, or monkeypatching the save path |
| Rename didn't shift pixels | Existing snapshot suite passes with **no** snapshot updates |

Validation: `uv run pytest`, `uv run ruff check src tests`, then
`HOOPHIGHER_STATS_PROVIDER=mock uv run hoop-higher` and press `t` on Home,
gameplay, and a modal.

## References

- Textual input guide (priority bindings): <https://textual.textualize.io/guide/input/#priority-bindings>
- Textual design/theme guide: <https://textual.textualize.io/guide/design/>
- Sibling doc: [../stat-desk/RESOURCES.md](../stat-desk/RESOURCES.md) — theme
  role table and Textual 8.x version notes.

## Appendix — auto-detection research (deferred)

Kept for a future `HOOPHIGHER_THEME=auto` version; none of this ships now.

- Textual has **no built-in** terminal-background detection (changelog
  checked through 8.2.8); it would be a hand-rolled OSC 11 query.
- Query `b"\x1b]11;?\x1b\\"` before `App.run()` (tty still in canonical
  mode); reply `ESC ] 11 ; rgb:RRRR/GGGG/BBBB (ST|BEL)` with 1–4 hex digits
  per channel; classify by relative luminance
  (`0.2126R + 0.7152G + 0.0722B > 0.5` → light). Handshake: termios cbreak +
  `select` with ~100–200 ms deadline, restore in `finally`, every failure →
  dark. A trailing DA1 query (`ESC [ c`) gives an early "unsupported" signal.
- `COLORFGBG` fallback: last field of `"<fg>;<bg>"` /
  `"<fg>;default;<bg>"`; vim heuristic: bg 0–6 or 8 → dark, 7 / 9–15 →
  light. Stale after live theme switches; weak signal.
- Known flaky terminals: tmux may reply with a stale outer color
  ([tmux#3994](https://github.com/orgs/tmux/discussions/3994)); Tabby
  always reports black ([tabby#10121](https://github.com/Eugeny/tabby/issues/10121)).
- References: [xterm ctlseqs OSC](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands),
  [OSC 10/11 Python query gist](https://gist.github.com/ntrrgc/fc47b416bff68ebc05883ec733c8a7b8),
  [Gentoo wiki — terminal colors](https://wiki.gentoo.org/wiki/Terminal_emulator/Colors);
  prior art: `delta`, `bat`, Rust `termbg`.
- Testability sketch: pure `parse_osc11_reply` / `classify_luminance` /
  `parse_colorfgbg` functions + a thin injectable tty layer.
