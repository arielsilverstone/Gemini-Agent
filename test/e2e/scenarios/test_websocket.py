# ============================================================================
#  File: test_websocket.py
#  Version: 1.0
#  Purpose: E2E tests for WebSocket connectivity and basic resilience
#  Created: 13AUG25
# ============================================================================
# SECTION 1: Global Variables & Imports
# ============================================================================

import pytest
import websockets
import asyncio
import json
from typing import Dict


# User-configurable variables
WS_PATH: str = "/ws"
CONNECT_TIMEOUT_SECS: int = 15
MESSAGE_TIMEOUT_SECS: int = 10


# ============================================================================
# SECTION 2: Tests
# ============================================================================
# Async Method 2.1: test_ws_connectivity_handshake
# Purpose: Verify that a client can connect and receive the welcome message.
# Loop comment: connect to the server and assert initial payload has 'status: connected'.
# ============================================================================
#
@pytest.mark.asyncio
async def test_ws_connectivity_handshake(backend_server: int) -> None:

    uri = f"ws://127.0.0.1:{backend_server}{WS_PATH}"
    async with websockets.connect(uri, open_timeout=CONNECT_TIMEOUT_SECS) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)
        data = json.loads(msg)
        assert data.get("status") == "connected"
#
# ============================================================================
# Async Method 2.2: test_ws_invalid_json_returns_error
# Purpose: Send invalid JSON and expect an error response from the server.
# Loop comment: connect to the server and assert initial payload has 'status: connected'.
# ============================================================================

@pytest.mark.asyncio
async def test_ws_invalid_json_returns_error(backend_server: int) -> None:

    uri = f"ws://127.0.0.1:{backend_server}{WS_PATH}"
    async with websockets.connect(uri, open_timeout=CONNECT_TIMEOUT_SECS) as ws:
        # Drain the welcome message first
        _ = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)

        # Send a non-JSON string
        await ws.send("this is not json")
        msg = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)
        data = json.loads(msg)
        assert data.get("status") == "error"
        assert "Invalid JSON" in data.get("message", "")

# ============================================================================
# Async Method 2.3: test_ws_unknown_command_returns_error
# Purpose: Send an unknown command structure; expect an error status.
# Loop comment: connect to the server and assert initial payload has 'status: connected'.
# ============================================================================
#
@pytest.mark.asyncio
async def test_ws_unknown_command_returns_error(backend_server: int) -> None:

    uri = f"ws://127.0.0.1:{backend_server}{WS_PATH}"
    async with websockets.connect(uri, open_timeout=CONNECT_TIMEOUT_SECS) as ws:
        # Drain the welcome message first
        _ = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)

        payload: Dict[str, object] = {"command": "unknown_command", "payload": {}}
        await ws.send(json.dumps(payload))
        msg = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)
        data = json.loads(msg)
        assert data.get("status") == "error"
        assert "Unknown command" in data.get("message", "")

# ============================================================================
# Async Method 2.4: test_ws_execute_workflow_smoke
# Purpose: Smoke test for workflow kickoff via WebSocket; ensure no crash and a handled response.
# Loop comment: connect to the server and assert initial payload has 'status: connected'.
# ============================================================================
#
@pytest.mark.asyncio
async def test_ws_execute_workflow_smoke(backend_server: int) -> None:

    uri = f"ws://127.0.0.1:{backend_server}{WS_PATH}"
    async with websockets.connect(uri, open_timeout=CONNECT_TIMEOUT_SECS) as ws:
        _ = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)

        payload = {
            "command": "execute_workflow",
            "payload": {"workflow_name": "nonexistent", "context": {"test": True}},
        }
        await ws.send(json.dumps(payload))
        msg = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT_SECS)
        data = json.loads(msg)
        # Accept either a start acknowledgement or an error message, but not a crash
        assert data.get("status") in {"workflow_started", "error"}
#
#
## End of test_websocket.py
