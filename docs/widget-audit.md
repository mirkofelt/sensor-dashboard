# Dashboard Widget Audit — CC & Lüftungsanlage

## Summary

The dashboard has one dedicated section for the ventilation system ("Lüftungsanlage") containing two widget types: a current-values grid and a history chart. The ComfoClime 24 (CC) data is embedded inside the Lüftungsanlage section — there is no separate CC section.

---

## Section: Lüftungsanlage (index.html:99–110)

### Widget 1 — Current-values grid (`#lueftung-grid`)

**HTML:** `<div class="vent-grid" id="lueftung-grid"></div>`  
**Populated by:** `loadLueftungsanlageCurrent()` (index.html:450)  
**API endpoint:** `GET /api/lueftungsanlage/current`  
**Backend:** `lueftungsanlage_current()` (app.py:144)

Cards rendered (fixed order, hardcoded in JS):

| Card | Data source | InfluxDB measurement | Field / tag |
|---|---|---|---|
| Außenluft (→Haus) | `q350.aussenluft` | `lueftung` | tag `luftstrom=aussenluft`, fields `temp`, `hum` |
| Zuluft (→Räume) | `q350.zuluft` | `lueftung` | tag `luftstrom=zuluft`, fields `temp`, `hum` |
| Abluft (Haus→) | `q350.abluft` | `lueftung` | tag `luftstrom=abluft`, fields `temp`, `hum` |
| Fortluft (→außen) | `q350.fortluft` | `lueftung` | tag `luftstrom=fortluft`, fields `temp`, `hum` |
| WP Modus | `cool24.mode` | `comfoclime` | field `mode` (0=AUS, 1=HEIZEN, 2=KÜHLEN) |
| CC Zuluft (vor WP) | `cool24.tpma_temp_c` | `comfoclime` | field `tpma_temp_c` |
| CC Zuluft (nach WP) | `cool24.supply_temp_c` | `comfoclime` | field `supply_temp_c` |
| WP Leistung | `cool24.power_w` + `cool24.power_pct` | `comfoclime` | fields `power_w`, `power_pct` |

**Note:** The backend also fetches `heat_pump_status`, `supply_coil_temp_c`, `exhaust_coil_temp_c`, `fan_speed`, `supply_air_flow`, `exhaust_air_flow` from `comfoclime` (app.py:172–178) but none of these are rendered in the current-values grid.

---

### Widget 2 — History chart (`#lueftung-chart`)

**HTML:** `<div class="chart-wrap">` … `<canvas id="lueftung-chart"></canvas>`  
**Populated by:** `loadLueftungsanlageHistory(range)` (index.html:481)  
**API endpoint:** `GET /api/lueftungsanlage/history?range=<6h|24h|7d>`  
**Backend:** `lueftungsanlage_history()` (app.py:159)  
**Default range:** 24h

Datasets rendered in the chart:

| Dataset label | Y-axis | Data source | InfluxDB measurement | Field |
|---|---|---|---|---|
| Q350 Außenluft | y (°C, left) | `q350.aussenluft` | `lueftung` | `temp`, tag `luftstrom=aussenluft` |
| Q350 Abluft | y (°C, left) | `q350.abluft` | `lueftung` | `temp`, tag `luftstrom=abluft` |
| Q350 Fortluft | y (°C, left) | `q350.fortluft` | `lueftung` | `temp`, tag `luftstrom=fortluft` |
| Q350 Zuluft | y (°C, left) | `q350.zuluft` | `lueftung` | `temp`, tag `luftstrom=zuluft` |
| CC Zuluft (vor WP) | y (°C, left) | `cool24.tpma_temp_c` | `comfoclime` | `tpma_temp_c` |
| CC Zuluft (nach WP) | y (°C, left) | `cool24.supply_temp_c` | `comfoclime` | `supply_temp_c` |
| CC Leistung | y1 (W, right, dashed) | `cool24.power_w` | `comfoclime` | `power_w` |

**Aggregation:** 15-minute mean windows (`aggregateWindow(every: 15m, fn: mean)`)

---

## CC Data — Complete InfluxDB Field Mapping

All fields fetched for the `comfoclime` measurement:

| Field | Used in current-values | Used in history chart | Used in Vergleich |
|---|---|---|---|
| `mode` | Yes (WP Modus card) | No | No |
| `heat_pump_status` | Fetched, not rendered | No | No |
| `tpma_temp_c` | Yes (CC Zuluft vor WP) | Yes | Yes (via `/api/series`) |
| `supply_temp_c` | Yes (CC Zuluft nach WP) | Yes | Yes (via `/api/series`) |
| `supply_coil_temp_c` | Fetched, not rendered | No | No |
| `exhaust_coil_temp_c` | Fetched, not rendered | No | No |
| `power_pct` | Yes (sub-label in WP Leistung) | No | No |
| `power_w` | Yes (WP Leistung) | Yes | Yes (via `/api/series`) |
| `fan_speed` | Fetched, not rendered | No | No |
| `supply_air_flow` | Fetched, not rendered | No | No |
| `exhaust_air_flow` | Fetched, not rendered | No | No |

---

## Vergleich (Compare) widget — Lüftungsanlage / CC series

The "Vergleich" section (index.html:112–126) uses `/api/series` to populate selectable chips. Series in the "Lüftungsanlage" group:

| Chip label | Series ID | Source |
|---|---|---|
| Q350 Außenluft (Temp) | `lueftung:aussenluft:temp` | `lueftung` measurement |
| Q350 Außenluft (Feuchte) | `lueftung:aussenluft:hum` | `lueftung` measurement |
| Q350 Abluft (Temp) | `lueftung:abluft:temp` | `lueftung` measurement |
| Q350 Abluft (Feuchte) | `lueftung:abluft:hum` | `lueftung` measurement |
| Q350 Fortluft (Temp) | `lueftung:fortluft:temp` | `lueftung` measurement |
| Q350 Fortluft (Feuchte) | `lueftung:fortluft:hum` | `lueftung` measurement |
| Q350 Zuluft (Temp) | `lueftung:zuluft:temp` | `lueftung` measurement |
| Q350 Zuluft (Feuchte) | `lueftung:zuluft:hum` | `lueftung` measurement |
| CC CC Zuluft (vor WP) | `comfoclime::tpma_temp_c` | `comfoclime` measurement |
| CC CC Zuluft (nach WP) | `comfoclime::supply_temp_c` | `comfoclime` measurement |
| CC CC Leistung | `comfoclime::power_w` | `comfoclime` measurement |

Default pre-selected: `lueftung:aussenluft:temp`, `lueftung:abluft:temp`

---

## Gaps / Observations

1. **7 CC fields fetched but not displayed** — `heat_pump_status`, `supply_coil_temp_c`, `exhaust_coil_temp_c`, `fan_speed`, `supply_air_flow`, `exhaust_air_flow` are all queried from `comfoclime` on every current-data refresh but silently dropped.
2. **CC label duplication** — In `/api/series`, CC series labels are built as `f"CC {lbl}"` where `lbl` already starts with "CC" (e.g. "CC Zuluft (vor WP)"), resulting in "CC CC Zuluft (vor WP)" in the Vergleich chip labels (app.py:353).
3. **Q350 humidity not in history chart** — Only `temp` is tracked historically for Q350 streams; `hum` appears only in current-values cards and Vergleich chips.
4. **`/api/ventilation/*` endpoints exist but are unused** — `GET /api/ventilation/current` and `GET /api/ventilation/history` (app.py:129–141) are legacy endpoints not called by the frontend; `loadLueftungsanlageCurrent()` uses `/api/lueftungsanlage/current` instead.
