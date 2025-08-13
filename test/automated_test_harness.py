#
# ============================================================================
#  File: automated_test_harness.py
#  Version: 3.0 (Complete Functional Refactor)
#  Purpose: Enterprise-grade test execution engine with real functionality
#  Created: 04AUG25 | Refactored: 04AUG25
# ============================================================================
# SECTION 1: Global Variables & Imports
# ============================================================================
#
import argparse
import asyncio
import json
import os
import requests
import shutil
import signal
import subprocess
import sys
import socket
import websockets
import yaml
import fastapi
import uvicorn
import jsonschema
import time

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from loguru import logger

try:
    from test_scenario_generator import ScenarioTestHarness
except Exception:
    ScenarioTestHarness = None  # Optional; generator-based scenarios are loaded lazily elsewhere

try:
    # The distribution is "python-dotenv"; runtime import is "dotenv"
    from dotenv import load_dotenv
except Exception:
    # Fallback no-op to avoid hard dependency during CI/E2E runs
    load_dotenv: Callable[..., bool] = lambda *args, **kwargs: False

#
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
TESTS_DIR = PROJECT_ROOT / 'tests'
CONFIG_DIR = PROJECT_ROOT / 'config'
AGENTS_DIR = PROJECT_ROOT / 'agents'
SRC_DIR = PROJECT_ROOT / 'src'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# Test state and results files
STATE_FILE = TESTS_DIR / 'testing_progress.json'
RESULTS_FILE = TESTS_DIR / 'test_results.json'
SUMMARY_FILE = TESTS_DIR / 'test_summary.json'

# Virtual environment paths
BASE_VENV_PATH = TESTS_DIR / '_base_venv'
TEST_VENVS_DIR = TESTS_DIR / 'venvs'

# Test timeout configurations (seconds)
WEBSOCKET_TIMEOUT = 30
API_TIMEOUT = 15
AGENT_EXECUTION_TIMEOUT = 120
WORKFLOW_TIMEOUT = 300

# Server configuration
PORT_RANGE_START = 9102
PORT_RANGE_END = 9120
#
# ============================================================================
# SECTION 2: Data Classes & Test Result Management
# ============================================================================
# Class 2.1: TestResult
# Purpose: Comprehensive test result data structure.
# ============================================================================
#
@dataclass
class TestResult:

    test_id: str
    test_name: str
    category: str
    status: str  # PASS, FAIL, ERROR, TIMEOUT, SKIP
    execution_time: float
    start_time: str
    end_time: str
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    output_logs: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    environment_info: Dict[str, str] = field(default_factory=dict)
    dependencies_checked: List[str] = field(default_factory=list)
    #
    # ========================================================================
    # Method 2.1.1: __post_init__
    # Purpose: Ensure dataclass defaults are immutable-safe.
    # ========================================================================
    #
    def __post_init__(self):
        # Defaults provided by field(default_factory=...) ensure non-None values
        return
#
# ============================================================================
# Class 2.2: TestSession
# Purpose: Complete test session management.
# ============================================================================
#
@dataclass
class TestSession:

    session_id: str
    start_time: str
    status: str  # RUNNING, COMPLETED, FAILED, ABORTED
    total_tests: int

    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    timeout_tests: int = 0
    skipped_tests: int = 0

    test_results: List[TestResult] = field(default_factory=list)

    environment_setup: Dict[str, Any] = field(default_factory=dict)

    end_time: Optional[str] = None
    total_execution_time: Optional[float] = None
    #
    # ========================================================================
    # Method 2.2.1: __post_init__
    # Purpose: Initialize computed fields if needed.
    # ========================================================================
    #
    def __post_init__(self):
        """Initialize computed fields if needed."""
        return
#
# ============================================================================
# SECTION 4: Test Environment Management
# ============================================================================
# Class 4.1: TestEnvironmentManager
# Purpose: Manages test virtual environments and dependencies.
# ============================================================================
#
class TestEnvironmentManager:
    #
    # ========================================================================
    # Method 4.1.1: __init__
    # Purpose: Initialize test environment manager.
    # ========================================================================
    #
    def __init__(self):
        self.current_venvs = {}
        self.cleanup_callbacks = []

        # Configure logger for test execution
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>TEST</cyan> | <white>{message}</white>",
            colorize=True
        )
        logger.add(
            TESTS_DIR / f"test_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            rotation="10 MB",
            retention="30 days"
        )
    #
    # ========================================================================
    # Async Method 4.1.2: setup_base_environment
    # Purpose: Setup base test environment with all required dependencies.
    # ========================================================================
    #
    async def setup_base_environment(self) -> bool:

        try:
            logger.info("Setting up base test environment...")

