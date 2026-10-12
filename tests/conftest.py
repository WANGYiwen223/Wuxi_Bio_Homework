import sqlite3

import pytest

from scripts.demo_data import COLLECTIONS, load_scenario, validate_scenario


@pytest.fixture
def seeded_db(tmp_path):
    def make(name="baseline"):
        scenario, records = load_scenario(name)
        validate_scenario(scenario, records)
        path = tmp_path / f"{name}.sqlite"
        import json
        with sqlite3.connect(path) as db:
            for collection, rows in records.items():
                key = COLLECTIONS[collection][0]
                db.execute(f"CREATE TABLE {collection} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                db.executemany(f"INSERT INTO {collection} VALUES (?, ?)", [(row[key], json.dumps(row)) for row in rows])
        return path, scenario
    return make
