# ============================================================================
# FILENAME: conftest.py
# PURPOSE: Configuration file for Gemini-Agent
# ============================================================================
# SECTION 1: Imports & Path Configuration
# ============================================================================
#
import asyncio
import json
import os

import pytest
import socket
import subprocess
import sys
import time
import websockets

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List
from loguru import logger


# Add project root to sys.path to allow for absolute imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Import config after path modification
from src.config import LOG_CONFIG, MCP_SERVERS
#
# ============================================================================
# SECTION 2: Logging Configuration
# ============================================================================
#
# Remove default logger to avoid duplicate output
logger.remove()

# Configure file logger for detailed, persistent logs
log_file_path = project_root / "logs" / "test_run.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)

logger.add(
    sink=log_file_path,
    level=LOG_CONFIG['handlers']['file']['level'],
    format=LOG_CONFIG['formatters']['default']['format'],
    rotation=LOG_CONFIG['handlers']['file']['rotation'],
    retention=LOG_CONFIG['handlers']['file']['retention'],
    enqueue=True,  # Make logging thread-safe
    backtrace=True,
    diagnose=True
)

# Configure console logger for immediate, high-level feedback
logger.add(
    sink=sys.stdout,
    level="INFO",
    format=LOG_CONFIG['formatters']['default']['format']
)
#
# ============================================================================
# SECTION 3:  MCP Server Fixtures
# ============================================================================
# Method 3.1: mcp_server
# ============================================================================
#
@pytest.fixture(scope="function")
def mcp_server(request: pytest.FixtureRequest) -> Generator[Dict[str, Any], None, None]:
    """
    Starts and stops MCP servers required by a test.
    The fixture uses the 'mcp_server' mark to determine which servers to start.
    Example: @pytest.mark.mcp_server(servers=['filesystem', 'memory'])
    """
    marker = request.node.get_closest_marker("mcp_server")
    if marker is None:
        required_servers = ['filesystem', 'memory']
    else:
        required_servers = marker.kwargs.get("servers", ['filesystem', 'memory'])

    server_configs = {server['name']: server for server in MCP_SERVERS}
    processes: Dict[str, subprocess.Popen] = {}
    server_endpoints: Dict[str, Any] = {}

    for server_name in required_servers:
        if server_name not in server_configs:
            pytest.fail(f"Unknown MCP server requested: {server_name}")

        config = server_configs[server_name]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

            project_root = Path(__file__).parent.parent
            script_dir = project_root / "tests" / "MCP Servers" / server_name
            script_path = script_dir / "launch-deno-server.bat"

            process = subprocess.Popen(
                [str(script_path), str(port)],
                cwd=str(script_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                shell=True  # Required for running batch files
            )
        processes[server_name] = process

        endpoint = f"http://localhost:{port}"
        server_endpoints[server_name] = {"endpoint": endpoint, "port": port}

        start_time = time.time()
        while time.time() - start_time < 15:  # Increased timeout to 15s
            try:
                with socket.create_connection(("localhost", port), timeout=0.2):
                    logger.info(f"MCP server '{server_name}' started successfully on port {port}.")
                    break
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(0.2)
        else:
            stdout, stderr = process.communicate(timeout=5)
            error_message = (
                f"MCP server '{server_name}' did not start within 15 seconds.\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )
            logger.info(error_message)
            pytest.fail(error_message)

    yield server_endpoints

    logger.info("Tearing down MCP servers...")
    for server_name, process in processes.items():
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning(f"Killed MCP server '{server_name}' as it did not terminate gracefully.")
    logger.info("MCP servers torn down.")
    #
    #
    ## END mcp_server fixture
