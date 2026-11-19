"""Network-free tests for the nearby healthcare provider and cache behavior."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app import healthcare


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {"elements": []}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://provider.example/api/interpreter")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("upstream status", request=request, response=response)

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0
        self.endpoints = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, endpoint, data):
        self.calls += 1
        self.endpoints.append(endpoint)
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class HealthcareFinderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        healthcare._provider_cursor = 0
        healthcare._request_times.clear()

    def _mock_client(self, client):
        return patch.object(healthcare.httpx, "AsyncClient", return_value=client)

    def _cache_path(self, temp_dir):
        return patch.object(healthcare, "CACHE_PATH", Path(temp_dir) / "cache.sqlite3")

    def test_database_is_initialized_during_application_import(self):
        self.assertTrue(healthcare.CACHE_PATH.exists())

    async def test_query_uses_one_spatial_selector_for_all_categories(self):
        query = healthcare._build_query(23.78, 90.41, 3000, "all")
        self.assertEqual(query.count("around:"), 1)
        self.assertIn('"amenity"~"^(hospital|clinic|doctors|pharmacy)$"', query)
        self.assertIn("out center qt;", query)

    async def test_empty_search_keeps_compatible_success_schema(self):
        with patch.object(healthcare.healthcare_store, "search_local_facilities", return_value=([], {})), \
                patch.object(healthcare, "_fetch_elements", return_value=([], "fresh", "overpass", "2026-11-17T00:00:00Z")):
            result = await healthcare.nearby_healthcare(23.78, 90.41, 1000, "all")
        self.assertEqual(result, {
            "radius_m": 1000,
            "category": "all",
            "count": 0,
            "facilities": [],
            "cache_status": "fresh",
            "source": "overpass",
            "is_stale": False,
            "stale": False,
            "last_updated": "2026-11-17T00:00:00Z",
            "local_database_available": True,
            "local_match_count": 0,
        })

    async def test_endpoint_marks_stale_results_explicitly(self):
        facility = {
            "type": "node", "id": 7, "lat": 23.78, "lon": 90.41,
            "tags": {"amenity": "hospital", "name": "Mapped Hospital"},
        }
        with patch.object(healthcare.healthcare_store, "search_local_facilities", return_value=([], {})), \
                patch.object(healthcare, "_fetch_elements", return_value=([facility], "stale", "persistent_overpass_cache", "2026-11-16T00:00:00Z")):
            result = await healthcare.nearby_healthcare(23.78, 90.41, 1000, "all")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["source"], "persistent_overpass_cache")
        self.assertTrue(result["is_stale"])
        self.assertEqual(result["last_updated"], "2026-11-16T00:00:00Z")

    async def test_failover_returns_actual_provider_data(self):
        facility = {"type": "node", "id": 42, "lat": 23.78, "lon": 90.41, "tags": {"amenity": "hospital", "name": "Example Hospital"}}
        client = FakeClient([httpx.TimeoutException("timeout"), FakeResponse({"elements": [facility]})])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), self._mock_client(client), \
                patch.object(healthcare.asyncio, "sleep", return_value=None):
            result = await healthcare._fetch_elements(23.78, 90.41, 1000, "hospital")
        self.assertEqual(result[:3], ([facility], "fresh", "overpass"))
        self.assertTrue(result[3])
        self.assertEqual(client.calls, 2)
        self.assertEqual(len(set(client.endpoints)), client.calls)

    async def test_retryable_provider_statuses_fail_over_to_next_provider(self):
        facility = {"type": "node", "id": 8, "lat": 23.78, "lon": 90.41, "tags": {"amenity": "clinic"}}
        for status_code in (500, 502, 429):
            with self.subTest(status=status_code), tempfile.TemporaryDirectory() as temp_dir:
                self.setUp()
                client = FakeClient([FakeResponse(status_code=status_code), FakeResponse({"elements": [facility]})])
                with self._cache_path(temp_dir), self._mock_client(client), \
                        patch.object(healthcare.asyncio, "sleep", return_value=None):
                    result = await healthcare._fetch_elements(23.78, 90.41, 1000, "clinic")
                self.assertEqual(result[:3], ([facility], "fresh", "overpass"))
                self.assertEqual(client.calls, 2)

    async def test_all_retryable_provider_statuses_return_service_unavailable(self):
        for status_code in (429, 500, 502, 503, 504):
            with self.subTest(status=status_code), tempfile.TemporaryDirectory() as temp_dir:
                self.setUp()
                client = FakeClient([FakeResponse(status_code=status_code) for _ in range(healthcare.MAX_PROVIDER_ATTEMPTS)])
                with self._cache_path(temp_dir), self._mock_client(client), \
                        patch.object(healthcare.asyncio, "sleep", return_value=None):
                    with self.assertRaises(HTTPException) as raised:
                        await healthcare._fetch_elements(23.78, 90.41, 1000, "clinic")
                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(len(set(client.endpoints)), client.calls)

    async def test_permanent_client_error_is_not_retried(self):
        client = FakeClient([FakeResponse(status_code=400)])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), self._mock_client(client):
            with self.assertRaises(HTTPException) as raised:
                await healthcare._fetch_elements(23.78, 90.41, 1000, "hospital")
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(client.calls, 1)

    async def test_empty_provider_result_is_success_and_persisted(self):
        client = FakeClient([FakeResponse({"elements": []})])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), self._mock_client(client):
            self.assertEqual((await healthcare._fetch_elements(23.78, 90.41, 1000, "clinic"))[:3], ([], "fresh", "overpass"))
            # The empty result is a valid cache entry, so no second provider call occurs.
            self.assertEqual((await healthcare._fetch_elements(23.78, 90.41, 1000, "clinic"))[:3], ([], "fresh", "persistent_overpass_cache"))
        self.assertEqual(client.calls, 1)

    async def test_all_provider_failures_raise_service_unavailable(self):
        client = FakeClient([httpx.TimeoutException("timeout") for _ in range(healthcare.MAX_PROVIDER_ATTEMPTS)])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), self._mock_client(client), \
                patch.object(healthcare.asyncio, "sleep", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                await healthcare._fetch_elements(23.78, 90.41, 1000, "all")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(client.calls, healthcare.MAX_PROVIDER_ATTEMPTS)
        self.assertEqual(len(set(client.endpoints)), client.calls)

    async def test_stale_cache_is_returned_when_all_providers_fail(self):
        facility = {"type": "node", "id": 99, "lat": 23.78, "lon": 90.41, "tags": {"amenity": "pharmacy", "name": "Mapped Pharmacy"}}
        client = FakeClient([httpx.TimeoutException("timeout") for _ in range(healthcare.MAX_PROVIDER_ATTEMPTS)])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), \
                patch.object(healthcare, "CACHE_TTL_SECONDS", 3600), \
                patch.object(healthcare, "STALE_CACHE_TTL_SECONDS", 86400), \
                self._mock_client(client), patch.object(healthcare.asyncio, "sleep", return_value=None):
            key = healthcare._persistent_cache_key(23.78, 90.41, 1000, "pharmacy")
            healthcare._cache_write_sync(key, [facility], "2026-11-16T00:00:00Z")
            with closing(sqlite3.connect(healthcare.CACHE_PATH)) as connection, connection:
                connection.execute("UPDATE nearby_osm_cache SET expires_at = ? WHERE cache_key = ?", (time.time() - 1, key))
            result = await healthcare._fetch_elements(23.78, 90.41, 1000, "pharmacy")
        self.assertEqual(result, ([facility], "stale", "persistent_overpass_cache", "2026-11-16T00:00:00Z"))

    async def test_failed_empty_provider_response_does_not_replace_stale_facilities(self):
        previous_facility = {
            "type": "node", "id": 201, "lat": 23.78, "lon": 90.41,
            "tags": {"amenity": "hospital", "name": "Cached Hospital"},
        }
        failed_response = FakeResponse({
            "elements": [], "remark": "runtime error: Query timed out while loading data.",
        })
        client = FakeClient([failed_response for _ in range(healthcare.MAX_PROVIDER_ATTEMPTS)])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), \
                patch.object(healthcare, "CACHE_TTL_SECONDS", 3600), \
                patch.object(healthcare, "STALE_CACHE_TTL_SECONDS", 86400), \
                self._mock_client(client), patch.object(healthcare.asyncio, "sleep", return_value=None):
            key = healthcare._persistent_cache_key(23.78, 90.41, 1000, "hospital")
            healthcare._cache_write_sync(key, [previous_facility], "2026-11-18T00:00:00Z")
            with closing(sqlite3.connect(healthcare.CACHE_PATH)) as connection, connection:
                connection.execute(
                    "UPDATE nearby_osm_cache SET expires_at = ? WHERE cache_key = ?",
                    (time.time() - 1, key),
                )
            response = await healthcare._fetch_elements(23.78, 90.41, 1000, "hospital")
            persisted = healthcare._cache_read_sync(key)
        self.assertEqual(response[:2], ([previous_facility], "stale"))
        self.assertEqual(persisted[0], [previous_facility])

    async def test_concurrent_identical_lookups_share_persisted_result(self):
        client = FakeClient([FakeResponse({"elements": []})])
        with tempfile.TemporaryDirectory() as temp_dir, \
                self._cache_path(temp_dir), self._mock_client(client):
            first, second = await asyncio.gather(
                healthcare._fetch_elements(23.78, 90.41, 1000, "all"),
                healthcare._fetch_elements(23.78, 90.41, 1000, "all"),
            )
        self.assertEqual(first[:3], ([], "fresh", "overpass"))
        self.assertEqual(second[:3], ([], "fresh", "persistent_overpass_cache"))
        self.assertEqual(client.calls, 1)

    async def test_local_facilities_prevent_overpass_request(self):
        facility = {
            "id": "node/8", "osm_type": "node", "name": "Local Clinic", "category": "clinic",
            "type_label": "Clinic", "lat": 23.78, "lon": 90.41, "address": None, "distance_m": 0,
        }
        metadata = {"dataset_source": "OpenStreetMap Bangladesh extract", "dataset_last_updated": "2026-11-16T00:00:00Z"}
        with patch.object(healthcare.healthcare_store, "search_local_facilities", return_value=([facility], metadata)), \
                patch.object(healthcare, "_fetch_elements", side_effect=AssertionError("Overpass must not run")):
            result = await healthcare.nearby_healthcare(23.78, 90.41, 1000, "all")
        self.assertEqual(result["facilities"], [facility])
        self.assertEqual(result["source"], "OpenStreetMap Bangladesh extract")
        self.assertTrue(result["is_stale"])

    async def test_no_local_or_cache_data_returns_service_unavailable(self):
        with patch.object(healthcare.healthcare_store, "search_local_facilities", return_value=([], {})), \
                patch.object(healthcare, "_fetch_elements", side_effect=HTTPException(503, "Map providers unavailable")):
            with self.assertRaises(HTTPException) as raised:
                await healthcare.nearby_healthcare(23.78, 90.41, 1000, "all")
        self.assertEqual(raised.exception.status_code, 503)

    async def test_local_database_failure_falls_back_to_provider(self):
        facility = {
            "type": "node", "id": 208, "lat": 23.78, "lon": 90.41,
            "tags": {"amenity": "hospital", "name": "Provider Hospital"},
        }
        with patch.object(
            healthcare.healthcare_store,
            "search_local_facilities",
            side_effect=sqlite3.OperationalError("database is unavailable"),
        ), patch.object(
            healthcare, "_fetch_elements",
            return_value=([facility], "fresh", "overpass", "2026-11-18T00:00:00Z"),
        ):
            result = await healthcare.nearby_healthcare(23.78, 90.41, 1000, "hospital")
        self.assertEqual([item["name"] for item in result["facilities"]], ["Provider Hospital"])
        self.assertFalse(result["local_database_available"])
        self.assertEqual(result["local_match_count"], 0)

    async def test_cache_persists_across_new_database_connections(self):
        with tempfile.TemporaryDirectory() as temp_dir, self._cache_path(temp_dir):
            key = healthcare._persistent_cache_key(23.78, 90.41, 1000, "hospital")
            healthcare._cache_write_sync(key, [], "2026-11-16T00:00:00Z")
            # This read opens a new SQLite connection and sees persisted data.
            cached = healthcare._cache_read_sync(key)
        self.assertEqual(cached, ([], "fresh", "2026-11-16T00:00:00Z"))

    async def test_cache_persists_across_application_process_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "restart-cache.sqlite3"
            key = healthcare._persistent_cache_key(23.78, 90.41, 1000, "hospital")
            with patch.object(healthcare, "CACHE_PATH", db_path):
                healthcare._cache_write_sync(key, [], "2026-11-16T00:00:00Z")
            environment = os.environ.copy()
            environment["CAREANYWHERE_HEALTHCARE_DB_PATH"] = str(db_path)
            environment["CAREANYWHERE_OSM_CACHE_TTL_SECONDS"] = str(healthcare.CACHE_TTL_SECONDS)
            code = (
                "import json,sys; from app.healthcare import _cache_read_sync; "
                "print(json.dumps(_cache_read_sync(sys.argv[1])))"
            )
            output = subprocess.check_output(
                [sys.executable, "-c", code, key],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                text=True,
            )
        self.assertEqual(json.loads(output), [[], "fresh", "2026-11-16T00:00:00Z"])


if __name__ == "__main__":
    unittest.main()
