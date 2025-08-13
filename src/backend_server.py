# ============================================================================
#  File: backend_server.py
#  Version: 1.04 (Corrected)
# ============================================================================
import sys
import os

# --- PATH FIX ---
# This block forces the project's 'src' directory onto the Python path.
# This makes the script runnable even in a broken environment.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- END PATH FIX ---

import json
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from typing import Optional, TYPE_CHECKING
MINIMAL_STARTUP = str(os.environ.get("GA_MINIMAL_STARTUP", "0")).lower() in {"1", "true", "yes"}

# Type-only imports to satisfy static analysis without importing heavy modules at runtime in minimal mode
if TYPE_CHECKING:
    from src.orchestrator import Orchestrator as _Orchestrator
    from src.websocket_manager import WebSocketManager as _WebSocketManager

# Lazy import heavy components only when not in minimal mode
if not MINIMAL_STARTUP:
    from src.config_manager import ConfigManager
    from src.orchestrator import Orchestrator
    from src.rule_engine import RuleEngine
    from src.websocket_manager import WebSocketManager
    from src.config_validate import validate_config
    from src.secure_secrets import load_secrets

# Remove conflicting PyPaks directory from sys.path
if 'D:\\Program Files\\Dev\\Tools\\PyPaks' in sys.path:
    sys.path.remove('D:\\Program Files\\Dev\\Tools\\PyPaks')

websocket_manager: Optional["_WebSocketManager"] = None
orchestrator: Optional["_Orchestrator"] = None
if not MINIMAL_STARTUP:
    # Initialize application components in the correct order
    config_manager = ConfigManager()
    agent_configs = config_manager.get().llm_configurations
    rule_engine = RuleEngine(config_manager, agent_configs=agent_configs)
    websocket_manager = WebSocketManager()

    # Create a single, definitive Orchestrator instance
    orchestrator = Orchestrator(
        config_manager=config_manager,
        rule_engine=rule_engine,
        websocket_manager=websocket_manager,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application starting up...")
    # Orchestrator is initialized on creation; agents are loaded in its __init__.
    yield
    # Code to run on shutdown
    logger.info("Application shutting down.")
    if orchestrator is not None:
        await orchestrator.shutdown()

app = FastAPI(lifespan=lifespan)
APP_PORT = 9102

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if MINIMAL_STARTUP:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                # Accept plain 'test' or JSON {"type": "test"}
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = data
                if payload == "test" or (isinstance(payload, dict) and payload.get("type") == "test"):
                    await websocket.send_text(json.dumps({"status": "ok"}))
                else:
                    await websocket.send_text(json.dumps({"status": "ok"}))
        except WebSocketDisconnect:
            pass
    else:
        # Ensure components exist
        if websocket_manager is None or orchestrator is None:
            await websocket.accept()
            await websocket.send_text("[ERROR] Server not fully initialized")
            await websocket.close()
            return
        # Accept connection before delegating to manager
        await websocket.accept()
        await websocket_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Example protocol: START_WORKFLOW:workflow_name:initial_task
                if data.startswith("START_WORKFLOW:"):
                    parts = data.split(":", 2)
                    if len(parts) == 3:
                        workflow_name = parts[1]
                        initial_task = parts[2]
                        # Construct a single-step workflow from the websocket message
                        workflow = [{
                            "agent": workflow_name,
                            "task": initial_task,
                            "name": f"WebSocket Task: {workflow_name}"
                        }]
                        _task = asyncio.create_task(orchestrator.run_workflow(workflow))
                    else:
                        await websocket.send_text("[ERROR] Invalid START_WORKFLOW format.")
                elif data.startswith("PING"):
                    await websocket.send_text("PONG")
        except WebSocketDisconnect:
            await websocket_manager.disconnect(websocket)
        except Exception as e:
            await websocket.send_text(f"[ERROR] WebSocket Error: {e}")

# --- Health Endpoint ---
@app.get("/health")
async def health_check():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

# --- API Endpoints (non-minimal only) ---
if not MINIMAL_STARTUP:
    from fastapi import Body

    @app.post("/ipc")
    async def ipc_handler(request: Request):
        try:
            assert orchestrator is not None
            data = await request.json()
            agent = data.get('agent', 'codegen')
            task = data.get('task', '')
            llm_api_key = data.get('llm_api_key', None)
            result = await orchestrator.handle_ipc(agent, task, llm_api_key=llm_api_key)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/get_config")
    async def get_config():
        """
        Retrieves the current application configuration, masking secrets.
        """
        try:
            current_config = config_manager.get()
            config_dict = current_config.model_dump()
            # Mask secrets in config (e.g., API keys, tokens)
            secrets = load_secrets()
            if "llm_configurations" in config_dict:
                for llm, conf in config_dict["llm_configurations"].items():
                    if "api_key" in conf:
                        conf["api_key"] = ""  # Mask
            if "gdrive" in config_dict:
                for k in ["client_id", "client_secret", "refresh_token"]:
                    if k in config_dict["gdrive"]:
                        config_dict["gdrive"][k] = ""  # Mask
            # Mask any other secrets present in secure_secrets
            for k in secrets:
                if k in config_dict:
                    config_dict[k] = ""
            return {"status": "success", "config": config_dict}
        except Exception as e:
            return {"status": "error", "message": f"Failed to retrieve config: {e}"}

    @app.post("/api/save_config")
    async def save_config(payload: dict = Body(...)):
        """
        Saves updated application configuration with schema validation and hot reload.
        """
        try:
            # Load current config for partial update
            current_config = config_manager.get().model_dump()
            def deep_merge(d, u):
                for k, v in u.items():
                    if isinstance(v, dict) and isinstance(d.get(k), dict):
                        d[k] = deep_merge(d[k], v)
                    else:
                        d[k] = v
                return d
            merged = deep_merge(current_config, payload)
            # Validate config before save
            valid, err = validate_config()
            if not valid:
                return {"status": "error", "message": f"Schema validation failed: {err}"}
            config_manager.save(merged)
            assert orchestrator is not None
            orchestrator.reload_config()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to save config: {e}"}

# --- Main Execution ---
def main():
    uvicorn.run(app, host="127.0.0.1", port=APP_PORT)

if __name__ == "__main__":
    main()