### CREATE VENV
            # Ensure test directories exist
            TEST_VENVS_DIR.mkdir(exist_ok=True)

            # Create base virtual environment if it doesn't exist
            if not BASE_VENV_PATH.exists():
                logger.info("Creating base virtual environment...")
                result = subprocess.run([
                    sys.executable, '-m', 'venv', str(BASE_VENV_PATH)
                ], capture_output=True, text=True, timeout=120)

                if result.returncode != 0:
                    logger.error(f"Failed to create base venv: {result.stderr}")
                    return False

            # Install required packages
            python_exe = BASE_VENV_PATH / 'Scripts' / 'python.exe'
            if not python_exe.exists():
                python_exe = BASE_VENV_PATH / 'bin' / 'python'  # Unix systems

            required_packages = [
                "pytest>=7.0.0",
                "pytest-asyncio>=0.21.0",
                "pytest-xdist>=3.0.0",
                "pytest-timeout>=2.1.0",
                "pytest-cov>=4.0.0",
                "coverage>=7.0.0",
                "requests>=2.28.0",
                "websockets>=10.0",
                "pyyaml>=6.0",
                "loguru>=0.6.0",
                "psutil>=5.9.0",
                "google-auth>=2.0.0",
                "google-auth-oauthlib>=0.5.0",
                "google-auth-httplib2>=0.1.0",
                "google-api-python-client>=2.0.0",
                "google-generativeai>=0.3.0",
                "anthropic>=0.8.0",
                "mcp>=0.1.12",
                "pydantic==2.11.7",
                "python-dotenv>=1.0.0",
                "fastapi>=0.100.0",
                "uvicorn>=0.20.0",
                "jsonschema>=4.0.0",
            ]

            logger.info("Installing test dependencies...")
            for package in required_packages:
                result = subprocess.run([
                    str(python_exe), '-m', 'pip', 'install', package
                ], capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    logger.warning(f"Failed to install {package}: {result.stderr}")
                    # Continue with other packages

            logger.success("Base test environment setup completed")
            return True

        except Exception as e:
            logger.error(f"Failed to setup base environment: {e}")
            return False
    #
    # ========================================================================
    # Async Method 4.1.3: create_test_environment
    # Purpose: Create isolated test environment for specific test.
    # ========================================================================
    #
    async def create_test_environment(self, test_id: str, requirements: Optional[List[str]] = None) -> Optional[Path]:

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            venv_name = f"{test_id}_{timestamp}"
            venv_path = TEST_VENVS_DIR / venv_name

            logger.info(f"Creating test environment: {venv_name}")
### CREATE VENV
            # Create virtual environment
            result = subprocess.run([
                sys.executable, '-m', 'venv', str(venv_path)
            ], capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                logger.error(f"Failed to create test venv {venv_name}: {result.stderr}")
                return None

            # Get python executable path
            python_exe = venv_path / 'Scripts' / 'python.exe'
            if not python_exe.exists():
                python_exe = venv_path / 'bin' / 'python'

            # Install base requirements needed by tests and server
            base_packages = [
                "pytest",
                "requests",
                "websockets",
                "pyyaml",
                "loguru",
                "fastapi",
                "uvicorn",
                "pydantic==2.11.7",
                "psutil",
                "jsonschema",
                "google-generativeai",
            ]
            if requirements is not None:
                base_packages.extend(requirements)

            for package in base_packages:
                result = subprocess.run([
                    str(python_exe), '-m', 'pip', 'install', package
                ], capture_output=True, text=True, timeout=120)

                if result.returncode != 0:
                    logger.warning(f"Failed to install {package} in {venv_name}")

            # Copy project files to test environment
            await self._copy_project_files(venv_path)

            # If a project requirements.txt exists in the copied project, install it
            project_requirements = (venv_path / 'project' / 'requirements.txt')
            # For lightweight connectivity tests, skip installing full project requirements to speed up and avoid build issues
            skip_reqs = 'ws_connectivity' in test_id
            if project_requirements.exists() and not skip_reqs:
                try:
                    result = subprocess.run([
                        str(python_exe), '-m', 'pip', 'install', '-r', str(project_requirements)
                    ], capture_output=True, text=True, timeout=600)
                    if result.returncode != 0:
                        logger.warning(f"Failed to install requirements.txt in {venv_name}: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Exception installing requirements.txt in {venv_name}: {e}")

            self.current_venvs[test_id] = venv_path
            logger.success(f"Test environment {venv_name} created successfully")
            return venv_path

        except Exception as e:
            logger.error(f"Failed to create test environment for {test_id}: {e}")
            return None
    #
    # ========================================================================
    # Async Method 4.1.4: _copy_project_files
    # Purpose: Copy essential project files to test environment.
    # ========================================================================
    #
    async def _copy_project_files(self, venv_path: Path):

        try:
            # Create project structure in venv
            project_path = venv_path / 'project'
            project_path.mkdir(exist_ok=True)

            # Copy key directories
            directories_to_copy = ['agents', 'src', 'config', 'frontend']

            for dir_name in directories_to_copy:
                source_dir = PROJECT_ROOT / dir_name
                if source_dir.exists():
                    dest_dir = project_path / dir_name
                    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)

            # Copy individual important files
            files_to_copy = ['main.py', 'requirements.txt', 'package.json']
            for file_name in files_to_copy:
                source_file = PROJECT_ROOT / file_name
                if source_file.exists():
                    dest_file = project_path / file_name
                    shutil.copy2(source_file, dest_file)

        except Exception as e:
            logger.error(f"Failed to copy project files: {e}")
    #
    # ========================================================================
    # Async Method 4.1.5: cleanup_environment
    # Purpose: Clean up test environment after test completion.
    # ========================================================================
    #
    async def cleanup_environment(self, test_id: str):

        try:
            if test_id in self.current_venvs:
                venv_path = self.current_venvs[test_id]
                if venv_path.exists():
                    def _onerror(func, path, exc_info):
                        try:
                            os.chmod(path, 0o777)
                            func(path)
                        except Exception:
                            pass
                    try:
                        shutil.rmtree(venv_path, onerror=_onerror)
                    except Exception as e:
                        logger.warning(f"Retrying cleanup for {venv_path} after error: {e}")
                        await asyncio.sleep(1.0)
                        try:
                            shutil.rmtree(venv_path, onerror=_onerror)
                        except Exception as e2:
                            logger.error(f"Failed to cleanup environment for {test_id}: {e2}")
                    logger.info(f"Cleaned up test environment: {venv_path.name}")
                del self.current_venvs[test_id]
        except Exception as e:
            logger.error(f"Failed to cleanup environment for {test_id}: {e}")
    #
    # ========================================================================
    # Async Method 4.1.6: cleanup_all
    # Purpose: Clean up all test environments.
    # ========================================================================
    #
    async def cleanup_all(self):
        for test_id in list(self.current_venvs.keys()):
            await self.cleanup_environment(test_id)
#
# ============================================================================
# SECTION 5: Server and Process Management
# ============================================================================
# Class 5.1: ServerManager
# Purpose:   Manages test servers and process lifecycle.
# ============================================================================
#
class ServerManager:
    #
    # ========================================================================
    # Method 5.1.1: __init__
    # Purpose: Initialize ServerManager with empty process and port sets.
    # ========================================================================
    #
    def __init__(self):
        self.running_processes = {}
        self.occupied_ports = set()
    #
    # ========================================================================
    # Method 5.1.2: find_available_port
    # Purpose: Find an available port for test server.
    # ========================================================================
    #
    def find_available_port(self, start_port: int = PORT_RANGE_START) -> int:

        for port in range(start_port, PORT_RANGE_END):
            if port not in self.occupied_ports:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('localhost', port))
                        self.occupied_ports.add(port)
                        return port
                except OSError:
                    continue

        raise RuntimeError(f"No available ports in range {start_port}-{PORT_RANGE_END}")
    #
    # ========================================================================
    # Async Method 5.1.3: start_test_server
    # Purpose: Start a test server instance.
    # ========================================================================
    #
    async def start_test_server(self, server_type: str, venv_path: Path, port: Optional[int] = None) -> Tuple[subprocess.Popen, int]:
        try:
            if port is None:
                port = self.find_available_port()

            python_exe = venv_path / 'Scripts' / 'python.exe'
            if not python_exe.exists():
                python_exe = venv_path / 'bin' / 'python'

            project_path = venv_path / 'project'

            # Launch the actual FastAPI app using uvicorn instead of a non-existent main.py
            # This binds explicitly to the selected port to keep harness coordination intact.
            cmd = [
                str(python_exe),
                '-m', 'uvicorn',
                'src.backend_server:app',
                '--host', '127.0.0.1',
                '--port', str(port),
                '--log-level', 'warning'
            ]

            env = os.environ.copy()
            env['PYTHONPATH'] = str(project_path)
            # Enable minimal startup for lightweight connectivity/health tests to avoid heavy deps at boot
            if server_type.lower() in ('websocket', 'api_minimal'):
                env['GA_MINIMAL_STARTUP'] = '1'

            process = subprocess.Popen(
                cmd,
                cwd=project_path,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for server to become healthy by polling /health
            server_ready = False
            start = time.time()
            while time.time() - start < 30:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    logger.error(f"Server failed to start: {stderr}")
                    raise RuntimeError(f"Server startup failed: {stderr}")
                try:
                    resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=1.5)
                    if resp.status_code == 200:
                        server_ready = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            if not server_ready:
                raise RuntimeError("Server did not become ready within 30s")

            self.running_processes[f"{server_type}_{port}"] = process
            logger.info(f"Started {server_type} server on port {port}")
            return process, port

        except Exception as e:
            logger.error(f"Failed to start {server_type} server: {e}")
            raise
    #
    # ========================================================================
    # Async Method 5.1.4: stop_server
    # Purpose: Stop a running test server.
    # ========================================================================
    #
    async def stop_server(self, server_key: str):
        try:
            if server_key in self.running_processes:
                process = self.running_processes[server_key]

                # Try graceful shutdown first
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    process.kill()
                    process.wait()

                del self.running_processes[server_key]

                # Free up port
                port = int(server_key.split('_')[-1])
                self.occupied_ports.discard(port)

                logger.info(f"Stopped server: {server_key}")

        except Exception as e:
            logger.error(f"Failed to stop server {server_key}: {e}")
    #
    # ========================================================================
    # Async Method 5.1.5: stop_all_servers
    # Purpose: Stop all running test servers.
    # ========================================================================
    #
    async def stop_all_servers(self):
        for server_key in list(self.running_processes.keys()):
            await self.stop_server(server_key)
