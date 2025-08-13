# ============================================================================
#  File: build_tests_from_scenarios.py
#  Version: 1.0
#  Purpose: Aggregate E2E scenario JSON files into tests/test_scenarios.json
#  Created: 13AUG25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Project paths
CURRENT_FILE = Path(__file__).resolve()
E2E_DIR = CURRENT_FILE.parent
PROJECT_ROOT = E2E_DIR.parent
SCENARIOS_DIR = E2E_DIR / "scenarios"
TESTS_DIR = PROJECT_ROOT / "tests"
OUTPUT_FILE = TESTS_DIR / "test_scenarios.json"

# SECTION 2: Utility Functions
# ============================================================================
# Function 2.1: load_json_file
# Purpose: Safely load a JSON file and return its content
# ============================================================================

def load_json_file(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load JSON from {str(path)}: {str(e)}")
        return None

# Function 2.2: validate_scenario
# Purpose: Validate a scenario dict matches minimal schema
# ============================================================================

def validate_scenario(s: Dict[str, Any]) -> bool:
    required = ["id", "name", "category", "type", "enabled", "priority", "timeout", "retry_count"]
    for k in required:
        if k not in s:
            print(f"[WARN] Scenario missing required key {k}: {s.get('id', '<no-id>')}")
            return False
    if s["type"] == "agent_test":
        if "agent_name" not in s or "task" not in s:
            print(f"[WARN] Agent test requires agent_name and task: {s.get('id', '<no-id>')}")
            return False
    return True

# Function 2.3: normalize_scenario
# Purpose: Ensure types and fields are normalized
# ============================================================================

def normalize_scenario(s: Dict[str, Any]) -> Dict[str, Any]:
    s["enabled"] = bool(s.get("enabled", True))
    s["priority"] = int(s.get("priority", 3))
    s["timeout"] = int(s.get("timeout", 60))
    s["retry_count"] = int(s.get("retry_count", 1))
    return s

# SECTION 3: Core Build Process
# ============================================================================
# Function 3.1: build_scenarios
# Purpose: Read all scenario JSON files, validate, dedupe by id, and write output
# ============================================================================

def build_scenarios() -> List[Dict[str, Any]]:
    if not SCENARIOS_DIR.exists():
        raise RuntimeError(f"Scenarios directory not found: {str(SCENARIOS_DIR)}")
    TESTS_DIR.mkdir(exist_ok=True)

    merged: Dict[str, Dict[str, Any]] = {}
    files = sorted(SCENARIOS_DIR.glob("*.json"))
    if not files:
        raise RuntimeError(f"No scenario JSON files found under {str(SCENARIOS_DIR)}")

    for fp in files:
        data = load_json_file(fp)
        if data is None:
            continue
        if isinstance(data, list):
            candidates = data
        else:
            candidates = [data]
        for s in candidates:
            if not isinstance(s, dict):
                print(f"[WARN] Ignoring non-dict scenario in {fp.name}")
                continue
            if not validate_scenario(s):
                continue
            s = normalize_scenario(s)
            sid = s["id"]
            # Last writer wins
            merged[sid] = s

    # Sort by priority asc, then name
    scenarios = list(merged.values())
    scenarios.sort(key=lambda x: (x.get("priority", 999), x.get("name", "")))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)

    print(f"[INFO] Wrote {len(scenarios)} scenarios to {str(OUTPUT_FILE)} at {datetime.utcnow().isoformat()}Z")
    return scenarios

# SECTION 4: Main
# ============================================================================
# Function 4.1: main
# Purpose: Entrypoint
# ============================================================================

def main() -> int:
    try:
        build_scenarios()
        return 0
    except Exception as e:
        print(f"[ERROR] Scenario build failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
