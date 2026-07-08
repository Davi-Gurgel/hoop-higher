# Hoop Higher

Hoop Higher is the game context for comparing NBA player scoring lines. This language defines the concepts used by players and contributors when discussing rules, data, and progress.

## Language

**Run**:
A continuous attempt played in one mode, accumulating score, correct answers, wrong answers, and best streak until an end condition. A run can span one or more rounds.
_Avoid_: Session, game, campaign

**NBA Game**:
A real NBA event used as the source of player lines for a round. An NBA game belongs to a date and includes teams, scores, and available individual scoring lines.
_Avoid_: Game, box score, game context

**Playable NBA Game**:
An NBA game with enough eligible player lines to generate a round with the requested number of questions.
_Avoid_: Valid game, available game, complete game

**Round**:
A block of questions generated from a single NBA game. A round has between 5 and 10 questions and ends when all of them have been answered.
_Avoid_: Phase, level

**Comparison Chain**:
A sequence of questions where the player revealed by one answer becomes the known reference for the next question. The chain creates continuity within a round and keeps questions from feeling isolated.
_Avoid_: Question list, independent pairs, random sequence

**Player Line**:
The statistical performance of an NBA player in one NBA game, including their points and recorded participation. The same NBA player can have different player lines in different NBA games.
_Avoid_: Player, stats, box score line

**NBA Player**:
A person who participated in an NBA game and can appear in questions through their player lines.
_Avoid_: Athlete, app player

**Hoop Higher Player**:
The person playing Hoop Higher, making guesses and accumulating score in runs.
_Avoid_: User, player, competitor

**Eligible Player Line**:
A player line that can participate in questions because the NBA player entered the NBA game. Lines without recorded participation are not used.
_Avoid_: Active player, valid player, valid line

**Question**:
A comparison between two player lines from the same NBA game. The first point total is known and the second is hidden until the Hoop Higher player chooses whether it was higher or lower.
_Avoid_: Trivia, challenge

**Guess**:
The Hoop Higher player's choice for a question, indicating whether the hidden point total was higher or lower than the known point total.
_Avoid_: Answer, choice

**Question Result**:
The record of a question after the guess, including whether the Hoop Higher player was correct, the revealed point total, and the impact on the run score.
_Avoid_: Answer, solution, feedback

**Endless Mode**:
A mode where the run continues after wrong guesses. Correct guesses increase the score and wrong guesses reduce it.
_Avoid_: Free mode, practice

**Arcade Mode**:
A mode where the run ends on the first wrong guess. Correct guesses are worth more than in modes without immediate elimination.
_Avoid_: Sudden death, elimination mode, hardcore

**Historical Mode**:
A mode where the run uses NBA games from historical dates selected by the system. Wrong guesses do not end the run.
_Avoid_: Classic, retro

**Score**:
The accumulated point total for a run, changed by each question result according to the selected mode.
_Avoid_: Total points

**Streak**:
The number of consecutive correct guesses within a run. The best streak is the highest streak reached in that run.
_Avoid_: Combo, series

**Question Difficulty**:
A classification based on the difference between the compared point totals. The smaller the difference, the harder the question.
_Avoid_: Level, rarity, player difficulty

**Stats Source**:
The origin of the NBA games and player lines used by the game. A stats source may fetch real data or provide simulated data, but it must provide equivalent domain concepts.
_Avoid_: Provider, API, backend

**Leaderboard**:
A list of the best locally saved runs, ordered by score and used to compare player performance.
_Avoid_: Ranking, table, overall score

**Player Stats**:
An aggregate summary of locally saved runs, including play volume, correct guesses, accuracy rate, best score, best streak, and mode distribution.
_Avoid_: Analytics, metrics

**Source Date**:
The date of the NBA games used as the source for a run. In Historical Mode, the run uses one source date selected by the system.
_Avoid_: Game date, historical date
