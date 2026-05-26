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
# Ventilation endpoints
# ---------------------------------------------------------------------------

VENT_ROWS = [
    {"luftstrom": "zuluft",    "_value": "18.3", "_time": "2024-01-01T12:00:00Z"},
    {"luftstrom": "abluft",    "_value": "22.1", "_time": "2024-01-01T12:00:00Z"},
    {"luftstrom": "aussenluft","_value": "12.4", "_time": "2024-01-01T12:00:00Z"},
    {"luftstrom": "fortluft",  "_value": "8.9",  "_time": "2024-01-01T12:00:00Z"},
]

def test_ventilation_current_structure():
    with patch("app._flux_query", return_value=VENT_ROWS):
        response = client.get("/api/ventilation/current")
    assert response.status_code == 200
    data = response.json()
    for stream in ("zuluft", "abluft", "aussenluft", "fortluft"):
        assert stream in data
        assert "temp" in data[stream]

def test_ventilation_current_values():
    with patch("app._flux_query", return_value=VENT_ROWS):
        response = client.get("/api/ventilation/current")
    data = response.json()
    assert data["zuluft"]["temp"] == 18.3
    assert data["abluft"]["temp"] == 22.1

def test_ventilation_history_range_forwarded():
    with patch("app._flux_query", return_value=[]) as mock_q:
        client.get("/api/ventilation/history?range=6h")
    call_args = mock_q.call_args[0][0]
    assert "6h" in call_args
