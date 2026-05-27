"""Sensor dashboard — serves room temperatures and ventilation data from InfluxDB v2."""
import os
import urllib.request
import json
from pathlib import Path
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Sensor Dashboard")

# Resolve templates relative to this file so the path works regardless of CWD
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

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
    """Current temperature, humidity, and heating status for all rooms."""
    temps   = _last_by_tag("raumtemperatur", "raum", "temp")
    hums    = _last_by_tag("raumtemperatur", "raum", "hum")
    heating = _last_by_tag("raumtemperatur", "raum", "heating")
    all_rooms = sorted(set(temps) | set(hums))
    return JSONResponse({
        r: {"temp": temps.get(r), "hum": hums.get(r), "heating": heating.get(r)}
        for r in all_rooms
    })


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


_TAG_KEY = {"raumtemperatur": "raum", "lueftung": "luftstrom", "energie": None, "verbraucher": None, "comfoclime": None}
_VENT_LABELS = {"aussenluft": "Außenluft", "abluft": "Abluft", "fortluft": "Fortluft", "zuluft": "Zuluft"}
_FIELD_LABELS = {"temp": "Temp", "hum": "Feuchte"}
_FIELD_UNITS  = {"temp": "°C", "hum": "%"}

_COMFOCLIME_FIELDS = [
    "mode", "heat_pump_status",
    "indoor_temp_c", "outdoor_temp_c", "set_point_temp_c",
    "tpma_temp_c", "supply_temp_c", "exhaust_temp_c",
    "supply_coil_temp_c", "exhaust_coil_temp_c",
    "power_pct", "power_w", "fan_speed",
]
_COMFOCLIME_HISTORY_FIELDS = ["indoor_temp_c", "outdoor_temp_c", "tpma_temp_c", "supply_temp_c", "exhaust_temp_c"]
_COMFOCLIME_SERIES = {
    "indoor_temp_c": ("CC Innenraum", "°C"),
    "outdoor_temp_c": ("CC Außen", "°C"),
    "tpma_temp_c": ("CC TPMA", "°C"),
    "supply_temp_c": ("CC Zuluft (nach WP)", "°C"),
    "exhaust_temp_c": ("CC Abluft", "°C"),
    "power_w": ("CC Leistung", "W"),
}


def _last_field(measurement: str, field: str) -> float | None:
    """Return the last value of a field from a tag-less measurement."""
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -2h)
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> last()
'''
    rows = _flux_query(query)
    for row in rows:
        v = _safe_float(row.get("_value"))
        if v is not None:
            return v
    return None


def _history_field(measurement: str, field: str, time_range: str) -> list[dict]:
    """Return [{t, v}, ...] averaged over 15-minute windows for a tag-less measurement."""
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
'''
    rows = _flux_query(query)
    return [{"t": r["_time"], "v": v} for r in rows if (v := _safe_float(r.get("_value"))) is not None and r.get("_time")]


_ENERGIE_FIELDS = ["pv_w", "verbrauch_w", "bezug_w", "einspeisung_w", "laden_w", "entladen_w",
                   "autonomie_pct", "eigenverbrauch_pct"]

_VERBRAUCHER_FIELDS = ["boiler1_w", "boiler2_w", "ir_heizer_w", "waschmaschine_w",
                       "lueftungsanlage_w", "ir_heizer_aktiv",
                       "bad_eg_ir_aktiv", "bad_og_ir_aktiv"]


@app.get("/api/energie/current")
async def energie_current():
    """Current energy values from the PV/inverter system."""
    return JSONResponse({f: _last_field("energie", f) for f in _ENERGIE_FIELDS})


@app.get("/api/energie/history")
async def energie_history(range: str = "24h"):
    """Energy history for all fields. range: 6h | 24h | 7d"""
    return JSONResponse({f: _history_field("energie", f, range) for f in _ENERGIE_FIELDS})


@app.get("/api/verbraucher/current")
async def verbraucher_current():
    """Current power consumption for individual consumers (Loxone meters)."""
    return JSONResponse({f: _last_field("verbraucher", f) for f in _VERBRAUCHER_FIELDS})


@app.get("/api/verbraucher/history")
async def verbraucher_history(range: str = "24h"):
    """Power history for individual consumers. range: 6h | 24h | 7d"""
    return JSONResponse({f: _history_field("verbraucher", f, range) for f in _VERBRAUCHER_FIELDS})


@app.get("/api/comfoclime/current")
async def comfoclime_current():
    """Current ComfoClime 24 heat pump values."""
    return JSONResponse({f: _last_field("comfoclime", f) for f in _COMFOCLIME_FIELDS})


