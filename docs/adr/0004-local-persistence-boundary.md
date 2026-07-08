# Local persistence boundary

SQLite local persistence stores run history, leaderboard data, aggregateable stats, answered questions, and cached external NBA data. The active run is still orchestrated in memory by the service layer and persisted incrementally, so the database is a durable record and cache rather than the gameplay engine.
