"""Tests for the sensor dashboard API."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import app, _safe_float, _last_by_tag, _history_by_tag

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def test_safe_float_valid_string():
    assert _safe_float("21.5") == 21.5

def test_safe_float_valid_number():
    assert _safe_float(19.8) == 19.8

def test_safe_float_rounds_to_one_decimal():
    assert _safe_float("21.567") == 21.6

def test_safe_float_none():
    assert _safe_float(None) is None

def test_safe_float_empty_string():
    assert _safe_float("") is None

def test_safe_float_non_numeric():
    assert _safe_float("n/a") is None


# ---------------------------------------------------------------------------
# HTML endpoint
# ---------------------------------------------------------------------------

def test_index_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Room endpoints
# ---------------------------------------------------------------------------

ROOM_ROWS = [
    {"raum": "Wohnzimmer", "_value": "21.5", "_time": "2024-01-01T12:00:00Z"},
    {"raum": "Schlafzimmer", "_value": "19.0", "_time": "2024-01-01T12:00:00Z"},
]

def test_rooms_current_structure():
    with patch("app._flux_query", return_value=ROOM_ROWS):
        response = client.get("/api/rooms/current")
    assert response.status_code == 200
    data = response.json()
    assert "Wohnzimmer" in data
    assert "temp" in data["Wohnzimmer"]
    assert "hum" in data["Wohnzimmer"]

def test_rooms_current_values():
    with patch("app._flux_query", return_value=ROOM_ROWS):
        response = client.get("/api/rooms/current")
    data = response.json()
    assert data["Wohnzimmer"]["temp"] == 21.5
    assert data["Schlafzimmer"]["temp"] == 19.0

def test_rooms_current_empty_influx():
    with patch("app._flux_query", return_value=[]):
        response = client.get("/api/rooms/current")
    assert response.status_code == 200
    assert response.json() == {}

def test_rooms_history_default_range():
    history_rows = [
        {"raum": "Wohnzimmer", "_value": "21.0", "_time": "2024-01-01T10:00:00Z"},
        {"raum": "Wohnzimmer", "_value": "21.5", "_time": "2024-01-01T10:15:00Z"},
    ]
    with patch("app._flux_query", return_value=history_rows):
        response = client.get("/api/rooms/history")
    assert response.status_code == 200
    data = response.json()
    assert "Wohnzimmer" in data
    assert len(data["Wohnzimmer"]) == 2
    assert data["Wohnzimmer"][0] == {"t": "2024-01-01T10:00:00Z", "v": 21.0}

def test_rooms_history_custom_range():
    with patch("app._flux_query", return_value=[]) as mock_q:
        client.get("/api/rooms/history?range=7d")
    # Ensure the range parameter was forwarded into the Flux query
    call_args = mock_q.call_args[0][0]
    assert "7d" in call_args


# ---------------------------------------------------------------------------
# Lüftungsanlage (unified) endpoints
# ---------------------------------------------------------------------------

def test_lueftungsanlage_current_structure():
    with patch("app._last_by_tag", return_value={"zuluft": 18.3, "abluft": 22.1}), \
         patch("app._last_field", return_value=None):
        response = client.get("/api/lueftungsanlage/current")
    assert response.status_code == 200
    data = response.json()
    assert "q350" in data
    assert "cool24" in data
    assert "zuluft" in data["q350"]
    assert "temp" in data["q350"]["zuluft"]
    assert "hum" in data["q350"]["zuluft"]

def test_lueftungsanlage_current_cool24_keys():
    with patch("app._last_by_tag", return_value={}), \
         patch("app._last_field", return_value=None):
        response = client.get("/api/lueftungsanlage/current")
    data = response.json()
    for field in ("mode", "heat_pump_status", "tpma_temp_c", "supply_temp_c"):
        assert field in data["cool24"]

def test_lueftungsanlage_history_range_forwarded():
    with patch("app._history_by_tag", return_value={}) as mock_hbt, \
         patch("app._history_field", return_value=[]):
        client.get("/api/lueftungsanlage/history?range=6h")
    mock_hbt.assert_called_once_with("lueftung", "luftstrom", "temp", "6h")


# ---------------------------------------------------------------------------
# CO2 history endpoint
# ---------------------------------------------------------------------------

CO2_ROWS = [
    {"raum": "Wohnzimmer", "_value": "520.0", "_time": "2024-01-01T10:00:00Z"},
    {"raum": "Wohnzimmer", "_value": "580.0", "_time": "2024-01-01T10:15:00Z"},
]

def test_co2history_structure():
    with patch("app._flux_query", return_value=CO2_ROWS):
        response = client.get("/api/rooms/co2history")
    assert response.status_code == 200
    data = response.json()
    assert "Wohnzimmer" in data
    assert data["Wohnzimmer"][0] == {"t": "2024-01-01T10:00:00Z", "v": 520.0}

def test_co2history_range_forwarded():
    with patch("app._flux_query", return_value=[]) as mock_q:
        client.get("/api/rooms/co2history?range=7d")
    call_args = mock_q.call_args[0][0]
    assert "7d" in call_args
    assert "co2" in call_args


# ---------------------------------------------------------------------------
# Presence endpoints
# ---------------------------------------------------------------------------

PRESENCE_ROWS = [
    {"room": "Wohnzimmer",   "_value": "1.0", "_time": "2024-01-01T12:00:00Z"},
    {"room": "Schlafzimmer", "_value": "0.0", "_time": "2024-01-01T12:00:00Z"},
]

def test_presence_current_structure():
    with patch("app._flux_query", return_value=PRESENCE_ROWS):
        response = client.get("/api/presence/current")
    assert response.status_code == 200
    data = response.json()
    assert data["Wohnzimmer"] == 1.0
    assert data["Schlafzimmer"] == 0.0

def test_presence_current_empty():
    with patch("app._flux_query", return_value=[]):
        response = client.get("/api/presence/current")
    assert response.status_code == 200
    assert response.json() == {}

def test_presence_history_structure():
    history_rows = [
        {"room": "Wohnzimmer", "_value": "1.0", "_time": "2024-01-01T10:00:00Z"},
        {"room": "Wohnzimmer", "_value": "0.0", "_time": "2024-01-01T10:15:00Z"},
    ]
    with patch("app._flux_query", return_value=history_rows):
        response = client.get("/api/presence/history")
    assert response.status_code == 200
    data = response.json()
    assert "Wohnzimmer" in data
    assert data["Wohnzimmer"][0] == {"t": "2024-01-01T10:00:00Z", "v": 1.0}

def test_presence_history_range_forwarded():
    with patch("app._flux_query", return_value=[]) as mock_q:
        client.get("/api/presence/history?range=7d")
    call_args = mock_q.call_args[0][0]
    assert "7d" in call_args
    assert "presence" in call_args
