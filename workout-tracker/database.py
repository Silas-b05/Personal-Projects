from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import libsql


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


def connect() -> Any:
    database_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")
    if not database_url or not auth_token:
        raise RuntimeError(
            "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must both be set."
        )
    connection = libsql.connect(database=database_url, auth_token=auth_token)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _rows(query: str, parameters: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with connect() as connection:
        cursor = connection.execute(query, tuple(parameters))
        columns = [description[0] for description in cursor.description or ()]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _execute(query: str, parameters: Iterable[Any] = ()) -> int:
    with connect() as connection:
        cursor = connection.execute(query, tuple(parameters))
        row = cursor.fetchone() if cursor.description else None
        connection.commit()
        return int(row[0]) if row else 0


def list_gyms() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM gyms ORDER BY name COLLATE NOCASE")


def add_gym(name: str, notes: str = "") -> int:
    return _execute(
        "INSERT INTO gyms(name, notes) VALUES (?, ?) RETURNING id",
        (name.strip(), notes.strip()),
    )


def delete_gym(gym_id: int) -> None:
    _execute("DELETE FROM gyms WHERE id = ?", (gym_id,))


def list_exercises() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM exercises ORDER BY name COLLATE NOCASE")


def add_exercise(name: str, muscle_group: str = "", notes: str = "") -> int:
    return _execute(
        "INSERT INTO exercises(name, muscle_group, notes) VALUES (?, ?, ?) RETURNING id",
        (name.strip(), muscle_group.strip(), notes.strip()),
    )


def delete_exercise(exercise_id: int) -> None:
    _execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))


def list_templates() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM workout_templates ORDER BY name COLLATE NOCASE")


def add_template(name: str, notes: str = "") -> int:
    return _execute(
        "INSERT INTO workout_templates(name, notes) VALUES (?, ?) RETURNING id",
        (name.strip(), notes.strip()),
    )


def delete_template(template_id: int) -> None:
    _execute("DELETE FROM workout_templates WHERE id = ?", (template_id,))


