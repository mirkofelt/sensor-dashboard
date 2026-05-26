"""Sensor dashboard — serves room temperatures and ventilation data from InfluxDB v2."""
import os
import urllib.request
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Sensor Dashboard")

# Resolve templates relative to this file so the path works regardless of CWD
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

INFLUX_HOST   = os.environ["INFLUX_HOST"]
INFLUX_PORT   = int(os.environ.get("INFLUX_PORT", "8086"))
INFLUX_TOKEN  = os.environ["INFLUX_TOKEN"]
INFLUX_ORG    = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "sensors")


def _flux_query(query: str) -> list[dict]:
    """Send a Flux query to InfluxDB and return parsed CSV rows as dicts."""
    url = f"http://{INFLUX_HOST}:{INFLUX_PORT}/api/v2/query?org={INFLUX_ORG}"
    body = json.dumps({"query": query, "type": "flux"}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Token {INFLUX_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/csv")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode()

    rows = []
    headers = None
    for line in raw.splitlines():
        # InfluxDB annotated CSV: lines starting with # are type annotations, not data
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if headers is None:
            headers = parts  # first non-annotation line is the header row
            continue
        rows.append(dict(zip(headers, parts)))
    return rows


def _last_by_tag(measurement: str, tag_key: str, field: str) -> dict[str, float | None]:
    """Return {tag_value: last_float} for one field in a measurement.

    We query temp and hum in separate calls rather than using Flux pivot()
    because pivot reshapes the CSV in a way that breaks the simple header→value
    parsing above (column names become dynamic and clash across series).
    """
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -2h)
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> last()
'''
    rows = _flux_query(query)
    result = {}
    for row in rows:
        tag_val = row.get(tag_key, "")
        val = _safe_float(row.get("_value"))
        if tag_val:
            result[tag_val] = val
    return result


def _history_by_tag(measurement: str, tag_key: str, field: str, time_range: str) -> dict[str, list]:
    """Return {tag_value: [{t, v}, ...]} averaged over 15-minute windows."""
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
'''
    rows = _flux_query(query)
    series: dict[str, list] = {}
    for row in rows:
        tag_val = row.get(tag_key, "")
        t = row.get("_time", "")
        v = _safe_float(row.get("_value"))
        if tag_val and t and v is not None:
            series.setdefault(tag_val, []).append({"t": t, "v": v})
    return series


def _safe_float(val) -> float | None:
    """Parse a value to a rounded float, returning None on failure."""
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/rooms/current")
async def rooms_current():
    """Current temperature and humidity for all rooms."""
    temps = _last_by_tag("raumtemperatur", "raum", "temp")
    hums  = _last_by_tag("raumtemperatur", "raum", "hum")
    all_rooms = sorted(set(temps) | set(hums))
    return JSONResponse({r: {"temp": temps.get(r), "hum": hums.get(r)} for r in all_rooms})


@app.get("/api/rooms/history")
async def rooms_history(range: str = "24h"):
    """Temperature history for all rooms. range: 6h | 24h | 7d"""
    return JSONResponse(_history_by_tag("raumtemperatur", "raum", "temp", range))


@app.get("/api/ventilation/current")
async def ventilation_current():
    """Current temperature and humidity for all ventilation air streams."""
    temps = _last_by_tag("lueftung", "luftstrom", "temp")
    hums  = _last_by_tag("lueftung", "luftstrom", "hum")
    all_streams = sorted(set(temps) | set(hums))
    return JSONResponse({s: {"temp": temps.get(s), "hum": hums.get(s)} for s in all_streams})


@app.get("/api/ventilation/history")
async def ventilation_history(range: str = "24h"):
    """Temperature history for all ventilation air streams. range: 6h | 24h | 7d"""
    return JSONResponse(_history_by_tag("lueftung", "luftstrom", "temp", range))
