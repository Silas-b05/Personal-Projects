"""Template ordering tests using isolated in-memory databases, never Turso."""
import itertools
import sqlite3
import unittest
from unittest.mock import patch

import libsql

import database as db


class TemplateOrderTests(unittest.TestCase):
    connection_factory = staticmethod(lambda: sqlite3.connect(":memory:"))

    def setUp(self):
        self.connection = self.connection_factory()
        self.connection.executescript(db.SCHEMA_PATH.read_text())
        self.connection.executescript("""
            INSERT INTO gyms(id, name) VALUES (1, 'Gym');
            INSERT INTO exercises(id, name) VALUES
                (1, 'Bench'), (2, 'Fly'), (3, 'Incline Bench'), (4, 'Dips'), (5, 'Press');
            INSERT INTO workout_templates(id, name) VALUES (1, 'Push A'), (2, 'Push B');
            INSERT INTO template_exercises
                (id, template_id, exercise_id, position, target_sets, target_reps)
                VALUES (1, 1, 1, 1, 3, '8-12'), (2, 1, 2, 2, 4, '10'),
                       (3, 1, 3, 3, 2, '6-8'), (4, 1, 4, 4, 3, '12'),
                       (5, 2, 1, 1, 5, '5');
            INSERT INTO workout_sessions(id, gym_id, template_id, started_at)
                VALUES (1, 1, 1, '2026-11-16');
            INSERT INTO workout_sets(session_id, exercise_id, set_number, weight, reps)
                VALUES (1, 1, 1, 60, 10);
        """)
        self.connection.commit()
        self.addCleanup(self.connection.close)
        patcher = patch.object(db, "connect", return_value=self.connection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def order(self):
        return [item['id'] for item in db.list_template_exercises(1)]

    def test_every_permutation_and_preserved_content(self):
        content = self.connection.execute(
            'SELECT id, exercise_id, target_sets, target_reps FROM template_exercises ORDER BY id'
        ).fetchall()
        history = self.connection.execute('SELECT * FROM workout_sets').fetchall()
        current = self.order()
        for permutation in itertools.permutations(current):
            desired = list(permutation)
            db.reorder_template_exercises(1, desired, current)
            self.assertEqual(self.order(), desired)
            self.assertEqual([item['position'] for item in db.list_template_exercises(1)], [1, 2, 3, 4])
            current = desired
        self.assertEqual(self.connection.execute(
            'SELECT id, exercise_id, target_sets, target_reps FROM template_exercises ORDER BY id'
        ).fetchall(), content)
        self.assertEqual(self.connection.execute('SELECT * FROM workout_sets').fetchall(), history)
        self.assertEqual(db.list_template_exercises(2)[0]['position'], 1)

    def test_rejects_stale_partial_duplicate_and_foreign_items(self):
        for desired in ([1, 2, 3], [1, 1, 2, 3], [1, 2, 3, 5]):
            with self.assertRaises(ValueError):
                db.reorder_template_exercises(1, desired, [1, 2, 3, 4])
            self.assertEqual(self.order(), [1, 2, 3, 4])
        db.reorder_template_exercises(1, [4, 3, 2, 1], [1, 2, 3, 4])
        with self.assertRaises(ValueError):
            db.reorder_template_exercises(1, [2, 1, 3, 4], [1, 2, 3, 4])
        self.assertEqual(self.order(), [4, 3, 2, 1])

    def test_failure_rolls_back_temporary_positions(self):
        self.connection.execute("""CREATE TRIGGER fail_reorder BEFORE UPDATE ON template_exercises
            WHEN NEW.position = 2 BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        self.connection.commit()
        with self.assertRaises(Exception):
            db.reorder_template_exercises(1, [4, 3, 2, 1], [1, 2, 3, 4])
        self.assertEqual(self.order(), [1, 2, 3, 4])
        self.assertEqual([item['position'] for item in db.list_template_exercises(1)], [1, 2, 3, 4])

    def test_remove_after_reorder_then_append(self):
        db.reorder_template_exercises(1, [4, 3, 2, 1], [1, 2, 3, 4])
        db.remove_template_exercise(4)
        self.assertEqual(self.order(), [3, 2, 1])
        self.assertEqual([item['position'] for item in db.list_template_exercises(1)], [1, 2, 3])
        new_id = db.add_template_exercise(1, 5, 3, '8-12')
        self.assertEqual(self.order(), [3, 2, 1, new_id])


class LibsqlTemplateOrderTests(TemplateOrderTests):
    connection_factory = staticmethod(lambda: libsql.connect(":memory:"))


if __name__ == '__main__':
    unittest.main()
