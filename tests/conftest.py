"""Set required env vars and src/ path before app module is imported."""
import os
import sys
from pathlib import Path

# Add src/ to path so tests can import app directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault("INFLUX_HOST", "test-host")
os.environ.setdefault("INFLUX_TOKEN", "test-token")
os.environ.setdefault("INFLUX_ORG", "test-org")
