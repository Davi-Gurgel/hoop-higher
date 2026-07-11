# Handoff: Hoop Higher — TUI Redesign (STAT DESK)

## Overview
Hoop Higher is a higher/lower guessing game about NBA player scoring, built with **Textual** (Python TUI framework). Each question compares two player lines from the same real NBA game: Player A's points are shown, Player B's are hidden, and the player guesses whether B scored higher or lower. This handoff covers a full visual redesign — codename **STAT DESK** — spanning all 6 screens, 2 modals, and every transient state (loading, error, reveal), in both dark (default) and light themes, across four terminal-size tiers.

## About the Design Files
The file in this bundle (`Hoop Higher TUI v2.dc.html`) is a **design reference created in HTML** — a prototype showing the intended look, layout, and behavior. It is **not production code to copy**. The HTML uses CSS `border`, `background`, flex/grid, and pixel font-sizes purely to *simulate* how the design should render on a character-grid terminal.

The task is to **recreate this design in the existing Textual codebase** using Textual's own primitives: `Screen` / `ModalScreen`, container widgets (`Horizontal`, `Vertical`, `Grid`), `Static`, `Button`, `Label`, `Footer`, `DataTable`, and **Textual CSS (`.tcss`)** for all styling. Where the HTML shows a "1px border", that maps to a Textual `border:` (e.g. `round`, `heavy`, `tall`, `hkey`); where it shows a filled button, that maps to a `Button` variant with `background`. Do not attempt to port the HTML/CSS literally.

## Fidelity
**High-fidelity.** Colors, hierarchy, copy, spacing intent, and state behavior are final. Recreate faithfully using Textual widgets + TCSS. The one translation layer to keep in mind: everything must land on a **monospace character grid** — spacing is in whole cells, "font sizes" in the mock are just relative emphasis (use bold / dim / color / `text-style`, not real font scaling), and the large point numerals in the mock should be rendered with Rich markup emphasis (bold + color), NOT an actual larger font. If big block-figure numerals are desired, use a figlet/ASCII-digit helper — but plain bold color is the default and is fine.

---

## Design Tokens

Define these once as a theme (Textual 0.86+ supports `App.theme` + design tokens, or use TCSS `$variables`). Every widget references a **role**, never a raw hex — a theme swap is one table.

### Dark theme (default)
| Role | Hex | Use |
|---|---|---|
| `void` | `#08090B` | space behind the app / outermost |
| `screen` | `#0E1013` | screen background |
| `panel` | `#191C22` | scorebug / header bands |
| `raised` | `#22262E` | cards, table row hover |
| `accent` | `#FF6A3D` | brand, focus fill, active game chip |
| `success` | `#46C988` | correct, positive delta |
| `danger` | `#FF5D61` | wrong, negative delta |
| `highlight` | `#F2C14E` | score value, loading, known-points |
| `text` | `#E8E6E1` | primary text |
| `muted` | `#9AA0AB` | labels, secondary meta |
| `dim` | `#5C626D` | footer hints, disabled, captions |
| `border` | `#2A2F38` | panel/card borders, rules |

Extra dark surfaces used in mocks: card fill `#12151B`; footer strip `#0C0E11`; success card fill `#0F1A14`; danger card fill `#1A1012`; loading strip fill `#16130C`; accent card fill `#1A120D`; disabled text `#363B44`; hidden-points glyph `#3A4048`.

### Light theme (paper)
| Role | Hex |
|---|---|
| `void` | `#EAE4D8` |
| `screen` | `#FAF7F1` |
| `panel` | `#ECE7DD` (bands `#F0EBE1`) |
| `raised` | `#E0D9CB` (card fill `#F3EEE4`) |
| `accent` | `#E0521F` |
| `success` | `#1F9D57` |
| `danger` | `#D13B3F` |
| `highlight` | `#B8791A` |
| `text` | `#1E1B16` |
| `muted` | `#6B6355` |
| `dim` | `#948B7A` |
| `border` | `#D5CDBD` |

**16/256-color fallback:** accent→bright orange/`208`, success→green/`42`, danger→red/`203`, highlight→yellow/`221`. Focus must remain distinguishable without color — always pair the accent fill with a style change (see Focus).

### Spacing / type scale (in cells)
- Screen padding: `1 2` (1 row top/bottom, 2 cols sides) on content; bands are full-bleed with `padding: 0 2`.
- Card padding: `1 2`. Gap between the two matchup cards: 1 col + a centered "VS" gutter.
- Emphasis levels: point total = **bold + highlight/accent color**; player name = **bold text**; card label = **dim, uppercase**; meta = muted.
- Type: JetBrains Mono is the reference face; in a terminal this is whatever monospace the user's terminal uses — do not ship a font. Use `text-style: bold` / `dim` / `reverse` for weight.

