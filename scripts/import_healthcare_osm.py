"""Import healthcare amenities from an OSM .osm.pbf file into SQLite.

Install the optional PBF reader first with: python -m pip install osmium
"""

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.healthcare_store import DB_PATH, import_facilities  # noqa: E402

HEALTHCARE_CATEGORIES = {"hospital", "clinic", "doctors", "pharmacy"}


def _tags_to_address(tags: dict) -> str | None:
    full = tags.get("addr:full") or tags.get("address")
    if full and str(full).strip():
        return str(full).strip()
    street = " ".join(
        str(part).strip()
        for part in (tags.get("addr:housenumber"), tags.get("addr:street"))
        if part and str(part).strip()
    )
    locality = ", ".join(
        str(part).strip()
        for part in (tags.get("addr:place"), tags.get("addr:city"), tags.get("addr:postcode"))
        if part and str(part).strip()
    )
    value = ", ".join(part for part in (street, locality) if part)
    return value or None


def _ring_centroid(rings: list[list[tuple[float, float]]]) -> tuple[float, float] | None:
    """Return a coordinate centroid from lon/lat rings; fallback to vertex mean."""
    weighted_x = weighted_y = total_area = 0.0
    vertices = []
    for points in rings:
        if len(points) < 3:
            continue
        vertices.extend(points)
        twice_area = 0.0
        cx = cy = 0.0
        closed = points if points[0] == points[-1] else [*points, points[0]]
        for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
            cross = x1 * y2 - x2 * y1
            twice_area += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        if abs(twice_area) > 1e-12:
            area = abs(twice_area / 2)
            weighted_x += (cx / (3 * twice_area)) * area
            weighted_y += (cy / (3 * twice_area)) * area
            total_area += area
    if total_area:
        return weighted_y / total_area, weighted_x / total_area
    if vertices:
        return (
            sum(point[1] for point in vertices) / len(vertices),
            sum(point[0] for point in vertices) / len(vertices),
        )
    return None


def import_pbf(pbf_path: Path, db_path: Path | str = DB_PATH) -> int:
    if not pbf_path.is_file():
        raise FileNotFoundError(f"OSM extract not found: {pbf_path}")
    try:
        import osmium
    except ImportError as exc:
        raise RuntimeError(
            "PBF import requires PyOsmium. Install it with: "
            "project\\Scripts\\python.exe -m pip install osmium"
        ) from exc

    class FacilityHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.records: dict[tuple[str, int], dict] = {}
            self.progress_counts = {"nodes": 0, "ways": 0, "areas": 0}

        def _progress(self, kind: str) -> None:
            self.progress_counts[kind] += 1
            processed = self.progress_counts[kind]
            if processed % 50_000 == 0:
                print(
                    f"Scanned {processed:,} {kind}; found {len(self.records):,} healthcare facilities so far.",
                    flush=True,
                )

        def _add(self, osm_type: str, osm_id: int, tags, lat: float, lon: float) -> None:
            # Check one tag before copying any tags; almost every object in a
            # country extract is irrelevant to the healthcare finder.
            category = tags.get("amenity")
            if category not in HEALTHCARE_CATEGORIES:
                return
            values = dict(tags)
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                return
            self.records[(osm_type, int(osm_id))] = {
                "osm_type": osm_type,
                "osm_id": int(osm_id),
                "name": values.get("name") or values.get("official_name") or "",
                "category": category,
                "lat": lat,
                "lon": lon,
                "address": _tags_to_address(values),
            }

        @staticmethod
        def _point(location):
            try:
                if not location.valid():
                    return None
                return float(location.lon), float(location.lat)
            except (AttributeError, TypeError, ValueError):
                return None

        def node(self, node):
            self._progress("nodes")
            if node.tags.get("amenity") not in HEALTHCARE_CATEGORIES:
                return
            point = self._point(node.location)
            if point:
                self._add("node", node.id, node.tags, point[1], point[0])

        def way(self, way):
            self._progress("ways")
            if way.tags.get("amenity") not in HEALTHCARE_CATEGORIES:
                return
            points = [point for point in (self._point(node.location) for node in way.nodes) if point]
            centroid = _ring_centroid([points])
            if centroid:
                self._add("way", way.id, way.tags, centroid[0], centroid[1])

        def area(self, area):
            self._progress("areas")
            if area.tags.get("amenity") not in HEALTHCARE_CATEGORIES:
                return
            rings = []
            for ring in area.outer_rings():
                points = [point for point in (self._point(node.location) for node in ring) if point]
                if points:
                    rings.append(points)
            centroid = _ring_centroid(rings)
            if centroid:
                osm_type = "way" if area.from_way() else "relation"
                self._add(osm_type, area.orig_id(), area.tags, centroid[0], centroid[1])

    handler = FacilityHandler()
    # locations enables way coordinates; area callback enables relation and
    # closed-way geometry assembly using PyOsmium's supported multipass flow.
    # The amenity filter keeps unrelated objects out of Python callbacks while
    # PyOsmium still builds its node-location index for ways and area relations.
    print(f"Scanning {pbf_path.name} for healthcare amenities; this can take several minutes.", flush=True)
    amenity_filter = osmium.filter.TagFilter(*(
        ("amenity", category) for category in sorted(HEALTHCARE_CATEGORIES)
    ))
    handler.apply_file(str(pbf_path), locations=True, filters=[amenity_filter])
    print(f"OSM scan complete: {len(handler.records):,} unique healthcare facilities found.", flush=True)
    if not handler.records:
        raise RuntimeError("No supported healthcare amenities were found; the existing database was left unchanged.")
    imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return import_facilities(
        list(handler.records.values()),
        dataset_source="OpenStreetMap Bangladesh extract",
        imported_at=imported_at,
        replace_existing=True,
        db_path=db_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OSM healthcare facilities from a .osm.pbf extract")
    parser.add_argument("pbf", type=Path, help="Path to the downloaded OSM .osm.pbf extract")
    parser.add_argument("--database", type=Path, default=DB_PATH, help=f"SQLite output path (default: {DB_PATH})")
    args = parser.parse_args()
    try:
        count = import_pbf(args.pbf, args.database)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print(f"Imported {count:,} healthcare facilities into {args.database}")
    print("The records are an OSM snapshot, not live facility availability.")


if __name__ == "__main__":
    main()