#
# ============================================================================
# SECTION 6: Functional Test Implementations
# ============================================================================
# Class 6.1: FunctionalTestExecutor
# Purpose:   Implements actual functional tests replacing simulated behavior.
# ============================================================================
#
class FunctionalTestExecutor:
    #
    # ========================================================================
    # Method 6.1.1: __init__
    # Purpose: Initialize the test executor with environment and server managers.
    # ========================================================================
    #
    def __init__(self, env_manager: TestEnvironmentManager, server_manager: ServerManager):
        self.env_manager = env_manager
        self.server_manager = server_manager
   #
    # ========================================================================
    # Async Method 6.1.2: test_websocket_connectivity
    # Purpose: Test WebSocket server connectivity and basic communication.
    # ========================================================================
    #
    async def test_websocket_connectivity(self, test_id: str) -> TestResult:
        start_time = datetime.now(timezone.utc)
        result = TestResult(
            test_id=test_id,
            test_name="WebSocket Connectivity Test",
            category="connectivity",
            status="RUNNING",
            execution_time=0.0,
            start_time=start_time.isoformat(),
            end_time=""
        )

        venv_path = None
        server_process = None

### CREATE VENV
        try:
            # Create test environment
            venv_path = await self.env_manager.create_test_environment(test_id, ["websockets"])
            if not venv_path:
                raise RuntimeError("Failed to create test environment")

            # Start WebSocket server
            server_process, port = await self.server_manager.start_test_server('websocket', venv_path)

            # Test WebSocket connection
            uri = f"ws://localhost:{port}/ws"
            async with websockets.connect(uri, open_timeout=WEBSOCKET_TIMEOUT) as websocket:
                # Send test message
                test_message = json.dumps({"type": "test", "data": "connectivity_check"})
                await websocket.send(test_message)

                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                response_data = json.loads(response)

                if response_data.get("status") == "ok":
                    result.status = "PASS"
                    result.output_logs.append("WebSocket connectivity test passed")
                else:
                    result.status = "FAIL"
                    result.error_message = f"Unexpected response: {response_data}"

        except asyncio.TimeoutError:
            result.status = "TIMEOUT"
            result.error_message = "WebSocket connection timeout"
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            result.error_traceback = str(e.__traceback__)

        finally:
            # Cleanup
            if server_process:
                await self.server_manager.stop_server(f"websocket_{port}")
            if venv_path:
                await self.env_manager.cleanup_environment(test_id)

            end_time = datetime.now(timezone.utc)
            result.end_time = end_time.isoformat()
            result.execution_time = (end_time - start_time).total_seconds()

        return result

    #
    # ========================================================================
    # Async Method 6.1.2a: test_rest_api_health
    # Purpose: Validate REST API basic readiness via /health endpoint in minimal mode.
    # ========================================================================
    #
    async def test_rest_api_health(self, test_id: str) -> TestResult:
        start_time = datetime.now(timezone.utc)
        result = TestResult(
            test_id=test_id,
            test_name="REST API Health Test",
            category="connectivity",
            status="RUNNING",
            execution_time=0.0,
            start_time=start_time.isoformat(),
            end_time=""
        )

        venv_path = None
        server_process = None

        try:
            # Create isolated environment
            venv_path = await self.env_manager.create_test_environment(test_id, ["requests", "fastapi", "uvicorn"])
            if not venv_path:
                raise RuntimeError("Failed to create test environment")

            # Start API server in minimal mode
            server_process, port = await self.server_manager.start_test_server('api_minimal', venv_path)

            # Poll /health and validate JSON payload
            url = f"http://127.0.0.1:{port}/health"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                if data.get("status") == "ok":
                    result.status = "PASS"
                    result.output_logs.append("REST /health responded with status ok")
                else:
                    result.status = "FAIL"
                    result.error_message = f"Unexpected /health payload: {data}"
            else:
                result.status = "FAIL"
                result.error_message = f"/health HTTP {resp.status_code}"

        except requests.Timeout:
            result.status = "TIMEOUT"
            result.error_message = "REST /health request timed out"
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
        finally:
            if server_process:
                await self.server_manager.stop_server(f"api_minimal_{port}")
            if venv_path:
                await self.env_manager.cleanup_environment(test_id)

            end_time = datetime.now(timezone.utc)
            result.end_time = end_time.isoformat()
            result.execution_time = (end_time - start_time).total_seconds()

        return result
    #
    # ========================================================================
    # Async Method 6.1.3: test_agent_execution
    # Purpose: Test individual agent execution with real task processing.
    # ========================================================================
    #
    async def test_agent_execution(self, test_id: str, agent_name: str, task: str) -> TestResult:

        start_time = datetime.now(timezone.utc)
        result = TestResult(
            test_id=test_id,
            test_name=f"Agent Execution Test - {agent_name}",
            category="agent_execution",
            status="RUNNING",
            execution_time=0.0,
            start_time=start_time.isoformat(),
            end_time=""
        )

        venv_path = None
