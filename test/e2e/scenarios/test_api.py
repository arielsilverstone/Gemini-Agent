# ============================================================================
#  File: test_api.py
#  Version: 1.0
#  Purpose: E2E tests for REST API endpoints exposed by backend_server.py
#  Created: 13AUG25
# ============================================================================
# SECTION 1: Global Variables & Imports
# ============================================================================
#
import pytest
import requests
import socket
import websockets
import asyncio

from typing import Dict

# User-configurable variables
HEALTH_PATH: str = "/health"
START_PATH: str = "/start"
STOP_PATH: str = "/stop"
INFER_PATH: str = "/infer"
TIMEOUT_SECS: int = 5
#
# ============================================================================
# SECTION 2: Tests
# ============================================================================
# Method 2.1:   test_health_ok
# Purpose:      Tests the health endpoint for a successful response.
# Loop comment: send GET request to /health and assert 200 status and {"status":"ok"}.
# ============================================================================
#
def test_health_ok(backend_server: int) -> None:

    r = requests.get(f"http://127.0.0.1:{backend_server}{HEALTH_PATH}", timeout=TIMEOUT_SECS)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert body.get("status") == "ok"
#
# ============================================================================
# Method 2.2:   test_start_stop_lifecycle
# Purpose:      Tests the start and stop endpoints for a successful response.
# Loop comment: send POST request to /start and assert 200 status and {"status":"started"}.
#               send POST request to /stop and assert 200 status and {"status":"stopped"}.
# ============================================================================
#
def test_start_stop_lifecycle(backend_server: int) -> None:

    r1 = requests.post(f"http://127.0.0.1:{backend_server}{START_PATH}", timeout=TIMEOUT_SECS)
    assert r1.status_code == 200
    assert r1.json().get("status") == "started"

    r2 = requests.post(f"http://127.0.0.1:{backend_server}{STOP_PATH}", timeout=TIMEOUT_SECS)
    assert r2.status_code == 200
    assert r2.json().get("status") == "stopped"
#
# ============================================================================
# Method 2.3:   test_infer_echo
# Purpose:      Tests the infer endpoint for a successful response.
# Loop comment: send POST request to /infer and assert 200 status and {"result":"hello"}.
# ============================================================================

def test_infer_echo(backend_server: int) -> None:
    payload: Dict[str, str] = {"prompt": "hello"}
    r = requests.post(f"http://127.0.0.1:{backend_server}{INFER_PATH}", json=payload, timeout=TIMEOUT_SECS)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "hello" in body.get("result", "")
#
#
## End of test_api.py