---

## Global chrome (present on most screens)

### Scorebug (top of Game; simplified header elsewhere)
A single full-width `panel`-background row, `border-bottom: solid $border`:
- **Left:** `HOOP HIGHER` (accent, bold) · `ENDLESS` (muted) · `round` (dim) `2` (text bold) · `Q` (dim) `3/5` (text bold).
- **Right:** `score` (dim) `640` (highlight bold) · `streak` (dim) `4` (text bold) · `best` (dim) `6` (muted).
- On a scoring event the score value recolors for one beat: `success` + `▲` on a gain, `danger` + `▼` on a loss, then settles back to `highlight`.

### Footer
Every screen ends with a `Footer`-style strip (`#0C0E11` bg, `border-top`), `dim` text listing live bindings, letter shortcuts bracketed inside labels, e.g.:
`H higher · L lower · ←/→ move · enter guess · esc abandon · Q quit`.

---

## Screens / Views

### 1. Home
- **Purpose:** entry; launch Play or jump to Leaderboard/Stats/Quit.
- **Layout:** vertical stack, screen padding `1 2`. Title, hairline rule, tagline, then a 4-item action list; footer pinned bottom.
- **Components:**
  - Title `HOOP HIGHER` — accent, bold, largest emphasis.
  - Rule: full-width `border` colored line (1 row).
  - Sub-tagline `higher / lower · guess who scored more` — muted.
  - Hype line `Two players, one hidden number. Back yourself.` — highlight.
  - Action rows (each full-width, `padding: 0 2`, height 3, rounded/`tall` border feel): **Play** (focused → accent fill, black text, right-aligned `enter`), **Leaderboard** `[L]`, **Stats** `[S]`, **Quit** `[Q]` (unfocused → border outline, text label, dim shortcut right-aligned).
  - Blinking accent cursor `▍` in footer (optional flavor).
- **Keys:** ↑/↓ move focus, Enter activates, L / S / Q shortcuts.

### 2. Mode Select
- **Purpose:** pick Endless / Arcade / Historical, then fetch game data.
- **Layout:** header band (`‹ back  CHOOSE YOUR MODE`), then 3 stacked mode cards, footer.
- **Mode card:** border box, `padding: 1 2`. Top row: `N  NAME` (bold) left, scoring right (`+100`/`−60` success/danger, `+150 / over` etc.). Second row: one-line description in muted.
  - Endless — `Miss all you like — the run rolls on.` · `+100 / −60`
  - Arcade — `One miss and you're done. Bigger points.` · `+150 / over`
  - Historical — `A random night from the archives.` · `+100 / −60`
  - Focused card → accent border + faint accent fill (`#1A120D`) + `▸` marker and accent name.
- **Keys:** ↑/↓ + Enter, or 1/2/3 jump; Esc back; Q quit.

#### 2a. Loading state
- Selected card shows `← starting` in highlight; the **other two cards disable** (dim text `#363B44`, dim border) and are non-focusable.
- An amber **status strip** appears (border-left 3-cell `highlight`, fill `#16130C`): braille spinner `⣾` (cycles `⣾⣽⣻⢿⡿⣟⣯⣷` on a timer) + message + dim sub-line.
- **Message escalates on a 1s tick:**
  - `<5s`: `Loading {mode} game data...`
  - `5–15s`: `Still fetching NBA games ({n}s)...`
  - `>15s`: `stats.nba.com is slow; press Esc to cancel ({n}s).`
- Footer: **`esc CANCEL`** (highlight, bold) — Esc cancels the async fetch. Back button relabels to Cancel.

#### 2b. Error state
- Fetch failure/timeout → red **toast** (Textual `notify(..., severity="error")` or a `ModalScreen`): title **`✗ Unable to start game`**, body e.g. `stats.nba.com timed out. Not on you this time — try again.` (danger border, `#1A1012` fill).
- Screen returns to **idle** (cards re-enabled); user picks again.