@app.get("/api/comfoclime/history")
async def comfoclime_history(range: str = "24h"):
    """Temperature history for ComfoClime 24. range: 6h | 24h | 7d"""
    return JSONResponse({f: _history_field("comfoclime", f, range) for f in _COMFOCLIME_HISTORY_FIELDS})


@app.get("/api/series")
async def list_series():
    """Return all available series with id, label, unit, and group."""
    vent_t = _last_by_tag("lueftung", "luftstrom", "temp")
    vent_h = _last_by_tag("lueftung", "luftstrom", "hum")
    room_t = _last_by_tag("raumtemperatur", "raum", "temp")
    room_h = _last_by_tag("raumtemperatur", "raum", "hum")

    _ENERGIE_LABELS = {
        "pv_w": "PV Erzeugung", "verbrauch_w": "Verbrauch", "bezug_w": "Netzbezug",
        "einspeisung_w": "Einspeisung", "laden_w": "Batterie laden", "entladen_w": "Batterie entladen",
        "autonomie_pct": "Autarkie", "eigenverbrauch_pct": "Eigenverbrauch",
    }
    _ENERGIE_UNITS = {
        "pv_w": "W", "verbrauch_w": "W", "bezug_w": "W", "einspeisung_w": "W",
        "laden_w": "W", "entladen_w": "W", "autonomie_pct": "%", "eigenverbrauch_pct": "%",
    }
    _VERBRAUCHER_LABELS = {
        "boiler1_w": "Boiler 1", "boiler2_w": "Boiler 2", "ir_heizer_w": "IR-Heizer",
        "waschmaschine_w": "Waschmaschine", "lueftungsanlage_w": "Lüftungsanlage",
        "ir_heizer_aktiv": "IR-Heizer (an/aus)",
        "bad_eg_ir_aktiv": "IR Bad EG (an/aus)", "bad_og_ir_aktiv": "IR Bad OG (an/aus)",
    }
    _VERBRAUCHER_UNITS = {
        "boiler1_w": "W", "boiler2_w": "W", "ir_heizer_w": "W",
        "waschmaschine_w": "W", "lueftungsanlage_w": "W",
        "ir_heizer_aktiv": "", "bad_eg_ir_aktiv": "", "bad_og_ir_aktiv": "",
    }

    series = []
    for field, lbl in _ENERGIE_LABELS.items():
        series.append({"id": f"energie::{field}", "label": lbl, "unit": _ENERGIE_UNITS[field], "group": "Energie"})
    for field, lbl in _VERBRAUCHER_LABELS.items():
        series.append({"id": f"verbraucher::{field}", "label": lbl, "unit": _VERBRAUCHER_UNITS[field], "group": "Verbraucher"})
    for field, (lbl, unit) in _COMFOCLIME_SERIES.items():
        series.append({"id": f"comfoclime::{field}", "label": lbl, "unit": unit, "group": "ComfoClime 24"})
    for stream in sorted(set(vent_t) | set(vent_h)):
        lbl = _VENT_LABELS.get(stream, stream.capitalize())
        for field in ("temp", "hum"):
            if (field == "temp" and stream in vent_t) or (field == "hum" and stream in vent_h):
                series.append({
                    "id": f"lueftung:{stream}:{field}",
                    "label": f"{lbl} ({_FIELD_LABELS[field]})",
                    "unit": _FIELD_UNITS[field],
                    "group": "Lüftung",
                })
    for room in sorted(set(room_t) | set(room_h)):
        for field in ("temp", "hum"):
            if (field == "temp" and room in room_t) or (field == "hum" and room in room_h):
                series.append({
                    "id": f"raumtemperatur:{room}:{field}",
                    "label": f"{room} ({_FIELD_LABELS[field]})",
                    "unit": _FIELD_UNITS[field],
                    "group": "Räume",
                })
    return JSONResponse(series)


@app.get("/api/compare")
async def compare(series: str = Query(default=""), range: str = "24h"):
    """Return history for a comma-separated list of 'measurement:tag_value:field' series."""
    if not series:
        return JSONResponse([])

    result = []
    for s in series.split(","):
        s = s.strip()
        parts = s.split(":")
        if len(parts) != 3:
            continue
        measurement, tag_value, field = parts
        tag_key = _TAG_KEY.get(measurement)
        if measurement not in _TAG_KEY:
            continue

        if tag_key:
            query = f'''from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{range})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}" and r.{tag_key} == "{tag_value}")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
'''
        else:
            query = f'''from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{range})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
'''
        rows = _flux_query(query)
        data = [{"t": r["_time"], "v": v} for r in rows if (v := _safe_float(r.get("_value"))) is not None and r.get("_time")]
        unit = "°C" if field.endswith("_temp_c") else _FIELD_UNITS.get(field, "W")
        result.append({"id": s, "unit": unit, "data": data})

    return JSONResponse(result)
