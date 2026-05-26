"""Sensor dashboard — serves room temps and ventilation data from InfluxDB."""
import os
import urllib.request
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

INFLUX_HOST   = os.environ["INFLUX_HOST"]
INFLUX_PORT   = int(os.environ.get("INFLUX_PORT", "8086"))
INFLUX_TOKEN  = os.environ["INFLUX_TOKEN"]
INFLUX_ORG    = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "sensors")


def _flux_query(query: str) -> list[dict]:
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
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if headers is None:
            headers = parts
            continue
        rows.append(dict(zip(headers, parts)))
    return rows


def _last_by_tag(measurement: str, tag_key: str, field: str) -> dict[str, float | None]:
    """Return {tag_value: last_float_value} for a given measurement/tag/field."""
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


def _history_by_tag(measurement: str, tag_key: str, field: str, range: str) -> dict[str, list]:
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{range})
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/rooms/current")
async def rooms_current():
    temps = _last_by_tag("raumtemperatur", "raum", "temp")
    hums  = _last_by_tag("raumtemperatur", "raum", "hum")
    all_rooms = sorted(set(temps) | set(hums))
    result = {r: {"temp": temps.get(r), "hum": hums.get(r)} for r in all_rooms}
    return JSONResponse(result)


@app.get("/api/rooms/history")
async def rooms_history(range: str = "24h"):
    return JSONResponse(_history_by_tag("raumtemperatur", "raum", "temp", range))


@app.get("/api/ventilation/current")
async def ventilation_current():
    temps = _last_by_tag("lueftung", "luftstrom", "temp")
    hums  = _last_by_tag("lueftung", "luftstrom", "hum")
    all_streams = sorted(set(temps) | set(hums))
    result = {s: {"temp": temps.get(s), "hum": hums.get(s)} for s in all_streams}
    return JSONResponse(result)


@app.get("/api/ventilation/history")
async def ventilation_history(range: str = "24h"):
    return JSONResponse(_history_by_tag("lueftung", "luftstrom", "temp", range))


def _safe_float(val) -> float | None:
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return None