### 3. Game (core screen)
- **Purpose:** answer the higher/lower question; the comparison chain runs here.
- **Layout (lg/md):** scorebug → context row → games strip → matchup row (two cards + VS) → prompt (centered) → two action buttons → footer.
  - **Context row:** left `Apr 12, 2025 · LAL @ DEN` (date bold, matchup dim); right `last  Morant 34 ›over› Curry 29  ✓ +100` (dim with accent `›over›` and success verdict). `border-bottom` hairline.
  - **Games strip:** horizontal row of chips, one per playable game that date. Active chip → accent border + accent text + full score `LAL 105 · DEN 109`; others → `border` outline, dim, abbreviated `BOS · LAL`.
  - **Matchup cards** (each `flex:1`, border, `padding: 1 2`, fill `#12151B`):
    - Label: `PLAYER A · LOCKED` (dim, uppercase) — B's is `PLAYER B · HIDDEN` with `HIDDEN` in accent.
    - Name (bold text), team + minutes (muted, `LAL · 37 min`).
    - **Point total = hero:** big bold `highlight` for the known player (`34`), and a dim placeholder `— —` for the hidden player, with a small `PTS` unit in dim.
    - Between the cards: a centered `VS` in a narrow dim gutter.
  - **Prompt (centered):** `Did {B_last} score more or fewer than {A_first}'s {A_pts}?` — muted sentence with `more`/`fewer` bolded and the number in highlight.
  - **Buttons (row, gap 1):** **HIGHER** `▲ HIGHER [H]` and **LOWER** `▼ LOWER [L]`. Focused = accent fill + black text + bold; unfocused = border outline + muted label + dim shortcut. **Neither is green/red at rest** — that's the key fix from the old design.
- **Keys:** H = higher, L = lower, ←/→ move focus between buttons, Enter guesses the focused one, Esc abandons run → Home, Q ends run + quits app.

#### 3a. Reveal — correct (1.2s hold)
- On guess **both buttons disable instantly** (dim, `opacity` feel — in Textual set `disabled` + dim) so no double-submit.
- Player B's `— —` flips to the real number; **B's whole card border + number turn `success`**, card fill → `#0F1A14`, number gets `▲` (or `▼` if the real number is lower). B label → `B · REVEALED` in success.
- A **verdict strip** drops in (border-left 3-cell success, fill `#0F1A14`): `CALLED IT.` (success bold) + `Jokić went for 49 — that's over.` + right-aligned `+100` (success bold).
- Scorebug score animates to new value, colored success `▲` for one beat.
- Footer: `reveal held · next question in 1.2s…` (blinking highlight).
- After **1.2s** the next question loads, OR the Round Summary / Game Over modal takes over.

#### 3b. Reveal — wrong (1.2s hold)
- Same mechanics but **danger**: B card border/number/fill danger (`#1A1012`), verdict `ICE COLD.` + `He dropped 49 — you said lower.` + `−60`. The **losing button** gets a danger outline + `✗`; the other stays neutral-disabled. Scorebug score/streak flash danger (streak resets to 0).

### 4. Round Summary (ModalScreen over Game)
- **Trigger:** after every 5th question when the run continues.
- **Modal:** accent border, dark fill `#12100C`, centered, ~64 cells wide.
  - Header: `ROUND 2 · COMPLETE` (accent bold) + `LAL @ DEN` (muted) right.
  - Rule.
  - Row: `✓ 4 right` (success) + `✗ 1 wrong` (danger) left; `round +340` (dim label + success bold signed delta) right.
  - Line: `Next round pulls a different game. Stay hot.` (text).
  - Action: **Continue** `▸ Continue [enter]` — accent fill, black text, single button.
- Game behind is dimmed (~25% opacity / heavy dim).
- **Keys:** Enter continues.

