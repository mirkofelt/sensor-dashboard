"""Set required env vars before app module is imported."""
import os

os.environ.setdefault("INFLUX_HOST", "test-host")
os.environ.setdefault("INFLUX_TOKEN", "test-token")
os.environ.setdefault("INFLUX_ORG", "test-org")
