"""SQLite storage and indexed local searches for OSM healthcare facilities."""

import math
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv(
    "CAREANYWHERE_HEALTHCARE_DB_PATH",
    os.getenv("CAREANYWHERE_OSM_CACHE_PATH", str(ROOT / "data" / "osm-healthcare-cache.sqlite3")),
))
CATEGORIES = ("hospital", "clinic", "pharmacy", "doctors")
CATEGORY_LABELS = {
    "hospital": "Hospital",
    "clinic": "Clinic",
    "pharmacy": "Pharmacy",
    "doctors": "Doctor / Medical practice",
}


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path | str | None = None) -> None:
    """Create database tables and location/category indexes idempotently."""
    with closing(_connect(db_path)) as connection, connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS healthcare_facilities ("
            "osm_type TEXT NOT NULL, osm_id INTEGER NOT NULL, name TEXT NOT NULL DEFAULT '', "
            "category TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, address TEXT, "
            "PRIMARY KEY (osm_type, osm_id), CHECK(category IN ('hospital','clinic','pharmacy','doctors')), "
            "CHECK(lat BETWEEN -90 AND 90), CHECK(lon BETWEEN -180 AND 180))"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_healthcare_facilities_lat_lon "
            "ON healthcare_facilities(lat, lon)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_healthcare_facilities_category_lat_lon "
            "ON healthcare_facilities(category, lat, lon)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS healthcare_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        # Query cache shares this local database file and survives restarts.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS nearby_osm_cache ("
            "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at REAL NOT NULL, "
            "stale_until REAL NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL DEFAULT '')"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(nearby_osm_cache)")}
        if "stale_until" not in columns:
            connection.execute("ALTER TABLE nearby_osm_cache ADD COLUMN stale_until REAL NOT NULL DEFAULT 0")
        if "fetched_at" not in columns:
            connection.execute("ALTER TABLE nearby_osm_cache ADD COLUMN fetched_at TEXT NOT NULL DEFAULT ''")


def import_facilities(
    records: list[dict],
    *,
    dataset_source: str,
    imported_at: str | None = None,
    replace_existing: bool = True,
    db_path: Path | str | None = None,
) -> int:
    """Atomically replace or merge OSM facility records and import metadata."""
    initialize_database(db_path)
    imported_at = imported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    accepted = []
    for record in records:
        try:
            osm_type = str(record["osm_type"])
            osm_id = int(record["osm_id"])
            category = str(record["category"])
            lat, lon = float(record["lat"]), float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if osm_type not in ("node", "way", "relation") or category not in CATEGORIES:
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        accepted.append((
            osm_type,
            osm_id,
            str(record.get("name") or "").strip(),
            category,
            lat,
            lon,
            str(record.get("address") or "").strip() or None,
        ))

    with closing(_connect(db_path)) as connection, connection:
        if replace_existing:
            connection.execute("DELETE FROM healthcare_facilities")
        connection.executemany(
            "INSERT OR REPLACE INTO healthcare_facilities "
            "(osm_type, osm_id, name, category, lat, lon, address) VALUES (?, ?, ?, ?, ?, ?, ?)",
            accepted,
        )
        connection.executemany(
            "INSERT OR REPLACE INTO healthcare_metadata(key, value) VALUES (?, ?)",
            (("dataset_source", dataset_source), ("dataset_last_updated", imported_at)),
        )
        count = connection.execute("SELECT COUNT(*) FROM healthcare_facilities").fetchone()[0]
        connection.execute("INSERT OR REPLACE INTO healthcare_metadata(key, value) VALUES ('facility_count', ?)", (str(count),))
    return len(accepted)


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    earth_radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return round(2 * earth_radius * math.atan2(math.sqrt(value), math.sqrt(1 - value)))


def search_local_facilities(
    lat: float,
    lon: float,
    radius: int,
    category: str,
    *,
    db_path: Path | str | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Use indexed bounding-box SQL then exact great-circle distance filtering."""
    lat_delta = radius / 111_320
    lon_delta = radius / (111_320 * max(abs(math.cos(math.radians(lat))), 0.01))
    min_lat, max_lat = max(-90, lat - lat_delta), min(90, lat + lat_delta)
    min_lon, max_lon = max(-180, lon - lon_delta), min(180, lon + lon_delta)
    selected_categories = CATEGORIES if category == "all" else (category,)
    placeholders = ",".join("?" for _ in selected_categories)
    sql = (
        "SELECT osm_type, osm_id, name, category, lat, lon, address "
        "FROM healthcare_facilities WHERE category IN (" + placeholders + ") "
        "AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?"
    )
    params = (*selected_categories, min_lat, max_lat, min_lon, max_lon)
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(sql, params).fetchall()
        metadata = {row["key"]: row["value"] for row in connection.execute(
            "SELECT key, value FROM healthcare_metadata WHERE key IN ('dataset_source','dataset_last_updated')"
        )}

    facilities = []
    for row in rows:
        distance = _distance_meters(lat, lon, row["lat"], row["lon"])
        if distance > radius:
            continue
        facilities.append({
            "id": f"{row['osm_type']}/{row['osm_id']}",
            "osm_type": row["osm_type"],
            "name": row["name"] or f"Unnamed {CATEGORY_LABELS[row['category']].lower()}",
            "category": row["category"],
            "type_label": CATEGORY_LABELS[row["category"]],
            "lat": row["lat"],
            "lon": row["lon"],
            "address": row["address"],
            "distance_m": distance,
        })
    facilities.sort(key=lambda facility: facility["distance_m"])
    return facilities, metadata


# Ensure the local store exists as soon as the application imports this module,
# before any Overpass request can occur (including when no extract has been imported).
initialize_database()
