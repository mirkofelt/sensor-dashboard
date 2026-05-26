# sensor-dashboard

Dark-theme home sensor dashboard. Reads room temperatures and ventilation data from InfluxDB v2, displays live charts with selectable time range (6h / 24h / 7d), and auto-refreshes every 60 seconds.

## Requirements

InfluxDB v2 with two measurements:

| Measurement | Tag | Fields |
|---|---|---|
| `raumtemperatur` | `raum` (room name) | `temp` (°C), `hum` (%) |
| `lueftung` | `luftstrom` (air stream) | `temp` (°C), `hum` (%) |

Expected `luftstrom` values: `abluft`, `fortluft`, `aussenluft`, `zuluft`

## Installation

### Unraid (one-click)

1. In Unraid, open **Docker → Add Container**
2. Paste the template URL at the bottom of the page:
   ```
   https://raw.githubusercontent.com/mirkofelt/sensor-dashboard/main/unraid-template.xml
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
| `GET /api/rooms/current` | Latest temp + humidity per room |
| `GET /api/rooms/history?range=24h` | Temperature history per room |
| `GET /api/ventilation/current` | Latest temp + humidity per air stream |
| `GET /api/ventilation/history?range=24h` | Temperature history per air stream |

Valid `range` values: `6h`, `24h`, `7d`
