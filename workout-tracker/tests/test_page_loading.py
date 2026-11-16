"""Parity and query-count checks against the original read helpers, without Turso."""
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import libsql
import database as db


class PageLoadingTests(unittest.TestCase):
    connection_factory = staticmethod(lambda: sqlite3.connect(":memory:"))

    def setUp(self):
        self.connection = self.connection_factory()
        self.connection.executescript(db.SCHEMA_PATH.read_text())
        self.connection.executescript("""
            INSERT INTO gyms(id, name) VALUES (1, 'Alpha'), (2, 'Beta');
            INSERT INTO workout_templates(id, name) VALUES (1, 'Push'), (2, 'Empty');
        """)
        for i in range(1, 9):
            self.connection.execute('INSERT INTO exercises(id, name) VALUES (?, ?)', (i, f'Exercise {i}'))
            self.connection.execute('INSERT INTO template_exercises(template_id, exercise_id, position) VALUES (1, ?, ?)', (i, i))
            if i == 8:  # Also exercise with no machines.
                continue
            for machine_id, gym_id in ((i * 10, 1), (i * 10 + 1, 1), (i * 10 + 2, 2)):
                self.connection.execute('INSERT INTO machines(id, gym_id, exercise_id, name) VALUES (?, ?, ?, ?)',
                                        (machine_id, gym_id, i, f'Machine {machine_id}'))
                self.connection.execute('INSERT INTO machine_adjustments(machine_id, setting_name, setting_value) VALUES (?, ?, ?)',
                                        (machine_id, 'Seat', str(machine_id)))
        for sid in range(1, 7):
            self.connection.execute('INSERT INTO workout_sessions(id, gym_id, template_id, started_at) VALUES (?, ?, 1, ?)',
                                    (sid, 2 if sid == 5 else 1, f'2026-01-0{sid}T12:00:00'))
            for i in range(1, 9):
                if sid == 6 and i > 2:
                    continue  # Current workout may have no sets yet.
                self.connection.execute('INSERT INTO workout_sets(session_id, exercise_id, set_number, weight, reps) VALUES (?, ?, 1, ?, ?)',
                                        (sid, i, sid * 10 + i, sid + i))
                if i < 8 and sid in (2, 4, 5, 6):
                    self.connection.execute('INSERT INTO session_exercise_machines(session_id, exercise_id, machine_id) VALUES (?, ?, ?)',
                                            (sid, i, i * 10 + {2: 0, 4: 1, 5: 2, 6: 0}[sid]))
        self.connection.commit()
        self.addCleanup(self.connection.close)
        patcher = patch.object(db, 'connect', return_value=self.connection)
        self.mock_connect = patcher.start()
        self.addCleanup(patcher.stop)

    def test_workout_matches_original_reads(self):
        before = self.connection.execute('SELECT * FROM workout_sets ORDER BY id').fetchall()
        data = db.load_workout(6)
        self.assertEqual(data['session'], db.get_session(6))
        expected_items = db.list_template_exercises(1)
        for actual, expected in zip(data['items'], expected_items, strict=True):
            for key in expected:
                self.assertEqual(actual[key], expected[key])
            eid = actual['exercise_id']
            machines = db.list_machines(1, eid)
            self.assertEqual([m['id'] for m in actual['machines']], [m['id'] for m in machines])
            for machine in actual['machines']:
                self.assertEqual(machine['settings'], [
                    {key: setting[key] for key in ('setting_name', 'setting_value')}
                    for setting in db.list_machine_settings(machine['id'])
                ])
            suggested = db.suggested_machine(6, 1, eid)
            valid_ids = [m['id'] for m in machines]
            if suggested not in valid_ids:
                suggested = valid_ids[0] if valid_ids else None
            self.assertEqual(actual['selected_machine_id'], suggested)
            self.assertEqual(actual['current_sets'], [
                {key: row[key] for key in ('set_number', 'weight', 'reps')}
                for row in db.list_session_sets(6, eid)
            ])
            for mid in [None, *valid_ids, 99999]:
                previous, sets = db.previous_sets(6, 1, eid, mid)
                self.assertEqual(db.workout_previous_sets(actual, mid), (previous, [
                    {key: row[key] for key in ('set_number', 'weight', 'reps')} for row in sets
                ]))
        self.assertEqual(self.connection.execute('SELECT * FROM workout_sets ORDER BY id').fetchall(), before)

    def test_constant_three_queries_one_connection(self):
        with patch.object(db, '_query_rows', wraps=db._query_rows) as query:
            self.assertEqual(len(db.load_workout(6)['items']), 8)
            self.assertEqual(query.call_count, 3)
        self.mock_connect.assert_called_once()

    def test_scoped_reload_and_missing_session(self):
        full = db.load_workout(6)
        self.assertEqual(db.load_workout(6, 2)['items'], [full['items'][1]])
        self.assertEqual(db.load_workout(999), {'session': None, 'items': []})
        self.assertEqual(db.load_workout(6, 999)['items'], [])

    def test_catalog_matches_old_helpers_in_one_query(self):
        ids = [item['id'] for item in db.list_template_exercises(1)]
        db.reorder_template_exercises(1, list(reversed(ids)), ids)
        with patch.object(db, '_query_rows', wraps=db._query_rows) as query:
            catalog = db.load_catalog(True)
            query.assert_called_once()
        self.assertEqual(catalog['gyms'], db.list_gyms())
        self.assertEqual(catalog['exercises'], db.list_exercises())
        self.assertEqual(catalog['templates'], db.list_templates())
        self.assertEqual(catalog['items_by_template'][1], db.list_template_exercises(1))
        self.assertEqual(db.load_catalog()['items_by_template'], {})

    def test_history_matches_previous_query(self):
        expected = db._rows('''
            SELECT ws.id, ws.started_at, ws.finished_at, g.name AS gym_name,
                   wt.name AS template_name, COUNT(wset.id) AS recorded_sets
            FROM workout_sessions ws JOIN gyms g ON g.id = ws.gym_id
            JOIN workout_templates wt ON wt.id = ws.template_id
            LEFT JOIN workout_sets wset ON wset.session_id = ws.id
            GROUP BY ws.id ORDER BY ws.started_at DESC LIMIT 2
        ''')
        self.assertEqual(db.list_sessions(2), expected)

    def test_new_writes_are_visible_on_next_load(self):
        db.save_exercise_sets(6, 1, [(1, 99, 5)], 11)
        fresh = db.load_workout(6, 1)['items'][0]
        self.assertEqual(fresh['selected_machine_id'], 11)
        self.assertEqual(fresh['current_sets'], [{'set_number': 1, 'weight': 99, 'reps': 5}])
        db.save_machine_setting(11, 'Seat', 'Updated')
        fresh = db.load_workout(6, 1)['items'][0]
        self.assertEqual(fresh['machines'][1]['settings'][0]['setting_value'], 'Updated')

    def test_failed_save_keeps_original_sets_and_machine(self):
        original_sets = db.list_session_sets(6, 1)
        original_machine = db.get_session_machine(6, 1)
        for machine_id, sets in ((12, [(1, 100, 5)]), (11, [(1, 100, -1)])):
            with self.assertRaises(Exception):
                db.save_exercise_sets(6, 1, sets, machine_id)
            self.assertEqual(db.list_session_sets(6, 1), original_sets)
            self.assertEqual(db.get_session_machine(6, 1), original_machine)

    def test_large_and_empty_set_saves(self):
        sets = [(i, float(i), 10) for i in range(1, 205)]
        db.save_exercise_sets(6, 1, sets, 10)
        self.assertEqual(len(db.list_session_sets(6, 1)), 204)
        db.save_exercise_sets(6, 1, [], 10)
        self.assertEqual(db.list_session_sets(6, 1), [])

    def test_machine_setting_upsert_keeps_id(self):
        original_id = db.save_machine_setting(10, 'Seat', '4')
        self.assertEqual(db.save_machine_setting(10, 'seat', '5'), original_id)

    def test_query_reduction_against_original_workout_loader(self):
        with patch.object(db, '_query_rows', wraps=db._query_rows) as query:
            session = db.get_session(6)
            for item in db.list_template_exercises(session['template_id']):
                eid = item['exercise_id']
                machines = db.list_machines(1, eid)
                mid = db.suggested_machine(6, 1, eid)
                if mid not in [m['id'] for m in machines]:
                    mid = machines[0]['id'] if machines else None
                if mid is not None:
                    db.list_machine_settings(mid)
                db.previous_sets(6, 1, eid, mid)
                db.list_session_sets(6, eid)
            old_count = query.call_count
        with patch.object(db, '_query_rows', wraps=db._query_rows) as query:
            db.load_workout(6)
            self.assertEqual(query.call_count, 3)
        self.assertGreaterEqual(old_count, 40)


class LibsqlPageLoadingTests(PageLoadingTests):
    connection_factory = staticmethod(lambda: libsql.connect(":memory:"))


class ConnectionLifecycleTests(unittest.TestCase):
    def test_real_connections_commit_and_rollback_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict('os.environ', {'TURSO_DATABASE_URL': directory + '/test.db',
                                          'TURSO_AUTH_TOKEN': 'test-only'}):
                db.initialize_database()
                gym = db.add_gym('Test')
                exercise = db.add_exercise('Test')
                template = db.add_template('Test')
                db.add_template_exercise(template, exercise, 3, '8-12')
                machine = db.add_machine(gym, exercise, 'Test')
                session = db.create_session(gym, template)
                db.save_exercise_sets(session, exercise, [(1, 10, 8)], machine)
                with self.assertRaises(Exception):
                    db.save_exercise_sets(session, exercise, [(1, -10, 8)], machine)
                data = db.load_workout(session)
                self.assertEqual(data['items'][0]['current_sets'],
                                 [{'set_number': 1, 'weight': 10.0, 'reps': 8}])


if __name__ == '__main__':
    unittest.main()
