# CareAnywhere AI

CareAnywhere AI is a FastAPI medical education chatbot with a nearby OpenStreetMap healthcare finder. The healthcare finder prefers a local SQLite snapshot, then its persistent nearby-query cache, and only then tries public Overpass providers.

## Local healthcare database

The facility database is initialized automatically when `app.healthcare` loads, before any Overpass request. By default it is stored at `data/osm-healthcare-cache.sqlite3`; the file contains the local facilities, import metadata, and persistent nearby-query cache. Set `CAREANYWHERE_HEALTHCARE_DB_PATH` to select another path. The legacy `CAREANYWHERE_OSM_CACHE_PATH` is still honored when the new setting is not set.

An imported OSM extract is a snapshot, not live facility status. Local results identify their source, set `is_stale` to `true`, and include `last_updated` (the time the extract was imported). Overpass cache responses report `source`, `is_stale`, and the source snapshot timestamp when supplied by Overpass. Existing `radius_m`, `category`, `count`, and `facilities` fields are unchanged.

## Download and import the Bangladesh OSM extract

Geofabrik provides the Bangladesh country extract as `bangladesh-latest.osm.pbf` at [download.geofabrik.de/asia/bangladesh.html](https://download.geofabrik.de/asia/bangladesh.html). Download the current extract manually; application startup never downloads it.

From PowerShell in the project root:

```powershell
# Initialize the local SQLite tables and indexes (also happens at app import).
project\Scripts\python.exe -c "from app.healthcare_store import initialize_database; initialize_database()"

Invoke-WebRequest `
  -Uri "https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf" `
  -OutFile ".\data\bangladesh-latest.osm.pbf"

project\Scripts\python.exe -m pip install osmium
project\Scripts\python.exe scripts\import_healthcare_osm.py .\data\bangladesh-latest.osm.pbf
```

The importer replaces the local facility snapshot atomically, stores mapped hospitals, clinics, pharmacies and doctors, and prints the number of records imported. It reads nodes, ways, and assembled area relations. Do not commit the extract or generated SQLite database.

## Run the application

```powershell
project\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Nearby Healthcare settings:

- `CAREANYWHERE_HEALTHCARE_DB_PATH`: combined local facilities/cache SQLite path.
- `CAREANYWHERE_OSM_CACHE_TTL_SECONDS`: fresh query-cache TTL (default `21600`, six hours).
- `CAREANYWHERE_OSM_STALE_TTL_SECONDS`: additional stale-cache fallback period (default `604800`, seven days).
- `CAREANYWHERE_OVERPASS_URL`: optional first provider endpoint, followed by public fallbacks.

When no local match or cached result is available and every provider fails, the endpoint returns HTTP 503 with an explanatory detail. It does not turn provider failure into a zero-result response and never invents facility records. Public Overpass uptime is not guaranteed.

## Tests

```powershell
project\Scripts\python.exe -m unittest discover -s tests -v
node --test tests\test_frontend_search.js
```
