"""Tests for the persistent local OSM healthcare facility store."""

import json
import sqlite3
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import healthcare_store
from app.healthcare_store import database_status, import_facilities, initialize_database, search_local_facilities


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

    def test_empty_default_database_seeds_from_bundled_snapshot(self):
        bundled_snapshot = Path(self.temp_dir.name) / "snapshot.json"
        bundled_snapshot.write_text(json.dumps({
            "dataset_source": "Fixture OSM extract",
            "dataset_last_updated": "2026-11-18T00:00:00Z",
            "attribution": "OpenStreetMap contributors",
            "facilities": [{
                "osm_type": "node", "osm_id": 101, "name": "Snapshot Clinic",
                "category": "clinic", "lat": 23.78, "lon": 90.41, "address": "Dhaka",
            }],
        }), encoding="utf-8")
        with patch.object(healthcare_store, "DB_PATH", self.db_path), \
                patch.object(healthcare_store, "SNAPSHOT_PATH", bundled_snapshot):
            initialize_database()
            found, metadata = search_local_facilities(23.78, 90.41, 1000, "clinic")
            status = database_status()
        self.assertEqual([row["name"] for row in found], ["Snapshot Clinic"])
        self.assertEqual(metadata["dataset_source"], "Fixture OSM extract")
        self.assertEqual(status, {
            "database_available": True, "initialized": True, "facility_count": 1,
            "local_search_available": True,
        })

    def test_packaged_snapshot_contains_attributed_imported_osm_rows(self):
        snapshot = json.loads(healthcare_store.SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["dataset_source"], "OpenStreetMap Bangladesh extract")
        self.assertEqual(len(snapshot["facilities"]), 7524)
        self.assertIn("OpenStreetMap contributors", snapshot["attribution"])
        self.assertEqual(
            {row["category"] for row in snapshot["facilities"]},
            {"hospital", "clinic", "pharmacy", "doctors"},
        )

    def test_database_diagnostics_report_unavailable_storage(self):
        status = database_status(Path(self.temp_dir.name) / "missing.sqlite3")
        self.assertEqual(status, {
            "database_available": False, "initialized": False, "facility_count": 0,
            "local_search_available": False,
        })

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
        environment["CAREANYWHERE_HEALTHCARE_SNAPSHOT_PATH"] = str(Path(self.temp_dir.name) / "missing-snapshot.json")
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
