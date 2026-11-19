"""Export public OSM healthcare rows as a small deploy-time seed snapshot."""

import argparse
import json
import os
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.healthcare_store import DB_PATH  # noqa: E402

DEFAULT_OUTPUT = ROOT / "data" / "healthcare_snapshot.json"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0. https://www.openstreetmap.org/copyright"


def export_snapshot(database: Path, output: Path) -> int:
    import sqlite3

    if not database.is_file():
        raise FileNotFoundError(f"Healthcare database not found: {database}")
    with closing(sqlite3.connect(database)) as connection, connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "healthcare_facilities" not in tables:
            raise RuntimeError("The selected database has no healthcare facilities table.")
        metadata = {}
        if "healthcare_metadata" in tables:
            metadata = dict(connection.execute(
                "SELECT key, value FROM healthcare_metadata "
                "WHERE key IN ('dataset_source','dataset_last_updated')"
            ).fetchall())
        facilities = [
            {
                "osm_type": row[0], "osm_id": row[1], "name": row[2], "category": row[3],
                "lat": row[4], "lon": row[5], "address": row[6],
            }
            for row in connection.execute(
                "SELECT osm_type, osm_id, name, category, lat, lon, address "
                "FROM healthcare_facilities ORDER BY category, osm_type, osm_id"
            )
        ]
    if not facilities:
        raise RuntimeError("The healthcare database is empty; refusing to write an empty deploy snapshot.")

    document = {
        "dataset_source": metadata.get("dataset_source", "OpenStreetMap healthcare snapshot"),
        "dataset_last_updated": metadata.get("dataset_last_updated"),
        "attribution": ATTRIBUTION,
        "facilities": facilities,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, output)
    return len(facilities)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DB_PATH, help=f"SQLite source (default: {DB_PATH})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"JSON seed output (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()
    try:
        count = export_snapshot(args.database, args.output)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print(f"Exported {count:,} public OSM healthcare facilities to {args.output}")
    print(ATTRIBUTION)


if __name__ == "__main__":
    main()
