"""Tests for the persistent local OSM healthcare facility store."""

import sqlite3
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.healthcare_store import import_facilities, initialize_database, search_local_facilities


class HealthcareStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "healthcare.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initializes_with_location_indexes(self):
        initialize_database(self.db_path)
        self.assertTrue(self.db_path.exists())
        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("healthcare_facilities", tables)
        self.assertIn("nearby_osm_cache", tables)
        self.assertIn("idx_healthcare_facilities_lat_lon", indexes)
        self.assertIn("idx_healthcare_facilities_category_lat_lon", indexes)

    def test_import_and_search_filter_by_category_and_exact_radius(self):
        records = [
            {"osm_type": "node", "osm_id": 1, "name": "Central Hospital", "category": "hospital", "lat": 23.780, "lon": 90.410},
            {"osm_type": "way", "osm_id": 2, "name": "Nearby Clinic", "category": "clinic", "lat": 23.784, "lon": 90.410},
            {"osm_type": "relation", "osm_id": 3, "name": "Far Pharmacy", "category": "pharmacy", "lat": 23.800, "lon": 90.410},
            {"osm_type": "node", "osm_id": 4, "name": "Nearby Doctor", "category": "doctors", "lat": 23.781, "lon": 90.411},
        ]
        count = import_facilities(
            records,
            dataset_source="test Bangladesh extract",
            imported_at="2026-11-17T00:00:00+00:00",
            db_path=self.db_path,
        )
        self.assertEqual(count, len(records))

        local, metadata = search_local_facilities(23.780, 90.410, 1000, "all", db_path=self.db_path)
        self.assertEqual({item["category"] for item in local}, {"hospital", "clinic", "doctors"})
        self.assertNotIn("Far Pharmacy", {item["name"] for item in local})
        self.assertEqual(metadata["dataset_source"], "test Bangladesh extract")
        self.assertEqual(metadata["dataset_last_updated"], "2026-11-17T00:00:00+00:00")

        hospitals, _ = search_local_facilities(23.780, 90.410, 1000, "hospital", db_path=self.db_path)
        pharmacies, _ = search_local_facilities(23.780, 90.410, 1000, "pharmacy", db_path=self.db_path)
        self.assertEqual([item["name"] for item in hospitals], ["Central Hospital"])
        self.assertEqual(pharmacies, [])

    def test_facility_rows_survive_database_reinitialization(self):
        record = {"osm_type": "node", "osm_id": 51, "name": "Saved Pharmacy", "category": "pharmacy", "lat": 23.78, "lon": 90.41}
        import_facilities([record], dataset_source="test snapshot", db_path=self.db_path)
        # A new connection after initialization simulates a new application process.
        initialize_database(self.db_path)
        facilities, metadata = search_local_facilities(23.78, 90.41, 1000, "pharmacy", db_path=self.db_path)
        self.assertEqual(facilities[0]["name"], "Saved Pharmacy")
        self.assertTrue(metadata["dataset_last_updated"])

    def test_imported_records_survive_a_new_python_process(self):
        record = {"osm_type": "way", "osm_id": 91, "name": "Persistent Clinic", "category": "clinic", "lat": 23.78, "lon": 90.41}
        import_facilities([record], dataset_source="test snapshot", db_path=self.db_path)
        environment = os.environ.copy()
        environment["CAREANYWHERE_HEALTHCARE_DB_PATH"] = str(self.db_path)
        check = (
            "import sys; from app.healthcare_store import search_local_facilities; "
            "rows, meta = search_local_facilities(23.78, 90.41, 1000, 'clinic'); "
            "print(rows[0]['name'] if rows else 'missing')"
        )
        output = subprocess.check_output(
            [sys.executable, "-c", check],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            text=True,
        ).strip()
        self.assertEqual(output, "Persistent Clinic")


if __name__ == "__main__":
    unittest.main()