### 5. Game Over (ModalScreen over Game)
- **Trigger:** run ends (arcade miss, or Esc from a finished state).
- **Modal:** danger border, fill `#140F0F`, centered, ~66 cells, centered text.
  - Header: `GAME OVER · arcade` (danger bold + dim mode) + end reason `Wrong Guess` (danger) right.
  - `final score` label (dim, uppercase) → **hero number** `1,450` (highlight, biggest emphasis).
  - Stat row (centered): `✓ 9 right` · `✗ 1 wrong` · `best streak 7`.
  - Flavor line (highlight): `Cooked — but respectable.`
  - Action: **Return home** `▸ Return home [enter / esc]` — text border button (not accent-filled here; it's terminal, not a call to replay).
- **Keys:** Enter or Esc → Home.

### 6. Leaderboard
- **Purpose:** top 10 locally-saved runs.
- **Layout:** header `‹ back  LEADERBOARD · top 10 · this machine`; a table; footer.
- **Table** (use Textual `DataTable` or a grid): columns `# / mode / score / best streak / accuracy / date`. Header row dim uppercase. Rank 1 row highlighted (accent rank, highlight mode, faint fill `#16130C`); alternating rows use `#101216` zebra. Numbers right-aligned. Accuracy in success when ≥75%, else muted.
- **Empty state:** `No runs recorded yet. The board's waiting.`
- **Keys:** Esc back, Q quit.

### 7. Stats
- **Purpose:** aggregate of all saved runs.
- **Layout:** header `‹ back  STATS · every run you've saved`; a 4-up stat card row; a 2-up best row; a per-mode bar breakdown; footer.
- **Components:**
  - Stat cards (border, `padding: 1 2`): `runs 42`, `questions 610`, `correct 471` (success value), `accuracy 77.2%` (success value, one decimal). Label dim uppercase, value bold large-emphasis.
  - Best row: `best score 2,150` (highlight), `best streak 11` (highlight).
  - **By mode** bars: `endless / arcade / historical` label + a horizontal bar (accent fill over `raised` track, proportion = mode's share) + count. In a terminal, draw bars with block chars `█`/`░` or a Textual `ProgressBar` styled to accent.
- **Empty state (mode breakdown):** `No runs yet — go make some regrettable guesses.`
- **Keys:** Esc back, Q quit.

---

## Interactions & Behavior
- **Focus:** the focused widget switches to a **solid accent fill + contrasting (near-black) text + bold**; all others are hairline outline + muted label. Because focus must survive 16-color/no-color terminals, the fill/`reverse` change is the primary signal, color is secondary. Menu focus moves with ↑/↓; the two Game buttons with ←/→.
- **The 1.2s reveal:** guess → disable both buttons immediately → flip hidden number + recolor B's card (success/danger) + drop verdict strip + flash scorebug → hold 1.2s (`set_timer(1.2, ...)`) → advance to next question or push a modal. Nothing is clickable during the hold.
- **Loading:** 1s `set_interval` drives both the spinner frame and the escalating message; store `elapsed` seconds. Esc calls the fetch's cancel/`worker.cancel()`.
- **Errors:** surface via `notify(severity="error")` toast (title + message), reset screen to idle.
- **Responsive:** see below.
- **Reduced motion / no color:** spinner and blink are decorative; the app must be fully readable if a terminal ignores them.

## State Management
Per the existing spec (behavior is unchanged — only the visuals are redesigned):
- **Run state:** `mode`, `round`, `question_index` (Q x/5), `score`, `streak`, `best_streak`, `correct_count`, `wrong_count`, `active_game_index`, list of playable games for the date, `last_guess` record (A name+pts, direction, B name+pts, verdict, delta).
- **Question state:** current A line (name, team, pts, min), current B line (name, team, hidden pts, min), the comparison chain reference.
- **Screen state (Mode Select):** `idle | loading | error`, `elapsed_seconds`, `selected_mode`.
- **Reveal state (Game):** `awaiting_guess | revealing`, `revealed_value`, `was_correct`, `score_delta`.
- **Scoring (must match `scoring.py`):** Endless +100 / −60; Arcade +150 / 0 (run ends on wrong); Historical +100 / −60. Arcade ends on first wrong; Endless/Historical continue.
- **Persistence:** leaderboard + stats saved locally per machine. Data source may be live (stats.nba.com, ~45s timeout) or a mock source. Theme choice (dark/light) persists per machine.

## Responsive behavior
Breakpoints match the app: **lg ≥128 · md 96–127 · sm 72–95 · xs <72** (width); heights **xs <24 · sm 24–31 · md 32–39 · lg ≥40**. Use Textual's `App.get_css_variables` / watch on `self.size` or CSS media-like `Screen` classes toggled on resize.

Degradation order for the **Game** screen (drop in this order as width shrinks; matchup + both action buttons NEVER drop):
1. **sm:** games strip collapses to `active + game N/total`; scorebug + footer abbreviate (`ENDLESS`→`E`, `←/→ move`→`←/→`); matchup stays side-by-side; buttons keep full `HIGHER`/`LOWER` labels; team-min shortens `37 min`→`37m`.
2. **xs:** games strip **and** last-guess line **dropped**; the two players **stack vertically** into compact rows (`A LeBron James  LAL  34p` / `— vs —` / `B Nikola Jokić  DEN  ——p`); buttons shrink to `▲ HI · H` / `▼ LO · L`.
3. **short height:** the game body scrolls (`overflow-y: auto` on the content container) while scorebug, buttons, and footer stay pinned.

Verdict strip and both modals stay full-priority at every size.

## Assets
None. No images, icons, or fonts ship — the design is pure text + Textual borders + Unicode glyphs (`▲ ▼ ▸ ‹ ✓ ✗ ★ ›` and braille spinner frames). Keep emoji out; Unicode width is unreliable across terminals — the glyphs used here are all single-width and safe.

## Files
- `Hoop Higher TUI v2.dc.html` — the full design reference (all screens/states, dark + light, responsive tiers, color system, and interaction spec). Open in a browser to view. This is the authoritative visual source; this README is the implementation contract.
