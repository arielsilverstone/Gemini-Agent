# ============================================================================
#  File: conftest.py
#  Version: 1.0
#  Purpose: E2E test fixtures for backend server startup and environment config
#  Created: 13AUG25
# ============================================================================
# SECTION 1: Global Variables & Imports
# ============================================================================
import os
import sys
import time
import json
import pytest
import requests
import signal
import socket
import subprocess

from pathlib import Path
from typing import Iterator, Generator
from loguru import logger

# User-configurable variables (placed at the top as required)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
BACKEND_SCRIPT: Path = PROJECT_ROOT / "src" / "backend_server.py"
HEALTH_PATH: str = "/health"
PORT_START: int = 9102
PORT_END: int = 9121
STARTUP_TIMEOUT_SECS: int = 45
HEALTH_TIMEOUT_SECS: int = 2

# Socket-based coordination to avoid path inconsistencies across drives/mounts
COORDINATION_PORT: int = 9190

# Use a single OS-wide coordination directory to avoid drive-letter aliasing (e.g., D: vs G:)
COORD_DIR: Path = Path(os.environ.get("GEMINI_E2E_COORD_DIR", "D:/Temp")).resolve()
COORD_DIR.mkdir(parents=True, exist_ok=True)

# Coordination files live under COORD_DIR so all workers share the same path
INFO_FILE: Path = COORD_DIR / "gemini_backend.info.json"
REFCOUNT_FILE: Path = COORD_DIR / "gemini_backend.refcount"
REFLOCK_FILE: Path = COORD_DIR / "gemini_backend.ref.lock"
LOG_STDOUT: Path = COORD_DIR / "gemini_backend.stdout.log"
LOG_STDERR: Path = COORD_DIR / "gemini_backend.stderr.log"
#
# ============================================================================
# SECTION 2: Helper Functions
# ============================================================================
# Method 2.1: _is_port_open
# Purpose: Check whether a TCP port is open on localhost.
# Loop comment: attempt a connection to the specified port and return status without raising.
# ============================================================================
#
def _is_port_open(port: int) -> bool:

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            logger.info(f"Port {port} is open")
            return True
        except Exception:
            logger.info(f"ISSUE: Port {port} is not open")
            return False
#
# ============================================================================
# Method 2.2: _probe_health
# Purpose: Call the backend /health endpoint; return True on {"status": "ok"}.
# ============================================================================
#
def _probe_health(port: int) -> bool:

    try:
        r = requests.get(f"http://127.0.0.1:{port}{HEALTH_PATH}", timeout=HEALTH_TIMEOUT_SECS)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                logger.info(f"ISSUE: Port {port} is not healthy")
                return False
            logger.info(f"Port {port} is healthy")
            return isinstance(data, dict) and data.get("status") == "ok"
        logger.info(f"ISSUE: Port {port} is not healthy")
        return False
    except Exception:
        logger.info(f"ISSUE: Port {port} is not healthy")
        return False
#
# ============================================================================
# Method 2.3: _choose_free_port
# Purpose: Choose a free TCP port on localhost within the preferred range, fallback to OS-assigned.
# ============================================================================
#
def _choose_free_port() -> int:

    # Loop comment: attempt binding sequentially in the preferred range, fallback to port 0
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                logger.info(f"Port {port} is free")
                return port
            except OSError:
                logger.info(f"ISSUE: Port {port} is not free")
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        logger.info(f"Port {s.getsockname()[1]} is free")
        return s.getsockname()[1]
#
# ============================================================================
# Method 2.4: _find_healthy_port
# Purpose: Scan the preferred range and return the first port whose /health reports ok.
# ============================================================================
#
def _find_healthy_port() -> int:

    # Loop comment: iterate across the allowed port range to locate a healthy server instance
    for p in range(PORT_START, PORT_END + 1):
        if _probe_health(p):
            logger.info(f"Port {p} is healthy")
            return p
    logger.info("ISSUE: No healthy backend port found in expected range")
    raise RuntimeError("No healthy backend port found in expected range")
#
# ============================================================================
# Method 2.5: _atomic_write_info
# Purpose: Atomically write the info file with selected port and process id.
# ============================================================================
#
def _atomic_write_info(port: int, pid: int) -> None:

    tmp = INFO_FILE.with_suffix(".tmp")
    data = json.dumps({"port": port, "pid": pid})
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, INFO_FILE)
    logger.info(f"Wrote info file: {INFO_FILE}")