def list_template_exercises(template_id: int) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT te.id, te.template_id, te.exercise_id, te.position,
               te.target_sets, te.target_reps, e.name AS exercise_name
        FROM template_exercises AS te
        JOIN exercises AS e ON e.id = te.exercise_id
        WHERE te.template_id = ?
        ORDER BY te.position
        """,
        (template_id,),
    )


def add_template_exercise(
    template_id: int,
    exercise_id: int,
    target_sets: int,
    target_reps: str,
) -> int:
    with connect() as connection:
        position = connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM template_exercises WHERE template_id = ?",
            (template_id,),
        ).fetchone()[0]
        cursor = connection.execute(
            """
            INSERT INTO template_exercises(
                template_id, exercise_id, position, target_sets, target_reps
            ) VALUES (?, ?, ?, ?, ?) RETURNING id
            """,
            (template_id, exercise_id, position, target_sets, target_reps.strip()),
        )
        row = cursor.fetchone()
        connection.commit()
        return int(row[0])


def remove_template_exercise(template_exercise_id: int) -> None:
    with connect() as connection:
        row = connection.execute(
            "SELECT template_id, position FROM template_exercises WHERE id = ?",
            (template_exercise_id,),
        ).fetchone()
        if row is None:
            return
        connection.execute("DELETE FROM template_exercises WHERE id = ?", (template_exercise_id,))
        connection.execute(
            """
            UPDATE template_exercises
            SET position = position - 1
            WHERE template_id = ? AND position > ?
            """,
            (row[0], row[1]),
        )
        connection.commit()


def list_machine_settings(
    gym_id: int | None = None,
    exercise_id: int | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    parameters: list[Any] = []
    if gym_id is not None:
        conditions.append("ms.gym_id = ?")
        parameters.append(gym_id)
    if exercise_id is not None:
        conditions.append("ms.exercise_id = ?")
        parameters.append(exercise_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return _rows(
        f"""
        SELECT ms.*, g.name AS gym_name, e.name AS exercise_name
        FROM machine_settings AS ms
        JOIN gyms AS g ON g.id = ms.gym_id
        JOIN exercises AS e ON e.id = ms.exercise_id
        {where}
        ORDER BY g.name COLLATE NOCASE, e.name COLLATE NOCASE,
                 ms.setting_name COLLATE NOCASE
        """,
        parameters,
    )


def save_machine_setting(
    gym_id: int,
    exercise_id: int,
    setting_name: str,
    setting_value: str,
) -> int:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO machine_settings(gym_id, exercise_id, setting_name, setting_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(gym_id, exercise_id, setting_name)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            (gym_id, exercise_id, setting_name.strip(), setting_value.strip()),
        )
        row = connection.execute(
            """
            SELECT id FROM machine_settings
            WHERE gym_id = ? AND exercise_id = ? AND setting_name = ?
            """,
            (gym_id, exercise_id, setting_name.strip()),
        ).fetchone()
        connection.commit()
        return int(row[0])


def delete_machine_setting(setting_id: int) -> None:
    _execute("DELETE FROM machine_settings WHERE id = ?", (setting_id,))


def create_session(gym_id: int, template_id: int) -> int:
    return _execute(
        """
        INSERT INTO workout_sessions(gym_id, template_id, started_at)
        VALUES (?, ?, ?) RETURNING id
        """,
        (gym_id, template_id, datetime.now().astimezone().isoformat(timespec="seconds")),
    )


def get_session(session_id: int) -> dict[str, Any] | None:
    rows = _rows(
        """
        SELECT ws.*, g.name AS gym_name, wt.name AS template_name
        FROM workout_sessions AS ws
        JOIN gyms AS g ON g.id = ws.gym_id
        JOIN workout_templates AS wt ON wt.id = ws.template_id
        WHERE ws.id = ?
        """,
        (session_id,),
    )
    return rows[0] if rows else None


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT ws.id, ws.started_at, ws.finished_at,
               g.name AS gym_name, wt.name AS template_name,
               COUNT(wset.id) AS recorded_sets
        FROM workout_sessions AS ws
        JOIN gyms AS g ON g.id = ws.gym_id
        JOIN workout_templates AS wt ON wt.id = ws.template_id
        LEFT JOIN workout_sets AS wset ON wset.session_id = ws.id
        GROUP BY ws.id
        ORDER BY ws.started_at DESC
        LIMIT ?
        """,
        (limit,),
    )


def list_session_sets(session_id: int, exercise_id: int) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT * FROM workout_sets
        WHERE session_id = ? AND exercise_id = ?
        ORDER BY set_number
        """,
        (session_id, exercise_id),
    )


def previous_sets(
    session_id: int,
    gym_id: int,
    exercise_id: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    sessions = _rows(
        """
        SELECT DISTINCT ws.id, ws.started_at
        FROM workout_sessions AS ws
        JOIN workout_sets AS wset ON wset.session_id = ws.id
        WHERE ws.id != ? AND ws.gym_id = ? AND wset.exercise_id = ?
        ORDER BY ws.started_at DESC
        LIMIT 1
        """,
        (session_id, gym_id, exercise_id),
    )
    if not sessions:
        return None, []
    previous_session = sessions[0]
    return previous_session, list_session_sets(previous_session["id"], exercise_id)


def save_exercise_sets(
    session_id: int,
    exercise_id: int,
    sets: list[tuple[int, float, int]],
) -> None:
    with connect() as connection:
        connection.execute(
            "DELETE FROM workout_sets WHERE session_id = ? AND exercise_id = ?",
            (session_id, exercise_id),
        )
        connection.executemany(
            """
            INSERT INTO workout_sets(session_id, exercise_id, set_number, weight, reps)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (session_id, exercise_id, set_number, weight, reps)
                for set_number, weight, reps in sets
            ],
        )
        connection.commit()


def finish_session(session_id: int, notes: str = "") -> None:
    _execute(
        "UPDATE workout_sessions SET finished_at = ?, notes = ? WHERE id = ?",
        (datetime.now().astimezone().isoformat(timespec="seconds"), notes.strip(), session_id),
    )
