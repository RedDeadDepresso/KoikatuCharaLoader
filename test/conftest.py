import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CRYPTO_PATH = DATA_DIR / "crypto.json"


@pytest.fixture
def data_dir():
    return DATA_DIR


@pytest.fixture
def hc_crypto():
    if not CRYPTO_PATH.exists():
        pytest.skip("data/crypto.json not found")
    with open(CRYPTO_PATH) as f:
        d = json.load(f)
    return d["key"].encode("utf-8"), d["iv"].encode("utf-8")


def pytest_addoption(parser):
    parser.addoption("--run-optional", action="store_true", help="Run optional tests")