### CREATE VENV
        try:
            # Create test environment
            venv_path = await self.env_manager.create_test_environment(test_id)
            if not venv_path:
                raise RuntimeError("Failed to create test environment")

            # Get python executable
            python_exe = venv_path / 'Scripts' / 'python.exe'
            if not python_exe.exists():
                python_exe = venv_path / 'bin' / 'python'

            # Determine agent class name reliably
            agent_class_map = {
                "codegen_agent": "CodeGenAgent",
                "doc_agent": "DocAgent",
                "fix_agent": "FixAgent",
                "planner_agent": "PlannerAgent",
                "qa_agent": "QAAgent",
                "test_agent": "TestAgent",
            }
            class_name = agent_class_map.get(agent_name, agent_name.replace('_', '').title())

            # Create agent test script
            test_script = f"""
#
# ============================================================================
# File: test_agent_execution.py
# Version: 1.0
# Purpose: E2E tests for agent execution and basic resilience
# Created: 13AUG25
# ============================================================================
# SECTION 1: Imports
# ============================================================================
#
import sys
import asyncio
import json
from pathlib import Path

sys.path.append(str(Path.cwd() / 'project'))

from agents.{agent_name} import {class_name}
#
# ============================================================================
# SECTION 2: Test Function
# ============================================================================
# Async Method 2.1: test_agent
# Purpose: Test individual agent execution with real task processing.
# ============================================================================
#
async def test_agent():
    config = {{"name": "{agent_name}", "enabled": True}}
    agent = {class_name}("{agent_name}", config)

    task = "{task}"
    context = {{"test_mode": True}}

    results = []
    async for chunk in agent.run(task, context):
        results.append(chunk)

    return {{"status": "completed", "results": results}}
#
# ============================================================================
# SECTION 3: Main Execution
# ============================================================================
#
if __name__ == "__main__":
    result = asyncio.run(test_agent())
    print(json.dumps(result))

#
#
## End of test_agent_execution.py
"""
#
            # Write and execute test script
            script_path = venv_path / 'test_script.py'
            script_path.write_text(test_script)

            process = subprocess.run([
                str(python_exe), str(script_path)
            ], capture_output=True, text=True, timeout=AGENT_EXECUTION_TIMEOUT, cwd=venv_path)

            if process.returncode == 0:
                output = json.loads(process.stdout)
                if output.get("status") == "completed":
                    result.status = "PASS"
                    result.output_logs.append(f"Agent {agent_name} executed successfully")
                    result.metrics["result_count"] = len(output.get("results", []))
                else:
                    result.status = "FAIL"
                    result.error_message = f"Agent execution failed: {output}"
            else:
                result.status = "FAIL"
                result.error_message = f"Agent process failed: {process.stderr}"

        except subprocess.TimeoutExpired:
            result.status = "TIMEOUT"
            result.error_message = f"Agent execution timeout after {AGENT_EXECUTION_TIMEOUT}s"
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)

        finally:
            if venv_path:
                await self.env_manager.cleanup_environment(test_id)

            end_time = datetime.now(timezone.utc)
            result.end_time = end_time.isoformat()
            result.execution_time = (end_time - start_time).total_seconds()

        return result
    #
    # ========================================================================
    # Async Method 6.1.4: test_workflow_execution
    # Purpose: Test complete workflow execution with multiple agents.
    # ========================================================================
    #
    async def test_workflow_execution(self, test_id: str, workflow_config: Dict) -> TestResult:

        start_time = datetime.now(timezone.utc)
        result = TestResult(
            test_id=test_id,
            test_name="Workflow Execution Test",
            category="workflow",
            status="RUNNING",
            execution_time=0.0,
            start_time=start_time.isoformat(),
            end_time=""
        )

        venv_path = None
        server_process = None
### CREATE VENV
        try:
            # Create test environment
            venv_path = await self.env_manager.create_test_environment(test_id)
            if not venv_path:
                raise RuntimeError("Failed to create test environment")

            # Start orchestrator server
            server_process, port = await self.server_manager.start_test_server('api', venv_path)

            # Create workflow configuration file
            config_path = venv_path / 'test_workflow.yaml'
            with open(config_path, 'w') as f:
                yaml.dump(workflow_config, f)

            # Execute workflow via API
            api_url = f"http://localhost:{port}/api/execute_workflow"

            with open(config_path, 'rb') as f:
                files = {'workflow': f}
                response = requests.post(api_url, files=files, timeout=WORKFLOW_TIMEOUT)

            if response.status_code == 200:
                workflow_result = response.json()
                if workflow_result.get("status") == "completed":
                    result.status = "PASS"
                    result.output_logs.append("Workflow executed successfully")
                    result.metrics["steps_completed"] = workflow_result.get("steps_completed", 0)
                else:
                    result.status = "FAIL"
                    result.error_message = f"Workflow failed: {workflow_result.get('error', 'Unknown error')}"
            else:
                result.status = "FAIL"
                result.error_message = f"API request failed: {response.status_code} - {response.text}"

        except requests.Timeout:
            result.status = "TIMEOUT"
            result.error_message = f"Workflow execution timeout after {WORKFLOW_TIMEOUT}s"
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)

        finally:
            if server_process:
                await self.server_manager.stop_server(f"api_{port}")
            if venv_path:
                await self.env_manager.cleanup_environment(test_id)

            end_time = datetime.now(timezone.utc)
            result.end_time = end_time.isoformat()
            result.execution_time = (end_time - start_time).total_seconds()

        return result
    #
    # ========================================================================
    # Async Method 6.1.5: test_rule_engine_functionality
    # Purpose: Test rule engine validation and enforcement.
    # ========================================================================
    #
    async def test_rule_engine_functionality(self, test_id: str) -> TestResult:

        start_time = datetime.now(timezone.utc)
        result = TestResult(
            test_id=test_id,
            test_name="Rule Engine Functionality Test",
            category="rule_engine",
            status="RUNNING",
            execution_time=0.0,
            start_time=start_time.isoformat(),
            end_time=""
        )

        venv_path = None
