# CC + Lüftungsanlage — Field Name Mapping

Maps old comfoclime CSV / InfluxDB field names to the current unified source layout
after the Q350 duplicate fields were removed from the CC recorder.

## Evidence sources

| File | Content |
|---|---|
| `home-recorder/comfoclime_2026-05-27.csv` | Old CC CSV — includes now-removed duplicate air-stream temps |
| `home-recorder/lueftung_2026-05-27.csv` | Q350 CSV — unchanged flat field names |
| `home-recorder/recorder.log` | Old CC print format: "Innen / Außen / Zuluft / TPMA / HP-Status / %" |
| `home-recorder/record_comfoclime.py` | Current recorder — duplicate fields removed, InfluxDB write only |
| `home-recorder/record_lueftung.py` | Current Q350 recorder — writes tagged line-protocol |

---

## comfoclime CSV → current InfluxDB destination

Old comfoclime CSV columns (2026-05-27) and what happened to each:

| Old CSV field | Old log label | Status | Current InfluxDB destination |
|---|---|---|---|
| `indoor_temp_c` | "Innen" | **REMOVED** — duplicate | `lueftung,luftstrom=abluft temp` |
| `outdoor_temp_c` | "Außen" | **REMOVED** — duplicate | `lueftung,luftstrom=aussenluft temp` |
| `exhaust_temp_c` | *(not logged)* | **REMOVED** — duplicate | `lueftung,luftstrom=fortluft temp` |
| `fan_speed` | *(not logged)* | kept | `comfoclime fan_speed` (integer) |
| `heat_pump_status` | "HP-Status" | kept | `comfoclime heat_pump_status` (integer) |
| `mode` | "kühl/heiz/aus" | kept | `comfoclime mode` (integer, 0/1/2) |
| `set_point_temp_c` | *(not logged)* | kept in InfluxDB | `comfoclime set_point_temp_c` ⚠️ not in `_COMFOCLIME_FIELDS` — written but never queried |
| `supply_air_flow` | *(not logged)* | kept | `comfoclime supply_air_flow` (integer) |
| `exhaust_air_flow` | *(not logged)* | kept | `comfoclime exhaust_air_flow` (integer) |
| `tpma_temp_c` | "TPMA" | kept | `comfoclime tpma_temp_c` |
| `supply_temp_c` | "Zuluft" ⚠️ | kept | `comfoclime supply_temp_c` |
| `supply_coil_temp_c` | *(not logged)* | kept | `comfoclime supply_coil_temp_c` |
| `exhaust_coil_temp_c` | *(not logged)* | kept | `comfoclime exhaust_coil_temp_c` |
| `power_pct` | "%" | kept | `comfoclime power_pct` |
| `power_w` | *(not logged)* | kept | `comfoclime power_w` |

---

## Q350 (lueftung) CSV → current InfluxDB destination

Unchanged — the Q350 recorder writes tagged line-protocol directly:

| CSV field | InfluxDB measurement | Tag | Field |
|---|---|---|---|
| `abluft_temp_c` | `lueftung` | `luftstrom=abluft` | `temp` |
| `abluft_hum_pct` | `lueftung` | `luftstrom=abluft` | `hum` |
| `fortluft_temp_c` | `lueftung` | `luftstrom=fortluft` | `temp` |
| `fortluft_hum_pct` | `lueftung` | `luftstrom=fortluft` | `hum` |
| `aussenluft_temp_c` | `lueftung` | `luftstrom=aussenluft` | `temp` |
| `aussenluft_hum_pct` | `lueftung` | `luftstrom=aussenluft` | `hum` |
| `zuluft_temp_c` | `lueftung` | `luftstrom=zuluft` | `temp` |
| `zuluft_hum_pct` | `lueftung` | `luftstrom=zuluft` | `hum` |

---

## Cross-source physical sensor equivalences

Where the CC and Q350 measure the same air at the same physical point:

| Old CC field | Q350 field | Physical location | Confirmed equal |
|---|---|---|---|
| `indoor_temp_c` | `abluft_temp_c` | Room air entering unit (Abluft) | Yes — same value in 2026-05-27 CSV (22.4 °C) |
| `outdoor_temp_c` | `aussenluft_temp_c` | Outside air intake | Yes — same value (19.7 °C) |
| `exhaust_temp_c` | `fortluft_temp_c` | Air discharged outside (Fortluft) | Yes — same value (20.4 °C) |

### ⚠️ Confusing name: "Zuluft" ≠ `zuluft`

The old CC log printed `supply_temp_c` as **"Zuluft"**. This is NOT the same as Q350's `zuluft` stream:

| Name | Field | Measurement point |
|---|---|---|
| CC "Zuluft" (old log) | `comfoclime supply_temp_c` | Air supply port **before** heat pump (~12 °C in cooling mode) |
| Q350 Zuluft | `lueftung,luftstrom=zuluft temp` | Final supply air delivered to rooms **after** heat pump (~22 °C) |

These are different physical points ~10 °C apart during active cooling. The dashboard correctly labels `supply_temp_c` as "CC Zuluft (vor WP)" to avoid the ambiguity.

---

## Issues found

### 1. `urllib` missing import in record_comfoclime.py
`_get()` (line 38) calls `urllib.request.urlopen` but `urllib.request` is never imported.
Confirmed broken in recorder.log:
```
NameError: name 'urllib' is not defined (2026-05-28T21:30:01)
```
Fix: add `import urllib.request` at the top of the file.

### 2. `set_point_temp_c` written to InfluxDB but never read
`record_comfoclime.py` writes `set_point_temp_c` to InfluxDB, but it is absent from
`_COMFOCLIME_FIELDS` in `app.py` and therefore never queried or displayed.

### 3. 7 CC fields fetched on every refresh but not rendered
See `widget-audit.md` — `heat_pump_status`, `supply_coil_temp_c`, `exhaust_coil_temp_c`,
`fan_speed`, `supply_air_flow`, `exhaust_air_flow` are in `_COMFOCLIME_FIELDS` and queried,
but the current-values grid and history chart silently discard them.
