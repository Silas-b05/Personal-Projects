PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    muscle_group TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workout_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS template_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    position INTEGER NOT NULL,
    target_sets INTEGER NOT NULL DEFAULT 3 CHECK (target_sets > 0),
    target_reps TEXT NOT NULL DEFAULT '8-12',
    UNIQUE (template_id, exercise_id),
    UNIQUE (template_id, position)
);

CREATE TABLE IF NOT EXISTS machine_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    setting_name TEXT NOT NULL,
    setting_value TEXT NOT NULL,
    UNIQUE (gym_id, exercise_id, setting_name)
);

-- `machine_settings` above is retained as a read-only legacy table so existing
-- installations can be migrated without replacing or deleting any saved data.
CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (gym_id, exercise_id, name)
);

CREATE TABLE IF NOT EXISTS machine_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    setting_name TEXT NOT NULL COLLATE NOCASE,
    setting_value TEXT NOT NULL,
    UNIQUE (machine_id, setting_name)
);

CREATE TABLE IF NOT EXISTS workout_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE RESTRICT,
    template_id INTEGER NOT NULL REFERENCES workout_templates(id) ON DELETE RESTRICT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workout_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    set_number INTEGER NOT NULL CHECK (set_number > 0),
    weight REAL NOT NULL CHECK (weight >= 0),
    reps INTEGER NOT NULL CHECK (reps >= 0),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (session_id, exercise_id, set_number)
);

CREATE TABLE IF NOT EXISTS session_exercise_machines (
    session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    PRIMARY KEY (session_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_started_at
    ON workout_sessions(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sets_exercise_session
    ON workout_sets(exercise_id, session_id);

CREATE INDEX IF NOT EXISTS idx_machines_gym_exercise
    ON machines(gym_id, exercise_id);

CREATE INDEX IF NOT EXISTS idx_session_exercise_machine
    ON session_exercise_machines(machine_id, exercise_id, session_id);