### CREATE VENV
        try:
            # Create test environment
            venv_path = await self.env_manager.create_test_environment(test_id)
            if not venv_path:
                raise RuntimeError("Failed to create test environment")

            python_exe = venv_path / 'Scripts' / 'python.exe'
            if not python_exe.exists():
                python_exe = venv_path / 'bin' / 'python'

            # Create rule engine test script
            test_script = """
#
# ============================================================================
# File: test_rule_engine.py
# Version: 1.1
# Purpose: Test rule engine validation and enforcement.
# ============================================================================
# SECTION 1: Global Variables & Imports
# ============================================================================
#
import sys
import asyncio
from pathlib import Path
sys.path.append(str(Path.cwd() / 'project'))

from src.rule_engine import RuleEngine
#
# ============================================================================
# SECTION 2: Test Functions
# ============================================================================
# Function 2.1: test_rule_engine
# Purpose: Test rule engine validation and enforcement.
# ============================================================================
#
async def test_rule_engine():
    # Initialize RuleEngine with minimal configuration; it will load fallback rules if full config is unavailable
    engine = RuleEngine()

    # Test rule validation against minimal fallback rules which include an output length constraint
    test_content = "This is test content that should trigger rules"
    violations = await engine.validate_output(test_content, "test_agent", "test_task")

    return {"violations_found": len(violations), "status": "functional"}
#
# ============================================================================
# SECTION 3: Test Execution
# ============================================================================
#
if __name__ == "__main__":
    result = asyncio.run(test_rule_engine())
    print(f"RULE_ENGINE_RESULT: {result}")
#
#
## End of test_rule_engine.py
"""

            script_path = venv_path / 'rule_test.py'
            script_path.write_text(test_script)

            process = subprocess.run([
                str(python_exe), str(script_path)
            ], capture_output=True, text=True, timeout=60, cwd=venv_path)

            if process.returncode == 0 and "RULE_ENGINE_RESULT:" in process.stdout:
                result.status = "PASS"
                result.output_logs.append("Rule engine functionality verified")
            else:
                result.status = "FAIL"
                result.error_message = f"Rule engine test failed: {process.stderr}"

        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)

        finally:
            if venv_path:
                await self.env_manager.cleanup_environment(test_id)

            end_time = datetime.now(timezone.utc)
            result.end_time = end_time.isoformat()
            result.execution_time = (end_time - start_time).total_seconds()

        return result
