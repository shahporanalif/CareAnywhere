"""Nearby OpenStreetMap healthcare searches."""

import asyncio
import hashlib
import json
import logging
import math
import os
import random
import sqlite3
import time
from collections import deque
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from app import healthcare_store

router = APIRouter(prefix="/api/healthcare", tags=["healthcare"])
logger = logging.getLogger(__name__)

# Global OSM data providers. Public endpoints can be busy;
# keep requests serialized and bounded, and configure a regional/local service
# for production deployments that need stronger availability.
_configured_provider = os.getenv("CAREANYWHERE_OVERPASS_URL", "").strip()
OVERPASS_URLS = tuple(dict.fromkeys((
    *((_configured_provider,) if _configured_provider else ()),
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)))
OVERPASS_USER_AGENT = "CareAnywhereAI/1.0 (Nearby Healthcare Finder)"


def _seconds_setting(name: str, default: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        if not math.isfinite(value):
            raise ValueError("non-finite value")
        return min(max(value, 1.0), maximum)
    except ValueError:
        logger.warning("Invalid %s setting; using default=%s", name, default)
        return default


HTTP_CONNECT_TIMEOUT_SECONDS = _seconds_setting("CAREANYWHERE_OSM_CONNECT_TIMEOUT_SECONDS", 4.0, 30.0)
HTTP_READ_TIMEOUT_SECONDS = _seconds_setting("CAREANYWHERE_OSM_READ_TIMEOUT_SECONDS", 9.0, 60.0)
MAX_TOTAL_SEARCH_DURATION_SECONDS = _seconds_setting("CAREANYWHERE_OSM_MAX_SEARCH_SECONDS", 28.0, 120.0)
OVERPASS_QUERY_TIMEOUT_SECONDS = 7
MAX_PROVIDER_ATTEMPTS = len(OVERPASS_URLS)
BACKOFF_BASE_SECONDS = 0.35
BACKOFF_MAX_SECONDS = 1.4
CACHE_TTL_SECONDS = max(0, int(os.getenv("CAREANYWHERE_OSM_CACHE_TTL_SECONDS", "21600")))
STALE_CACHE_TTL_SECONDS = max(0, int(os.getenv("CAREANYWHERE_OSM_STALE_TTL_SECONDS", "604800")))
CACHE_PATH = healthcare_store.DB_PATH
RATE_WINDOW_SECONDS = 60
RATE_LIMIT = 30
DAY_WINDOW_SECONDS = 24 * 60 * 60
DAILY_RATE_LIMIT = 1000

_cache_lock = asyncio.Lock()
_rate_lock = asyncio.Lock()
# One upstream operation per process prevents overlapping public API work.
_overpass_semaphore = asyncio.Semaphore(1)
_request_times: deque[float] = deque()
_provider_cursor = 0

_CATEGORY_TAGS = {
    "hospital": ("hospital",),
    "clinic": ("clinic",),
    "pharmacy": ("pharmacy",),
    "doctors": ("doctors",),
    "all": ("hospital", "clinic", "doctors", "pharmacy"),
}
_CATEGORY_LABELS = {
    "hospital": "Hospital",
    "clinic": "Clinic",
    "pharmacy": "Pharmacy",
    "doctors": "Doctor / Medical practice",
}


def _persistent_cache_key(lat: float, lon: float, radius: int, category: str) -> str:
    """Hash the query identity so precise coordinates are not stored in SQLite."""
    query_identity = f"{lat:.5f}|{lon:.5f}|{radius}|{category}"
    return hashlib.sha256(query_identity.encode("utf-8")).hexdigest()


def _cache_read_sync(key: str) -> tuple[list[dict], str, str] | None:
    if CACHE_TTL_SECONDS == 0 or not CACHE_PATH.exists():
        logger.info("nearby_cache event=miss reason=database_unavailable_or_disabled")
        return None
    try:
        with closing(sqlite3.connect(CACHE_PATH, timeout=2)) as connection, connection:
            row = connection.execute(
                "SELECT payload, expires_at, stale_until, fetched_at FROM nearby_osm_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None:
                logger.info("nearby_cache event=miss")
                return None
            now = time.time()
            if row[2] <= now:
                connection.execute("DELETE FROM nearby_osm_cache WHERE cache_key = ?", (key,))
                return None
            payload = json.loads(row[0])
            # Older cache entries stored a bare list; support those through migration.
            elements = payload.get("elements") if isinstance(payload, dict) else payload
            fetched_at = payload.get("last_updated", "") if isinstance(payload, dict) else ""
            fetched_at = fetched_at or row[3]
            if not fetched_at:
                fetched_at = datetime.fromtimestamp(row[1] - CACHE_TTL_SECONDS, timezone.utc).isoformat(timespec="seconds")
            if not isinstance(elements, list):
                logger.warning("nearby_cache event=miss reason=invalid_payload")
                return None
            logger.info("nearby_cache event=hit freshness=%s", "fresh" if row[1] > now else "stale")
            return elements, "fresh" if row[1] > now else "stale", fetched_at
    except (sqlite3.Error, json.JSONDecodeError, OSError) as exc:
        logger.warning("Nearby OSM cache read failed: %s", type(exc).__name__)
        return None


def _cache_write_sync(key: str, elements: list[dict], fetched_at: str) -> None:
    if CACHE_TTL_SECONDS == 0:
        return
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(CACHE_PATH, timeout=2)) as connection, connection:
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
            now = time.time()
            connection.execute("DELETE FROM nearby_osm_cache WHERE stale_until <= ?", (now,))
            connection.execute(
                "INSERT OR REPLACE INTO nearby_osm_cache(cache_key, payload, expires_at, stale_until, fetched_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    json.dumps({"elements": elements, "last_updated": fetched_at}, separators=(",", ":")),
                    now + CACHE_TTL_SECONDS,
                    now + CACHE_TTL_SECONDS + STALE_CACHE_TTL_SECONDS,
                    fetched_at,
                ),
            )
            # Bound disk use while retaining the most recent 2,000 public query results.
            connection.execute(
                "DELETE FROM nearby_osm_cache WHERE cache_key NOT IN ("
                "SELECT cache_key FROM nearby_osm_cache ORDER BY expires_at DESC LIMIT 2000)"
            )
    except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
        logger.warning("Nearby OSM cache write failed: %s", type(exc).__name__)


