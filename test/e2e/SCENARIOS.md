# Gemini-Agent E2E Test Plan (13AUG25)

This document outlines end-to-end (E2E) scenarios to validate the system across API, WebSocket, agent orchestration, and configuration boundaries. Scenarios are designed to be parallelizable and isolated.

## Scope

- Backend FastAPI server in `src/backend_server.py`
- WebSocket endpoint `/ws`
- Basic API endpoints: `/health`, `/start`, `/stop`, `/infer`
- Orchestrator workflow bootstrapping via WebSocket command `execute_workflow` (smoke)
- Non-auth public behavior (auth-only endpoints excluded)

## Parallelization Strategy

- Each worker launches its own backend server on a unique port using a session-scoped fixture.
- Tests are idempotent and avoid writing above `tests/`.

## Scenarios

1. WebSocket connectivity and welcome handshake
   - Connect to `ws://localhost:{port}/ws` with no token
   - Expect initial message with `status: connected`
   - Close cleanly

2. WebSocket echo/error resilience
   - Send invalid JSON -> expect error response
   - Send unknown command -> expect `status: error`

3. REST health endpoint availability
   - GET `/health` -> 200 and `{ "status": "ok" }`

4. REST infer endpoint basic functionality
   - POST `/infer` with `{ "prompt": "hello" }` -> 200 and echo payload

5. Server lifecycle endpoints
   - POST `/start` -> 200 and `{ "status": "started" }`
   - POST `/stop` -> 200 and `{ "status": "stopped" }`

6. Workflow kick-off via WebSocket (smoke)
   - Send command `{ command: "execute_workflow", payload: { workflow_name: "nonexistent" } }`
   - Expect either `workflow_started` or a handled error response (no crash)

7. Concurrency and isolation
   - Run all above in parallel across workers; ensure no port conflicts and clean shutdown.

## Out of Scope (separate suites)

- Auth-required `/api/*` endpoints without valid credentials
- Full multi-agent workflow assertions
- External service integrations (Google APIs, Anthropic, etc.)

## Execution

- Tests live under `tests/e2e/scenarios/`
- Execute with pytest-xdist from the chosen venv:
  - `pytest -q -n auto tests/e2e/scenarios`

## Dependencies

- pytest, pytest-xdist, pytest-asyncio
- requests, websockets

All tests avoid modifying files above `tests/`.