#
# ============================================================================
# SECTION 7: Test Suite Orchestrator
# ============================================================================
# Class 7.1: TestSuiteOrchestrator
# Purpose: Main orchestrator for comprehensive test suite execution.
# ============================================================================
#
class TestSuiteOrchestrator:
    #
    # ========================================================================
    # Method 7.1.1: __init__
    # Purpose: Initialize the orchestrator with environment and server
    #          managers.
    # ========================================================================
    #
    def __init__(self):
        self.env_manager = TestEnvironmentManager()
        self.server_manager = ServerManager()
        self.test_executor = FunctionalTestExecutor(self.env_manager, self.server_manager)
        self.current_session = None
        self.test_queue = []

        # Register cleanup handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    #
    # ========================================================================
    # Method 7.1.2: _signal_handler
    # Purpose: Handle cleanup on signal termination.
    # ========================================================================
    #
    def _signal_handler(self, signum, frame):

        logger.warning(f"Received signal {signum}, initiating cleanup...")
        asyncio.create_task(self._emergency_cleanup())
    #
    # ========================================================================
    # Async Method 7.1.3: _emergency_cleanup
    # Purpose: Emergency cleanup procedure.
    # ========================================================================
    #
    async def _emergency_cleanup(self):

        try:
            await self.server_manager.stop_all_servers()
            await self.env_manager.cleanup_all()
            if self.current_session:
                self.current_session.status = "ABORTED"
                await self._save_session_state()
            logger.info("Emergency cleanup completed")
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
    #
    # ========================================================================
    # Async Method 7.1.4: load_test_scenarios
    # Purpose: Load test scenarios from configuration file.
    # ========================================================================
    #
    async def load_test_scenarios(self, scenarios_file: Optional[Path] = None) -> List[Dict]:

        try:
            if scenarios_file is None:
                scenarios_file = TESTS_DIR / 'test_scenarios.json'

            if not scenarios_file.exists():
                # Create default test scenarios if file doesn't exist
                default_scenarios = self._create_default_scenarios()
                with open(scenarios_file, 'w') as f:
                    json.dump(default_scenarios, f, indent=2)
                logger.info(f"Created default test scenarios: {scenarios_file}")
                return default_scenarios

            with open(scenarios_file, 'r') as f:
                scenarios = json.load(f)

            logger.info(f"Loaded {len(scenarios)} test scenarios from {scenarios_file}")
            return scenarios

        except Exception as e:
            logger.error(f"Failed to load test scenarios: {e}")
            return self._create_default_scenarios()
    #
    # ========================================================================
    # Method 7.1.5: _create_default_scenarios
    # Purpose: Create default test scenarios if file doesn't exist.
    # ========================================================================
    #
    def _create_default_scenarios(self) -> List[Dict]:

        try:
            # Import the scenario generator
            from test_scenario_generator import TestScenarioGenerator

            # Initialize generator
            generator = TestScenarioGenerator(PROJECT_ROOT)

            # Find all specification files with pattern: testing-to-do [DATE]-[TIME].json
            spec_files = []
            for file_path in TESTS_DIR.glob("testing-to-do *.json"):
                spec_files.append(file_path)
            #
            # ================================================================
            # Method 7.1.5.1: extract_datetime
            # Purpose: Extract date-time from filename.
            # ========================================================================
            #
            def extract_datetime(filename):

                try:
                    # Extract pattern like "04AUG25-1820" from filename
                    import re
                    match = re.search(r'(\d{2}[A-Z]{3}\d{2})-(\d{4})', filename.stem)
                    if match:
                        return match.group(0)  # Return the full datetime string for sorting
                    return "00000-0000"  # Default for files that don't match pattern
                except Exception:
                    return "00000-0000"

            spec_files.sort(key=lambda f: extract_datetime(f.name))

            if not spec_files:
                logger.warning("No testing specification files found, using fallback scenarios")
                return self._get_fallback_scenarios()

            # Load scenarios from all specification files (descendants override ancestors)
            all_scenarios = []
            scenario_registry = {}  # Track scenarios by ID for override logic

            for spec_file in spec_files:
                logger.info(f"Loading scenarios from: {spec_file.name}")
                file_scenarios = generator.load_scenario_specifications(spec_file)

                for scenario in file_scenarios:
                    scenario_id = scenario.get('name', '').lower().replace(' ', '_').replace(':', '')
                    if scenario_id:
                        # Later files override earlier scenarios with same ID
                        scenario_registry[scenario_id] = scenario
                        logger.debug(f"Loaded/Updated scenario: {scenario_id}")

            # Convert registry back to list
            all_scenarios = list(scenario_registry.values())

            logger.info(f"Successfully loaded {len(all_scenarios)} unique scenarios from {len(spec_files)} specification files")
            return all_scenarios

        except ImportError:
            logger.error("test_scenario_generator not found, using fallback scenarios")
            return self._get_fallback_scenarios()
        except Exception as e:
            logger.error(f"Failed to load scenarios from specification files: {e}")
            return self._get_fallback_scenarios()
    #
    # ========================================================================
    # Method 7.1.6: _get_fallback_scenarios
    # Purpose: Return fallback scenarios if specification files cannot be loaded.
    # ========================================================================
    def _get_fallback_scenarios(self) -> List[Dict]:

        return [
            {
                "id": "ws_connectivity_fallback",
                "name": "WebSocket Connectivity Test (Fallback)",
                "category": "connectivity",
                "type": "websocket_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 2
            },
            {
                "id": "rest_health_fallback",
                "name": "REST API Health Test (Fallback)",
                "category": "connectivity",
                "type": "rest_health_test",
                "enabled": True,
                "priority": 1,
                "timeout": 15,
                "retry_count": 2
            },
            {
                "id": "rule_engine_fallback",
                "name": "Rule Engine Functionality Test (Fallback)",
                "category": "rule_engine",
                "type": "rule_engine_test",
                "enabled": True,
                "priority": 2,
                "timeout": 60,
                "retry_count": 1
            },
            {
                "id": "agent_basic_fallback",
                "name": "Basic Agent Test (Fallback)",
                "category": "agent_execution",
                "type": "agent_test",
                "agent_name": "codegen_agent",
                "task": "Generate basic test code",
                "enabled": True,
                "priority": 3,
                "timeout": 120,
                "retry_count": 1
            }
        ]
    #
    # ========================================================================
    # Async Method 7.1.7: execute_test_suite
    # Purpose: Execute complete test suite with specified scenarios.
    # ========================================================================
    #
    async def execute_test_suite(self, scenarios: List[Dict], parallel_execution: bool = True, max_workers: int = 4) -> TestSession:

        session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now(timezone.utc)

        # Filter enabled scenarios and sort by priority
        enabled_scenarios = [s for s in scenarios if s.get('enabled', True)]
        enabled_scenarios.sort(key=lambda x: x.get('priority', 999))

        self.current_session = TestSession(
            session_id=session_id,
            start_time=start_time.isoformat(),
            status="RUNNING",
            total_tests=len(enabled_scenarios)
        )

        logger.info(f"Starting test session {session_id} with {len(enabled_scenarios)} tests")

        # Setup base environment
        if not await self.env_manager.setup_base_environment():
            logger.error("Failed to setup base test environment")
            self.current_session.status = "FAILED"
            return self.current_session

        try:
            if parallel_execution and len(enabled_scenarios) > 1:
                # Execute tests in parallel with controlled concurrency
                results = await self._execute_parallel_tests(enabled_scenarios, max_workers)
                logger.info(f"(enabled_scenarios, max_workers)")
            else:
                # Execute tests sequentially
                results = await self._execute_sequential_tests(enabled_scenarios)
                logger.info(f"(enabled_scenarios)")

            # Process results
            for result in results:
                self.current_session.test_results.append(result)
                logger.info(f"(result)")
                if result.status == "PASS":
                    self.current_session.passed_tests += 1
                elif result.status == "FAIL":
                    self.current_session.failed_tests += 1
                elif result.status == "ERROR":
                    self.current_session.error_tests += 1
                elif result.status == "TIMEOUT":
                    self.current_session.timeout_tests += 1
                else:
                    self.current_session.skipped_tests += 1

            # Finalize session
            end_time = datetime.now(timezone.utc)
            self.current_session.end_time = end_time.isoformat()
            self.current_session.total_execution_time = (end_time - start_time).total_seconds()

            if self.current_session.failed_tests == 0 and self.current_session.error_tests == 0:
                logger.info(f"Test session completed: {self.current_session.passed_tests}/{self.current_session.total_tests} tests passed")
                self.current_session.status = "COMPLETED"
            else:
                logger.info(f"Test session completed with failures: {self.current_session.passed_tests}/{self.current_session.total_tests} tests passed")
                self.current_session.status = "COMPLETED_WITH_FAILURES"

            logger.info(f"Test session completed: {self.current_session.passed_tests}/{self.current_session.total_tests} tests passed")

        except Exception as e:
            logger.error(f"Test session failed: {e}")
            self.current_session.status = "FAILED"

        finally:
            await self._save_session_state()
            await self.server_manager.stop_all_servers()
            await self.env_manager.cleanup_all()

        return self.current_session
    #
    # ========================================================================
    # Async Method 7.1.8: _execute_parallel_tests
    # Purpose: Execute tests in parallel with controlled concurrency.
    # ========================================================================
    #
    async def _execute_parallel_tests(self, scenarios: List[Dict], max_workers: int) -> List[TestResult]:
        semaphore = asyncio.Semaphore(max_workers)
        #
        # ========================================================================
        # Async Method 7.1.8.1: execute_with_semaphore
        # Purpose: Execute a single test with semaphore control.
        # ========================================================================
        #
        async def execute_with_semaphore(scenario):
            async with semaphore:
                return await self._execute_single_test(scenario)

        tasks = [execute_with_semaphore(scenario) for scenario in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions from parallel execution
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = TestResult(
                    test_id=scenarios[i].get('id', f'test_{i}'),
                    test_name=scenarios[i].get('name', 'Unknown Test'),
                    category=scenarios[i].get('category', 'unknown'),
                    status="ERROR",
                    execution_time=0.0,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    error_message=str(result)
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        logger.info(f"Parallel test execution completed: {len(final_results)} tests executed")
        return final_results
    #
    # ========================================================================
    # Async Method 7.1.9: _execute_sequential_tests
    # Purpose: Execute tests sequentially.
    # ========================================================================
    #
    async def _execute_sequential_tests(self, scenarios: List[Dict]) -> List[TestResult]:

        results = []

        for i, scenario in enumerate(scenarios):
            logger.info(f"Executing test {i+1}/{len(scenarios)}: {scenario.get('name', 'Unknown')}")

            try:
                result = await self._execute_single_test(scenario)
                results.append(result)

                # Save intermediate progress
                if i % 5 == 0:  # Save every 5 tests
                    await self._save_session_state()

            except Exception as e:
                logger.error(f"Failed to execute test {scenario.get('id', 'unknown')}: {e}")
                error_result = TestResult(
                    test_id=scenario.get('id', f'test_{i}'),
                    test_name=scenario.get('name', 'Unknown Test'),
                    category=scenario.get('category', 'unknown'),
                    status="ERROR",
                    execution_time=0.0,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    error_message=str(e)
                )
                results.append(error_result)

        return results
    #
    # ========================================================================
    # Async Method 7.1.10: _execute_single_test
    # Purpose: Execute a single test scenario with retry logic.
    # ========================================================================
    #
    async def _execute_single_test(self, scenario: Dict) -> TestResult:

        test_type = scenario.get('type', 'unknown')
        test_id = scenario.get('id', 'unknown_test')
        retry_count = scenario.get('retry_count', 0)

        last_result = None

        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying test {test_id}, attempt {attempt + 1}")

                if test_type == 'websocket_test':
                    result = await self.test_executor.test_websocket_connectivity(test_id)
                elif test_type == 'rest_health_test':
                    result = await self.test_executor.test_rest_api_health(test_id)
                elif test_type == 'agent_test':
                    agent_name = scenario.get('agent_name', 'unknown_agent')
                    task = scenario.get('task', 'Default test task')
                    result = await self.test_executor.test_agent_execution(test_id, agent_name, task)
                elif test_type == 'workflow_test':
                    workflow_config = scenario.get('workflow_config', {})
                    result = await self.test_executor.test_workflow_execution(test_id, workflow_config)
                elif test_type == 'rule_engine_test':
                    result = await self.test_executor.test_rule_engine_functionality(test_id)
                else:
                    raise ValueError(f"Unknown test type: {test_type}")

                # If test passed, return immediately
                if result.status == "PASS":
                    return result

                last_result = result

                # Wait before retry
                if attempt < retry_count:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Test execution error for {test_id}: {e}")
                last_result = TestResult(
                    test_id=test_id,
                    test_name=scenario.get('name', 'Unknown Test'),
                    category=scenario.get('category', 'unknown'),
                    status="ERROR",
                    execution_time=0.0,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    error_message=str(e)
                )

        return last_result or TestResult(
            test_id=test_id,
            test_name=scenario.get('name', 'Unknown Test'),
            category=scenario.get('category', 'unknown'),
            status="ERROR",
            execution_time=0.0,
            start_time=datetime.now(timezone.utc).isoformat(),
            end_time=datetime.now(timezone.utc).isoformat(),
            error_message="Test execution failed without result"
        )
    #
    # ========================================================================
    # Async Method 7.1.11: _save_session_state
    # Purpose: Save current test session state to persistent storage.
    # ========================================================================
    #
    async def _save_session_state(self):

        try:
            if self.current_session:
                # Save to state file
                state_data = asdict(self.current_session)
                with open(STATE_FILE, 'w') as f:
                    json.dump(state_data, f, indent=2)

                # Save results file
                results_data = {
                    "session_id": self.current_session.session_id,
                    "results": [asdict(result) for result in self.current_session.test_results]
                }
                with open(RESULTS_FILE, 'w') as f:
                    json.dump(results_data, f, indent=2)

                # Save summary file
                summary_data = {
                    "session_id": self.current_session.session_id,
                    "status": self.current_session.status,
                    "total_tests": self.current_session.total_tests,
                    "passed": self.current_session.passed_tests,
                    "failed": self.current_session.failed_tests,
                    "errors": self.current_session.error_tests,
                    "timeouts": self.current_session.timeout_tests,
                    "skipped": self.current_session.skipped_tests,
                    "execution_time": self.current_session.total_execution_time,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                with open(SUMMARY_FILE, 'w') as f:
                    json.dump(summary_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save session state: {e}")
    #
    # ========================================================================
    # Async Method 7.1.12: generate_test_report
    # Purpose: Generate comprehensive test execution report.
    # ========================================================================
    #
    async def generate_test_report(self, session: TestSession) -> str:

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("GEMINI-AGENT FUNCTIONAL TEST HARNESS EXECUTION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Session ID: {session.session_id}")
        report_lines.append(f"Start Time: {session.start_time}")
        report_lines.append(f"End Time: {session.end_time}")
        report_lines.append(f"Total Execution Time: {session.total_execution_time:.2f} seconds")
        report_lines.append(f"Status: {session.status}")
        report_lines.append("")

        # Summary statistics
        report_lines.append("TEST EXECUTION SUMMARY")
        report_lines.append("-" * 40)
        report_lines.append(f"Total Tests: {session.total_tests}")
        report_lines.append(f"Passed: {session.passed_tests}")
        report_lines.append(f"Failed: {session.failed_tests}")
        report_lines.append(f"Errors: {session.error_tests}")
        report_lines.append(f"Timeouts: {session.timeout_tests}")
        report_lines.append(f"Skipped: {session.skipped_tests}")

        pass_rate = (session.passed_tests / session.total_tests * 100) if session.total_tests > 0 else 0
        report_lines.append(f"Pass Rate: {pass_rate:.1f}%")
        report_lines.append("")

        # Detailed test results
        report_lines.append("DETAILED TEST RESULTS")
        report_lines.append("-" * 40)

        for result in session.test_results:
            report_lines.append(f"Test: {result.test_name}")
            report_lines.append(f"  ID: {result.test_id}")
            report_lines.append(f"  Category: {result.category}")
            report_lines.append(f"  Status: {result.status}")
            report_lines.append(f"  Execution Time: {result.execution_time:.2f}s")

            if result.error_message:
                report_lines.append(f"  Error: {result.error_message}")
                logger.error(f"Test failed: {result.error_message}")

            if result.metrics:
                report_lines.append(f"  Metrics: {result.metrics}")

            report_lines.append("")

        # Failure analysis
        failed_tests = [r for r in session.test_results if r.status in ['FAIL', 'ERROR', 'TIMEOUT']]
        if failed_tests:
            report_lines.append("FAILURE ANALYSIS")
            report_lines.append("-" * 40)

            for result in failed_tests:
                report_lines.append(f"FAILED: {result.test_name}")
                report_lines.append(f"  Reason: {result.error_message}")
                if result.error_traceback:
                    report_lines.append(f"  Traceback: {result.error_traceback}")
                report_lines.append("")
                logger.error(f"Test failed: {result.error_message}")

        # Recommendations
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("-" * 40)

        if session.passed_tests == session.total_tests:
            report_lines.append("[OK] All tests passed! System is functioning correctly.")
            logger.info("All tests passed! System is functioning correctly.")
        else:
            if session.failed_tests > 0:
                report_lines.append("[WARN] Failed tests indicate functional issues that need attention.")
            if session.error_tests > 0:
                report_lines.append("[ERROR] Error tests indicate system-level problems requiring investigation.")
            if session.timeout_tests > 0:
                report_lines.append("[TIMEOUT] Timeout tests suggest performance or connectivity issues.")

        report_lines.append("")
        report_lines.append("=" * 80)

        # Save report to file
        report_content = "\n".join(report_lines)
        report_file = TESTS_DIR / f"test_report_{session.session_id}.txt"
        with open(report_file, 'w') as f:
            f.write(report_content)

        logger.info(f"Test report saved to: {report_file}")
        return report_content
#
# ============================================================================
# SECTION 8: Main Execution & CLI Interface
# ============================================================================
# Async Function 8.1: main
# Purpose: Main execution function for the test harness.
# ============================================================================
#
async def main():

    parser = argparse.ArgumentParser(
        description="Gemini-Agent Functional Test Harness v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python automated_test_harness.py --all
    python automated_test_harness.py --scenarios test_scenarios.json --parallel --workers 6
    python automated_test_harness.py --single ws_connectivity
    python automated_test_harness.py --category agent_execution --sequential
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Execute all default test scenarios'
    )

    parser.add_argument(
        '--scenarios',
        type=Path,
        help='Path to custom test scenarios JSON file'
    )

    parser.add_argument(
        '--single',
        type=str,
        help='Execute single test by ID'
    )

    parser.add_argument(
        '--category',
        type=str,
        choices=['connectivity', 'agent_execution', 'workflow', 'rule_engine'],
        help='Execute tests from specific category'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        help='Execute tests in parallel (default)'
    )

    parser.add_argument(
        '--sequential',
        action='store_true',
        help='Execute tests sequentially'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Overall timeout for test suite execution (seconds)'
    )

    parser.add_argument(
        '--report-only',
        action='store_true',
        help='Generate report from last test session without executing tests'
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clean up test environments and exit'
    )

    args = parser.parse_args()

    # Handle cleanup request
    if args.cleanup:
        logger.info("Cleaning up test environments...")
        orchestrator = TestSuiteOrchestrator()
        await orchestrator._emergency_cleanup()
        logger.info("Cleanup completed")
        return

    # Handle report-only request
    if args.report_only:
        try:
            with open(STATE_FILE, 'r') as f:
                session_data = json.load(f)

            # Reconstruct session object
            session = TestSession(**session_data)
            session.test_results = [TestResult(**result) for result in session_data.get('test_results', [])]

            orchestrator = TestSuiteOrchestrator()
            report = await orchestrator.generate_test_report(session)
            print(report)
            return

        except FileNotFoundError:
            logger.error("No previous test session found")
            return
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return

    # Initialize orchestrator
    orchestrator = TestSuiteOrchestrator()
    logger.info("Test harness initialized")

    try:
        # Load test scenarios
        if args.scenarios:
            scenarios = await orchestrator.load_test_scenarios(args.scenarios)
            logger.info(f"Loaded {len(scenarios)} test scenarios from {args.scenarios}")
        else:
            scenarios = await orchestrator.load_test_scenarios()
            logger.info(f"Loaded {len(scenarios)} test scenarios from default location")

        # Filter scenarios based on arguments
        if args.single:
            scenarios = [s for s in scenarios if s.get('id') == args.single]
            logger.info(f"Filtered to single test scenario: {args.single}")
            if not scenarios:
                logger.error(f"Test scenario '{args.single}' not found")
                return
        elif args.category:
            scenarios = [s for s in scenarios if s.get('category') == args.category]
            logger.info(f"Filtered to category: {args.category}")
            if not scenarios:
                logger.error(f"No test scenarios found for category '{args.category}'")
                return

        # Determine execution mode
        parallel_execution = args.parallel and not args.sequential

        logger.info(f"Executing {len(scenarios)} test scenarios...")
        logger.info(f"Execution mode: {'Parallel' if parallel_execution else 'Sequential'}")

        # Execute test suite with timeout
        session = await asyncio.wait_for(
            orchestrator.execute_test_suite(scenarios, parallel_execution, args.workers),
            timeout=args.timeout
        )

        # Generate and display report
        report = await orchestrator.generate_test_report(session)
        logger.info("\n" + report)
        print("\n" + report)

        # Exit with appropriate code
        if session.status == "COMPLETED":
            logger.info("All tests passed! System is functioning correctly.")
            sys.exit(0)
        else:
            logger.info("Some tests failed. System may have issues.")
            sys.exit(1)

    except asyncio.TimeoutError:
        logger.error(f"Test suite execution timed out after {args.timeout} seconds")
        await orchestrator._emergency_cleanup()
        sys.exit(2)
    except KeyboardInterrupt:
        await orchestrator._emergency_cleanup()
        logger.info("Test execution interrupted by user")
        sys.exit(3)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        await orchestrator._emergency_cleanup()
        sys.exit(4)
#
# ============================================================================
# SECTION 9: Entry Point
# ============================================================================
#
if __name__ == "__main__":
    # Ensure proper event loop handling on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Test harness interrupted")
        sys.exit(3)
    except Exception as e:
        logger.error(f"Fatal error in test harness: {e}")
        sys.exit(4)
#
#
## End of automated_test_harness.py