async def _read_cache(key: str) -> tuple[list[dict], str, str] | None:
    async with _cache_lock:
        return await asyncio.to_thread(_cache_read_sync, key)


async def _write_cache(key: str, elements: list[dict], fetched_at: str) -> None:
    async with _cache_lock:
        await asyncio.to_thread(_cache_write_sync, key, elements, fetched_at)


async def _check_rate_limit() -> None:
    """Limit upstream lookups without storing client IPs or coordinates."""
    now = time.monotonic()
    async with _rate_lock:
        while _request_times and now - _request_times[0] >= DAY_WINDOW_SECONDS:
            _request_times.popleft()
        if len(_request_times) >= DAILY_RATE_LIMIT:
            retry_after = max(1, math.ceil(DAY_WINDOW_SECONDS - (now - _request_times[0])))
            raise HTTPException(
                status_code=429,
                detail="Nearby search daily limit reached. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        recent_requests = sum(now - requested_at < RATE_WINDOW_SECONDS for requested_at in _request_times)
        if recent_requests >= RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Nearby searches are busy. Please wait a minute and try again.",
                headers={"Retry-After": "60"},
            )
        _request_times.append(now)


def _build_query(lat: float, lon: float, radius: int, category: str) -> str:
    around = f"around:{radius},{lat:.6f},{lon:.6f}"
    tags = "|".join(_CATEGORY_TAGS[category])
    # A single selector avoids repeating the expensive around() spatial scan.
    return (
        f"[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];\n"
        f'nwr({around})["amenity"~"^({tags})$"];\n'
        "out center qt;"
    )


async def _request_provider(endpoint: str, query: str) -> tuple[list[dict], str]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=HTTP_CONNECT_TIMEOUT_SECONDS,
            read=HTTP_READ_TIMEOUT_SECONDS,
            write=5.0,
            pool=2.0,
        ),
        headers={"User-Agent": OVERPASS_USER_AGENT},
    ) as client:
        response = await client.post(endpoint, data={"data": query})
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Provider returned an invalid response")
    remark = str(payload.get("remark", "")).lower()
    if any(message in remark for message in ("runtime error", "timed out", "out of memory")):
        raise TimeoutError(remark[:160] or "Provider could not complete the query")
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Provider response did not include an elements list")
    osm3s = payload.get("osm3s") if isinstance(payload.get("osm3s"), dict) else {}
    fetched_at = osm3s.get("timestamp_osm_base") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return elements, str(fetched_at)


