DROP TABLE IF EXISTS models;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS statistics;
DROP TABLE IF EXISTS benchmarks;
DROP TABLE IF EXISTS correlations;

CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    season_year INTEGER NOT NULL,
    made_playoffs BOOLEAN NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    ties INTEGER NOT NULL,
    FOREIGN KEY (model_id) REFERENCES models (id) ON DELETE CASCADE
);

CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    value REAL NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
);

CREATE TABLE benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    mean_value REAL NOT NULL,
    median_value REAL NOT NULL,
    std_dev REAL,
    min_value REAL,
    max_value REAL,
    FOREIGN KEY (model_id) REFERENCES models (id) ON DELETE CASCADE
);

CREATE TABLE correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    category1 TEXT NOT NULL,
    category2 TEXT NOT NULL,
    coefficient REAL NOT NULL,
    FOREIGN KEY (model_id) REFERENCES models (id) ON DELETE CASCADE
);