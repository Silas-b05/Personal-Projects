"""Read-only filter regression tests; never connect to a real Turso database."""
import sqlite3
import unittest
from unittest.mock import patch

import database as db


class MachineFilterTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(db.SCHEMA_PATH.read_text())
        self.connection.executescript("""
            INSERT INTO gyms(id, name) VALUES (1, 'Alpha gym'), (2, 'Beta gym');
            INSERT INTO exercises(id, name) VALUES
                (1, 'Lateral Raises'), (2, 'Leg Press'), (3, 'Squats');
            INSERT INTO machines(id, gym_id, exercise_id, name) VALUES
                (1, 1, 1, 'Cable station'), (2, 2, 1, 'Cable station'),
                (3, 1, 2, 'Leg machine');
            INSERT INTO machine_adjustments(machine_id, setting_name, setting_value)
                VALUES (1, 'Seat', '4'), (1, 'Arm', '2'), (3, 'Seat', '8');
        """)
        self.mock_connect = patch.object(db, "connect", return_value=self.connection)
        self.connect = self.mock_connect.start()
        self.addCleanup(self.mock_connect.stop)
        self.addCleanup(self.connection.close)

    def test_filtered_machines_and_adjustments_in_one_query(self):
        before = self.connection.total_changes
        with patch.object(db, "_rows", wraps=db._rows) as query:
            machines = db.machines_for_settings(1)
            query.assert_called_once()
        self.connect.assert_called_once()
        self.assertEqual([m["id"] for m in machines], [1, 2])
        self.assertEqual([s["setting_name"] for s in machines[0]["settings"]],
                         ["Arm", "Seat"])
        self.assertEqual(machines[1]["settings"], [])
        self.assertEqual(self.connection.total_changes, before)

    def test_switch_exercise_and_no_matches(self):
        machines = db.machines_for_settings(2)
        self.assertEqual([m["id"] for m in machines], [3])
        self.assertEqual(machines[0]["settings"][0]["setting_value"], "8")
        self.assertEqual(db.machines_for_settings(3), [])
        self.assertEqual(db.machines_for_settings(999), [])


if __name__ == "__main__":
    unittest.main()
