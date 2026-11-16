"""Reproducible simulated-latency benchmark, not a production speed claim.

Run from workout-tracker: python tests/benchmark_loading.py
"""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database as db
from test_page_loading import PageLoadingTests


def original_load(session_id):
    session = db.get_session(session_id)
    for item in db.list_template_exercises(session['template_id']):
        eid = item['exercise_id']
        machines = db.list_machines(session['gym_id'], eid)
        machine = db.suggested_machine(session_id, session['gym_id'], eid)
        if machine not in [m['id'] for m in machines]:
            machine = machines[0]['id'] if machines else None
        if machine is not None:
            db.list_machine_settings(machine)
        db.previous_sets(session_id, session['gym_id'], eid, machine)
        db.list_session_sets(session_id, eid)


if __name__ == '__main__':
    fixture = PageLoadingTests()
    fixture.setUp()
    original_query = db._query_rows

    def delayed_query(*args, **kwargs):
        time.sleep(0.02)  # Model 20 ms per read, not measured Turso latency.
        return original_query(*args, **kwargs)

    try:
        for name, loader in [('Original', original_load), ('Optimized', db.load_workout)]:
            fixture.mock_connect.reset_mock()
            with patch.object(db, '_query_rows', side_effect=delayed_query) as query:
                started = time.perf_counter()
                loader(6)
                elapsed = time.perf_counter() - started
                print(f'{name}: {query.call_count} reads, {fixture.mock_connect.call_count} connections, '
                      f'{elapsed:.3f}s with simulated 20ms/read latency')
    finally:
        fixture.doCleanups()
