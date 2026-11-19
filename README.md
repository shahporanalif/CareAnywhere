# CareAnywhere AI

CareAnywhere AI is a FastAPI medical education chatbot with a nearby OpenStreetMap healthcare finder. The healthcare finder prefers a local SQLite snapshot, then its persistent nearby-query cache, and only then tries public Overpass providers.

## Local healthcare database

The facility database is initialized automatically when `app.healthcare` loads, before any Overpass request. By default it is stored at `data/osm-healthcare-cache.sqlite3`; the file contains the local facilities, import metadata, and persistent nearby-query cache. Set `CAREANYWHERE_HEALTHCARE_DB_PATH` to select another path. The legacy `CAREANYWHERE_OSM_CACHE_PATH` is still honored when the new setting is not set.

An imported OSM extract is a snapshot, not live facility status. Local results identify their source, set `is_stale` to `true`, and include `last_updated` (the time the extract was imported). Overpass cache responses report `source`, `is_stale`, and the source snapshot timestamp when supplied by Overpass. Existing `radius_m`, `category`, `count`, and `facilities` fields are unchanged.

Nearby success responses also include `local_database_available` and `local_match_count` so clients can distinguish an empty local search from unavailable local storage without changing the existing result fields.

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
- `CAREANYWHERE_OSM_CONNECT_TIMEOUT_SECONDS`, `CAREANYWHERE_OSM_READ_TIMEOUT_SECONDS`, and `CAREANYWHERE_OSM_MAX_SEARCH_SECONDS`: bound provider connect/read waits and the complete serialized search (defaults `4`, `9`, and `28` seconds).
- `CAREANYWHERE_HEALTHCARE_SNAPSHOT_PATH`: optional path to a bundled JSON seed snapshot.

When no local match or cached result is available and every provider fails, the endpoint returns HTTP 503 with an explanatory detail. It does not turn provider failure into a zero-result response and never invents facility records. Public Overpass uptime is not guaranteed.

## Render deployment

The SQLite database is intentionally ignored by Git and is not copied from a developer's Windows machine. The separate `data/healthcare_snapshot.json` contains the public OSM healthcare rows from the Bangladesh extract, plus its import timestamp and OSM attribution. It is about 1.2 MB. On startup, an empty healthcare database is initialized and populated from this bundled snapshot; an existing database with records is preserved. This uses no startup download and does not include medical conversation memory.

For a Render native Python web service, use:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health`

After deployment, `/api/health` reports a safe `healthcare` object with `database_available`, `initialized`, `facility_count`, and `local_search_available`. A healthy bundled deployment should report `local_search_available: true` and the snapshot facility count. The health endpoint does not expose a file path, API key, or user coordinates.

Render Free services use an ephemeral filesystem: the generated SQLite file and Overpass query cache can disappear after a restart, spin-down, or deploy. The bundled JSON remains in the deployment and recreates the facility snapshot at startup, so nearby Bangladesh lookups still have local OSM records after a restart. The query cache itself will not persist there. Preserving SQLite cache writes across restarts requires a persistent disk or another persistent datastore; Render persistent disks require a paid service. No paid storage has been configured by this project. If you attach a disk, mount it at `/var/data` and set `CAREANYWHERE_HEALTHCARE_DB_PATH=/var/data/osm-healthcare-cache.sqlite3` in the service environment. The empty database on that disk will be seeded from the bundled snapshot on first startup.

### Refresh the deployed OSM snapshot

Update the local OSM database from a current Bangladesh extract using the earlier import steps, then export the deployment seed:

```powershell
project\Scripts\python.exe scripts\import_healthcare_osm.py .\data\bangladesh-latest.osm.pbf
project\Scripts\python.exe scripts\export_healthcare_snapshot.py
```

Review the import timestamp and OSM attribution in `data/healthcare_snapshot.json`, then commit that JSON and redeploy. The Render instance does not download the full Geofabrik PBF extract. The importer only updates from authentic OSM data; it refuses to replace the existing snapshot if it finds no supported records.

## Tests

```powershell
project\Scripts\python.exe -m unittest discover -s tests -v
node --test tests\test_frontend_search.js tests\test_translations.js
```
