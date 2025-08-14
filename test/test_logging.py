# ============================================================================
# File: test_logging.py
# Purpose: Centralized logging and statistics for test runs.
# Created: 13AUG25
# ============================================================================

# Section 1: Imports and Initializations
# ============================================================================
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, TypedDict

# Define the directory for log files and results
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Generate a unique ID for the current test run
TEST_RUN_ID = f"test_session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

# Define the default results file path
RESULTS_FILE = LOG_DIR / f"test_results_{TEST_RUN_ID}.json"

# ============================================================================
# Section 2: Data Structures for Test Events
# ============================================================================

class TestEvent(TypedDict):
    """Represents a single test event (e.g., setup, call, teardown)."""
    node_id: str
    when: str
    outcome: str
    duration: float
    timestamp: str
    error_message: str
    details: Dict[str, Any]

# ============================================================================
# Section 3: Test Statistics Manager Class
# ============================================================================

class TestLogger:
    """Manages the collection and reporting of test statistics."""

    def __init__(self, run_id: str):
        self.stats: Dict[str, Any] = {
            "run_id": run_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "total_duration": 0.0,
            "results": {},
            "summary": {"passed": 0, "failed": 0, "skipped": 0, "error": 0, "total": 0},
            "events": [],
        }

    def start_test(self, test_name: str):
        """Records the start of a test."""
        if test_name not in self.stats["results"]:
            self.stats["results"][test_name] = {
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": None,
                "duration": 0.0,
                "outcome": "pending",
                "message": "",
                "history": [],
            }

    def end_test(self, test_name: str, outcome: str, message: str, details: Dict[str, Any]):
        """Records the end of a test and updates the summary."""
        end_time = datetime.now(timezone.utc)
        if test_name in self.stats["results"]:
            test_data = self.stats["results"][test_name]
            start_time = datetime.fromisoformat(test_data["start_time"])
            duration = (end_time - start_time).total_seconds()

            test_data["end_time"] = end_time.isoformat()
            test_data["duration"] = duration
            test_data["outcome"] = outcome
            test_data["message"] = message
            
            event = TestEvent(
                node_id=test_name,
                when=details.get('when', 'call'),
                outcome=outcome,
                duration=duration,
                timestamp=end_time.isoformat(),
                error_message=message if outcome in ['failed', 'error'] else "",
                details=details
            )
            self.stats["events"].append(event)
            test_data["history"].append(event)

            # Update summary
            if outcome in ["passed", "failed", "skipped", "error"]:
                self.stats["summary"][outcome] += 1
            self.stats["summary"]["total"] += 1

    def save_results(self, results_file: Path):
        """Saves the collected test results to a JSON file."""
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        start_time = datetime.fromisoformat(self.stats["start_time"])
        self.stats["total_duration"] = (datetime.fromisoformat(self.stats["end_time"]) - start_time).total_seconds()
        
        with open(results_file, 'w') as f:
            json.dump(self.stats, f, indent=4)

    def get_stats(self) -> Dict[str, Any]:
        """Returns the current statistics, calculating summary fields."""
        summary = self.stats["summary"]
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        summary["success_rate"] = (passed / total * 100) if total > 0 else 0
        return self.stats

# ============================================================================
# Section 4: Global Instance
# ============================================================================

# Global instance of the TestLogger for the current test run
test_stats = TestLogger(TEST_RUN_ID)