#
# ==========================================================================
# Method 2.6: _with_refcount_lock / _read_refcount / _write_refcount
# Purpose: Safely mutate a small integer refcount in a file with a lock file.
# ==========================================================================
#
def _acquire_ref_lock(timeout: float = 10.0) -> bool:

    deadline = time.time() + timeout
    REFLOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Acquiring reflock: {REFLOCK_FILE}")
    while time.time() < deadline:
        try:
            fd = os.open(str(REFLOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            logger.info(f"Acquired reflock: {REFLOCK_FILE}")
            return True
        except FileExistsError:
            logger.info(f"Reflock already exists: {REFLOCK_FILE}")
            time.sleep(0.05)
    logger.info(f"Failed to acquire reflock: {REFLOCK_FILE}")
    return False
#
# ==========================================================================
# Method 2.7: _release_ref_lock
# Purpose: Safely release the refcount lock file.
# ==========================================================================
#
def _release_ref_lock() -> None:
    try:
        if REFLOCK_FILE.exists():
            os.remove(REFLOCK_FILE)
            logger.info(f"Released reflock: {REFLOCK_FILE}")
    except Exception:
        pass
#
# ==========================================================================
# Method 2.8: _read_refcount
# Purpose: Safely read the refcount file.
# ==========================================================================
#
def _read_refcount() -> int:
    try:
        if REFCOUNT_FILE.exists():
            txt = REFCOUNT_FILE.read_text(encoding="utf-8").strip()
            return int(txt or "0")
    except Exception:
        return 0
    return 0
#
# ==========================================================================
# Method 2.9: _write_refcount
# Purpose: Safely write the refcount file.
# ==========================================================================
#
def _write_refcount(value: int) -> None:

    tmp = REFCOUNT_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(max(0, value)))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, REFCOUNT_FILE)
    logger.info(f"Wrote refcount file: {REFCOUNT_FILE}")
#
# ==========================================================================
# Method 2.10: _inc_refcount
# Purpose: Safely increment the refcount file.
# ==========================================================================
#
def _inc_refcount() -> int:

    if not _acquire_ref_lock():
        return _read_refcount()
    try:
        val = _read_refcount() + 1
        _write_refcount(val)
        return val
    finally:
        _release_ref_lock()
#
# ==========================================================================
# Method 2.11: _dec_refcount
# Purpose: Safely decrement the refcount file.
# ==========================================================================
#
def _dec_refcount() -> int:

    if not _acquire_ref_lock():
        return max(0, _read_refcount() - 1)
    try:
        val = max(0, _read_refcount() - 1)
        _write_refcount(val)
        return val
    finally:
        _release_ref_lock()
#
# ============================================================================
# SECTION 3: Pytest Fixtures
# ============================================================================
# Method 3.1: backend_server
# Purpose: Session-scoped fixture that starts a backend server and yields its port.
# ============================================================================