async def _fetch_elements(lat: float, lon: float, radius: int, category: str) -> tuple[list[dict], str, str, str]:
    """Read persistent cache, otherwise make bounded, serialized provider attempts."""
    started = time.monotonic()
    deadline = started + MAX_TOTAL_SEARCH_DURATION_SECONDS
    key = _persistent_cache_key(lat, lon, radius, category)
    cached = await _read_cache(key)
    if cached is not None and cached[1] == "fresh":
        logger.info("nearby_search event=cache_hit source=persistent_overpass_cache freshness=fresh")
        return cached[0], cached[1], "persistent_overpass_cache", cached[2]

    global _provider_cursor
    queue_timeout = max(0.0, deadline - time.monotonic())
    if queue_timeout <= 0:
        if cached is not None and cached[1] == "stale":
            logger.warning("nearby_search event=stale_cache_fallback reason=search_deadline_exceeded")
            return cached[0], "stale", "persistent_overpass_cache", cached[2]
        raise HTTPException(503, "Nearby healthcare search exceeded its time limit. Please try again later.")
    try:
        await asyncio.wait_for(_overpass_semaphore.acquire(), timeout=queue_timeout)
    except asyncio.TimeoutError as exc:
        if cached is not None and cached[1] == "stale":
            logger.warning("nearby_search event=stale_cache_fallback reason=upstream_queue_timeout")
            return cached[0], "stale", "persistent_overpass_cache", cached[2]
        raise HTTPException(503, "Nearby healthcare search is busy. Please try again shortly.") from exc

    try:
        # A previous request for this query may have populated the cache while
        # this request waited on the single upstream slot.
        cached = await _read_cache(key)
        if cached is not None and cached[1] == "fresh":
            logger.info("nearby_search event=cache_hit source=persistent_overpass_cache freshness=fresh")
            return cached[0], cached[1], "persistent_overpass_cache", cached[2]
        await _check_rate_limit()

        query = _build_query(lat, lon, radius, category)
        saw_timeout = False
        saw_rate_limit = False
        saw_provider_busy = False
        last_error: Exception | None = None
        first_provider = _provider_cursor % len(OVERPASS_URLS)
        attempts = min(MAX_PROVIDER_ATTEMPTS, len(OVERPASS_URLS))
        for attempt in range(attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                saw_timeout = True
                break
            endpoint = OVERPASS_URLS[(first_provider + attempt) % len(OVERPASS_URLS)]
            provider = endpoint.split("/")[2]
            try:
                elements, fetched_at = await asyncio.wait_for(
                    _request_provider(endpoint, query), timeout=remaining
                )
                _provider_cursor = (first_provider + attempt + 1) % len(OVERPASS_URLS)
                await _write_cache(key, elements, fetched_at)
                logger.info("nearby_provider event=success provider=%s result_count=%s", provider, len(elements))
                return elements, "fresh", "overpass", fetched_at
            except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                saw_timeout, last_error = True, exc
                logger.warning("nearby_provider event=timeout provider=%s attempt=%s/%s", provider, attempt + 1, attempts)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                code = exc.response.status_code
                logger.warning("nearby_provider event=http_status provider=%s status=%s attempt=%s/%s", provider, code, attempt + 1, attempts)
                if code == 429:
                    saw_rate_limit = True
                    saw_provider_busy = True
                elif code in (500, 502, 503, 504):
                    saw_timeout = saw_timeout or code == 504
                    saw_provider_busy = True
                elif 400 <= code < 500:
                    if cached is not None and cached[1] == "stale":
                        logger.warning("Serving stale nearby OSM cache after provider rejected the query")
                        return cached[0], "stale", "persistent_overpass_cache", cached[2]
                    raise HTTPException(502, "The map data service rejected the nearby search query.") from exc
            except (httpx.RequestError, ValueError, TimeoutError) as exc:
                last_error = exc
                saw_timeout = saw_timeout or isinstance(exc, TimeoutError)
                event = "connection_error" if isinstance(exc, httpx.RequestError) else "invalid_response"
                logger.warning("nearby_provider event=%s provider=%s error=%s attempt=%s/%s", event, provider, type(exc).__name__, attempt + 1, attempts)

            if attempt + 1 < attempts:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    saw_timeout = True
                    break
                maximum_delay = min(BACKOFF_BASE_SECONDS * (2 ** attempt), BACKOFF_MAX_SECONDS)
                await asyncio.sleep(min(random.uniform(0, maximum_delay), remaining))

        # Even if the whole provider set failed, the next user search begins
        # at the next host instead of repeatedly favoring the same one.
        _provider_cursor = (first_provider + 1) % len(OVERPASS_URLS)
        if cached is not None and cached[1] == "stale":
            logger.warning("nearby_search event=stale_cache_fallback reason=all_providers_failed")
            return cached[0], "stale", "persistent_overpass_cache", cached[2]
        if saw_timeout:
            raise HTTPException(
                503,
                "Nearby healthcare data is temporarily unavailable because all map data providers timed out. Try again later.",
            ) from last_error
        if saw_rate_limit:
            raise HTTPException(503, "Map data services are busy. Please wait and try again.") from last_error
        if saw_provider_busy:
            raise HTTPException(503, "Nearby healthcare search is temporarily unavailable. Please try again later.") from last_error
        raise HTTPException(503, "Could not reach an available map data service. Please try again later.") from last_error
    finally:
        _overpass_semaphore.release()


def _coordinates(element: dict) -> tuple[float, float] | None:
    coords = element if element.get("type") == "node" else element.get("center")
    if not isinstance(coords, dict):
        return None
    try:
        lat = float(coords["lat"])
        lon = float(coords["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _address(tags: dict) -> str | None:
    full = tags.get("addr:full") or tags.get("address")
    if full and str(full).strip():
        return str(full).strip()
    street_line = " ".join(
        str(value).strip()
        for value in (tags.get("addr:housenumber"), tags.get("addr:street"))
        if value and str(value).strip()
    )
    locality = ", ".join(
        str(value).strip()
        for value in (tags.get("addr:place"), tags.get("addr:city"), tags.get("addr:postcode"))
        if value and str(value).strip()
    )
    address = ", ".join(part for part in (street_line, locality) if part)
    return address or None


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    earth_radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return round(2 * earth_radius * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


@router.get("/nearby")
async def nearby_healthcare(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius: int = Query(default=3000, ge=1000, le=10000),
    category: Literal["hospital", "clinic", "pharmacy", "doctors", "all"] = "all",
):
    """Search imported local OSM facilities first, then cache and Overpass."""
    local_database_error = None
    try:
        local_facilities, local_metadata = await asyncio.to_thread(
            healthcare_store.search_local_facilities,
            lat,
            lon,
            radius,
            category,
            db_path=CACHE_PATH,
        )
    except (sqlite3.Error, OSError) as exc:
        local_facilities, local_metadata = [], {}
        local_database_error = exc
        logger.error("nearby_local_database event=unavailable error=%s", type(exc).__name__)
    logger.info(
        "nearby_local_search event=complete result_count=%s database_available=%s",
        len(local_facilities),
        local_database_error is None,
    )
    if local_facilities:
        return {
            "radius_m": radius,
            "category": category,
            "count": len(local_facilities),
            "facilities": local_facilities,
            "cache_status": "local_snapshot",
            "source": local_metadata.get("dataset_source", "local OSM database"),
            "is_stale": True,
            "stale": True,
            "last_updated": local_metadata.get("dataset_last_updated"),
            "local_database_available": True,
            "local_match_count": len(local_facilities),
        }

    try:
        elements, freshness, source, last_updated = await _fetch_elements(lat, lon, radius, category)
    except HTTPException as exc:
        if exc.status_code == 503:
            if local_database_error is not None:
                detail = "Local healthcare database is unavailable and external map data providers failed."
            else:
                detail = "No local healthcare facilities matched this search, and external map data providers failed."
            raise HTTPException(503, detail) from exc
        raise
    facilities = []
    seen: set[tuple[str, int]] = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        amenity = str(tags.get("amenity", ""))
        if amenity not in _CATEGORY_LABELS or (category != "all" and amenity != category):
            continue
        coords = _coordinates(element)
        if coords is None:
            continue
        facility_lat, facility_lon = coords
        element_type = str(element.get("type", ""))
        try:
            element_id = int(element["id"])
        except (KeyError, TypeError, ValueError):
            continue
        identity = (element_type, element_id)
        if identity in seen:
            continue
        seen.add(identity)
        name = tags.get("name") or tags.get("official_name")
        name = str(name).strip() if name else ""
        if not name:
            name = f"Unnamed {_CATEGORY_LABELS[amenity].lower()}"
        facilities.append({
            "id": f"{element_type}/{element_id}",
            "osm_type": element_type,
            "name": name,
            "category": amenity,
            "type_label": _CATEGORY_LABELS[amenity],
            "lat": facility_lat,
            "lon": facility_lon,
            "address": _address(tags),
            "distance_m": _distance_meters(lat, lon, facility_lat, facility_lon),
        })
    facilities.sort(key=lambda facility: facility["distance_m"])
    is_stale = freshness == "stale"
    return {
        "radius_m": radius,
        "category": category,
        "count": len(facilities),
        "facilities": facilities,
        "cache_status": freshness,
        "source": source,
        "is_stale": is_stale,
        "stale": is_stale,
        "last_updated": last_updated,
        "local_database_available": local_database_error is None,
        "local_match_count": len(local_facilities),
    }
