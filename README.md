# sensor-dashboard

Dark-theme home sensor dashboard. Reads data from InfluxDB v2 and displays live charts with selectable time range (6h / 24h / 7d), auto-refreshing every 60 seconds.

**Sections:** Room climate (temp, humidity, CO2, heating) · Ventilation system (Zehnder Q350 + ComfoClime 24 heat pump) · Energy (PV/inverter) · Consumers · Presence · Series comparison

## Requirements

InfluxDB v2 with the following measurements:

| Measurement | Tag | Fields |
|---|---|---|
| `raumtemperatur` | `raum` | `temp` (°C), `hum` (%), `heating` (0/1), `co2` (ppm) |
| `lueftung` | `luftstrom` | `temp` (°C), `hum` (%) |
| `comfoclime` | — | `mode`, `heat_pump_status`, `tpma_temp_c`, `supply_temp_c`, `set_point_temp_c`, `supply_coil_temp_c`, `exhaust_coil_temp_c`, `power_pct`, `power_w`, `fan_speed`, `supply_air_flow`, `exhaust_air_flow` |
| `q350` | — | `power_w` |
| `energie` | — | `pv_w`, `verbrauch_w`, `bezug_w`, `einspeisung_w`, `laden_w`, `entladen_w`, `autonomie_pct`, `eigenverbrauch_pct` |
| `verbraucher` | — | per-device `*_aktiv` fields (0/1) |
| `presence` | `room` | `active` (0/1) |

Expected `luftstrom` values: `abluft`, `fortluft`, `aussenluft`, `zuluft`

## Installation

### Unraid (one-click)

1. In Unraid, open **Docker → Add Container**
2. Paste the template URL at the bottom of the page:
   ```
   https://raw.githubusercontent.com/mirkofelt/sensor-dashboard/main/sensor-dashboard.xml
   ```
3. Fill in your InfluxDB connection details
4. Click **Apply**

### Docker

```bash
docker run -d \
  --name sensor-dashboard \
  -p 8000:8000 \
  -e INFLUX_HOST=192.168.1.100 \
  -e INFLUX_TOKEN=your-api-token \
  -e INFLUX_ORG=your-org-id \
  ghcr.io/mirkofelt/sensor-dashboard:latest
```

### Docker Compose

```bash
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `INFLUX_HOST` | yes | — | InfluxDB IP address or hostname |
| `INFLUX_PORT` | no | `8086` | InfluxDB port |
| `INFLUX_TOKEN` | yes | — | InfluxDB v2 API token (read access to your bucket) |
| `INFLUX_ORG` | yes | — | InfluxDB organization ID or name |
| `INFLUX_BUCKET` | no | `sensors` | InfluxDB bucket name |
| `DASHBOARD_PORT` | no | `8000` | Host port (Docker Compose only) |

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
uvicorn app:app --reload
```

## API

| Endpoint | Description |
|---|---|
| `GET /` | Dashboard HTML |
| `GET /api/rooms/current` | Latest temp, humidity, heating state, and CO2 per room |
| `GET /api/rooms/history?range=24h` | Temperature history per room |
| `GET /api/rooms/co2history?range=24h` | CO2 history per room |
| `GET /api/lueftungsanlage/current` | Q350 air streams + Cool24 heat pump current values |
| `GET /api/lueftungsanlage/history?range=24h` | Q350 + Cool24 temperature and power history |
| `GET /api/energie/current` | Current PV/energy values |
| `GET /api/energie/history?range=24h` | Energy history |
| `GET /api/verbraucher/current` | Current active/inactive state per consumer |
| `GET /api/verbraucher/history?range=24h` | Consumer state history |
| `GET /api/presence/current` | Current presence state per room |
| `GET /api/presence/history?range=24h` | Presence history per room |
| `GET /api/series` | All available series with id, label, unit, and group |
| `GET /api/compare?series=...&range=24h` | Time-series data for selected series |

Valid `range` values: `6h`, `24h`, `7d`
