import os
import sys
from pathlib import Path

os.environ["RV_DATA_MODE"] = "demo"
os.environ["RV_DATA_SOURCE"] = "demo"
os.environ["STAFFING_PERSISTENCE"] = "memory"

API_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = API_ROOT.parents[1] / "packages" / "rv-availability" / "src"
for p in (str(API_ROOT), str(PKG_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.staffing_store import reset_staffing_store_for_tests


@pytest.fixture(scope="function")
def client():
    from app.config import get_settings
    from app.ports.stubs import reset_ports_cache

    get_settings.cache_clear()
    reset_ports_cache()
    reset_staffing_store_for_tests()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token():
    return "dev-simulator-token"


START, END = "2026-12-01", "2027-06-30"
MONTHS = [{"month_key": "2026-12-01", "hours": 40}, {"month_key": "2027-01-01", "hours": 40}]


def _search(client, token, project="P1", **extra):
    body = {
        "project_id": project,
        "start_date": START,
        "end_date": END,
        "launch_token": token,
        "month_hours": MONTHS,
        **extra,
    }
    r = client.post("/api/staffing/pools/search", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def emp(client, token):
    employees = _search(client, token)["employees"]
    assert employees, "demo data must provide a pool"
    return [e["employee_key"] for e in employees]