# Layer boundaries for gameplay

Hoop Higher keeps domain code responsible for pure gameplay concepts and rules, services responsible for orchestrating runs across stats sources and persistence, data code responsible for APIs/cache/SQLite, and TUI code responsible for rendering state and sending user intent. This boundary prevents Textual, persistence, and provider concerns from leaking into scoring, difficulty, question generation, and other core game behavior.