@pytest.fixture(scope="session")
def backend_server() -> Generator[int, None, None]:
    """
    Process: launch backend_server.py using the current Python executable (ensures venv usage), then poll for health across the permitted port range until ready.
    """
    assert BACKEND_SCRIPT.exists(), f"Backend script not found: {BACKEND_SCRIPT}"

    # Start the backend process using the same interpreter running pytest (keeps us in the chosen venv)
    env = os.environ.copy()

    # Explicit PYTHONPATH: put only the project root first to avoid src/agents shadowing top-level agents
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    # Coordinate a single backend across xdist workers using a localhost TCP lock
    owner = False
    process = None
    port: int = 0
    lock_sock: socket.socket | None = None

    # Attempt to become the owner by binding the coordination socket exclusively
    try:
        lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.info(f"Binding coordination socket to port {COORDINATION_PORT}")
        # Allow immediate reuse across quick successive pytest invocations
        lock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lock_sock.bind(("127.0.0.1", COORDINATION_PORT))
        lock_sock.listen(1)
        owner = True
        logger.info(f"Acquired coordination lock on port {COORDINATION_PORT}")
        # Try multiple times in case of transient bind/import errors
        healthy = False
        last_stdout = ""
        last_stderr = ""
        for _attempt in range(5):
            port = _choose_free_port()
            # Open dedicated log files so the child keeps valid handles even if parent exits
            LOG_STDOUT.parent.mkdir(parents=True, exist_ok=True)
            out_f = open(LOG_STDOUT, "a", encoding="utf-8")
            err_f = open(LOG_STDERR, "a", encoding="utf-8")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "src.backend_server:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "debug",
                ],
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=out_f,
                stderr=err_f,
                text=True,
            )
            logger.info(f"Backend process started with PID {process.pid}")

            # Loop comment: wait for health on the chosen port
            start = time.time()
            while time.time() - start < STARTUP_TIMEOUT_SECS:
                # If process died early, capture logs and retry
                if process.poll() is not None:
                    try:
                        stdout, stderr = process.communicate(timeout=2)
                    except Exception:
                        stdout, stderr = "", ""
                    last_stdout, last_stderr = stdout, stderr
                    logger.info(f"Backend process died with PID {process.pid}")
                    break
                if _probe_health(port):
                    logger.info(f"Backend process healthy with PID {process.pid}")
                    # Publish port for other workers
                    _atomic_write_info(port, process.pid)
                    healthy = True
                    break
                time.sleep(0.5)

            # Close our parent copies of file handles; child keeps its own
            try:
                out_f.close()
                logger.info(f"Closed stdout file: {LOG_STDOUT}")
            except Exception:
                pass
            try:
                err_f.close()
                logger.info(f"Closed stderr file: {LOG_STDERR}")
            except Exception:
                pass

            if healthy:
                logger.info(f"Backend process healthy with PID {process.pid}")
                break

            # Ensure the failed process is terminated before retrying
            try:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                        logger.info(f"Backend process terminated with PID {process.pid}")
                    except Exception:
                        process.kill()
                        logger.info(f"Backend process killed with PID {process.pid}")
            except Exception:
                pass

        if not healthy:
            msg = (
                "Backend failed to start after 5 attempts.\n"
                f"Last STDOUT:\n{last_stdout}\nLast STDERR:\n{last_stderr}"
            )
            logger.info("Backend failed to start after 5 attempts.")
            raise RuntimeError(msg)


    except OSError:
        owner = False

    # If not owner, wait for info file to appear and probe health
    if not owner:
        start = time.time()
        while time.time() - start < STARTUP_TIMEOUT_SECS:
            try:
                if INFO_FILE.exists():
                    with open(INFO_FILE, "r", encoding="utf-8") as f:
                        info = json.loads(f.read() or "{}")
                    port = int(info.get("port", 0))
                    if port and _probe_health(port):
                        logger.info(f"Backend process healthy on port {port}")
                        break
            except Exception:
                port = 0
            time.sleep(0.5)
            logger.info("Waiting for backend to become healthy...")
        else:
            raise RuntimeError("Backend did not become healthy within timeout (waiting on lock)")

    # Increase refcount now that we have a usable backend port
    _inc_refcount()

    # Yield the port to tests
    try:
        yield port
        logger.info(f"Yielding port {port}")
    finally:
        remaining = _dec_refcount()
        # Only the owner tears down the process and releases files when last worker finishes
        if owner and remaining == 0:
            try:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                        logger.info(f"Backend process terminated with PID {process.pid}")
                    except Exception:
                        process.kill()
                        logger.info(f"Backend process killed with PID {process.pid}")
            finally:
                if lock_sock is not None:
                    logger.info(f"Closing coordination socket on port {COORDINATION_PORT}")
                    try:
                        lock_sock.close()
                        logger.info(f"Closed coordination socket on port {COORDINATION_PORT}")
                    except Exception:
                        logger.info(f"Failed to close coordination socket on port {COORDINATION_PORT}")
                        pass
                try:
                    logger.info(f"Removing info file: {INFO_FILE}")
                    if INFO_FILE.exists():
                        os.remove(INFO_FILE)
                except Exception:
                    logger.info(f"Failed to remove info file: {INFO_FILE}")
                    pass
                try:
                    logger.info(f"Removing refcount file: {REFCOUNT_FILE}")
                    if REFCOUNT_FILE.exists():
                        os.remove(REFCOUNT_FILE)
                except Exception:
                    logger.info(f"Failed to remove refcount file: {REFCOUNT_FILE}")
                    pass
#
#
## End of conftest.py
