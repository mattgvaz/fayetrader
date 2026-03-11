from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import settings
from app.main import app


@pytest.fixture
def tmp_path() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="fayetrader-test-"))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_engine_runtime(tmp_path) -> None:
    original_market = settings.faye_market_data_adapter
    original_broker = settings.faye_broker_adapter
    try:
        settings.faye_market_data_adapter = "mock"
        settings.faye_broker_adapter = "paper"
        routes.engine.reset(runtime_dir=tmp_path / "runtime")
        yield
    finally:
        settings.faye_market_data_adapter = original_market
        settings.faye_broker_adapter = original_broker
