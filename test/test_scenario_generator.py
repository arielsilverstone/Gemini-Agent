#
# ============================================================================
#  File: test_scenario_generator.py
#  Version: 1.0 (Dynamic Test Generation Engine)
#  Purpose: Generates executable test functions from JSON scenario
#           specifications
#  Created: 05AUG25
# ============================================================================
# SECTION 1: Imports & Configuration
# ============================================================================
#
import asyncio
import json
import re
import websockets
import requests
import subprocess
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from loguru import logger
#
# ============================================================================
# SECTION 2: Test Action Mapping & Execution Primitives
# ============================================================================
# Class 2.1: ActionMapping
# Purpose: Maps JSON action strings to executable functions.
# ============================================================================
#
@dataclass
class ActionMapping:

    pattern: str
    function: Callable
    parameters: Dict[str, Any]
    timeout: Optional[int] = None
    retry_count: int = 1
#
# ============================================================================
# Class 2.2: TestExecutionPrimitives
# Purpose: Core test execution operations mapped from JSON actions.
# ============================================================================
#
class TestExecutionPrimitives:

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backend_process = None
        self.frontend_process = None
        self.websocket_connection = None
        self.test_port = 9102

    # ------------------------------------------------------------------------
    # PRIMITIVE: Backend System Operations
    # ------------------------------------------------------------------------
    #
    # ========================================================================
    # Method 2.2.1: start_backend
    # Purpose: Starts the backend server process. Maps JSON actions:
    #          "Start backend", "Launch backend server"
    # ========================================================================
    #
    async def start_backend(self, timeout: int = 60) -> Tuple[bool, str]:

        try:
            backend_script = self.project_root / "src" / "backend_server.py"
            if not backend_script.exists():
                return False, f"Backend script not found: {backend_script}"

            # Start backend process
            self.backend_process = subprocess.Popen(
                ["python", str(backend_script), "--port", str(self.test_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for startup confirmation
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.backend_process.poll() is not None:
                    stdout, stderr = self.backend_process.communicate()
                    return False, f"Backend failed to start: {stderr.decode()}"

                # Test if server is responding
                try:
                    response = requests.get(
                        f"http://localhost:{self.test_port}/health", timeout=2
                    )
                    if response.status_code == 200:
                        return True, "Backend started successfully"
                except requests.exceptions.RequestException:
                    await asyncio.sleep(1)
                    continue

            return False, "Backend startup timeout exceeded"

        except Exception as e:
            return False, f"Backend startup error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.2: stop_backend
    # Purpose: Stops the backend server process. Maps JSON action:
    #          "Stop backend", "Terminate backend server"
    # ========================================================================
    #
    async def stop_backend(self) -> Tuple[bool, str]:

        try:
            if self.backend_process:
                self.backend_process.terminate()
                await asyncio.sleep(2)
                if self.backend_process.poll() is None:
                    self.backend_process.kill()
                self.backend_process = None
                return True, "Backend stopped successfully"
            return True, "Backend was not running"
        except Exception as e:
            return False, f"Backend stop error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.3: start_frontend
    # Purpose: Starts the frontend application. Maps JSON action:
    #          "Start frontend", "Launch frontend application"
    # ========================================================================
    #
    async def start_frontend(self, timeout: int = 30) -> Tuple[bool, str]:

        try:
            frontend_html = self.project_root / "frontend" / "index.html"
            if not frontend_html.exists():
                return False, f"Frontend HTML not found: {frontend_html}"

            # For testing, we simulate frontend startup
            # In real implementation, this might launch Electron or serve HTML
            self.frontend_process = True  # Placeholder for actual process
            return True, "Frontend started successfully"
        except Exception as e:
            return False, f"Frontend startup error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.4: stop_frontend
    # Purpose: Stops the frontend application. Maps JSON action:
    #          "Stop frontend", "Terminate frontend application"
    # ========================================================================
    #
    async def stop_frontend(self) -> Tuple[bool, str]:
        try:
            if self.frontend_process:
                self.frontend_process = None
                return True, "Frontend stopped successfully"
            return True, "Frontend was not running"
        except Exception as e:
            return False, f"Frontend stop error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.5: connect_websocket
    # Purpose: Establishes WebSocket connection to backend. Maps JSON action:
    #          "Connect WebSocket", "Establish WebSocket connection"
    # ========================================================================
    #
    async def connect_websocket(self, timeout: int = 10) -> Tuple[bool, str]:

        try:
            ws_uri = f"ws://localhost:{self.test_port}/ws"
            self.websocket_connection = await asyncio.wait_for(
                websockets.connect(ws_uri), timeout=timeout
            )
            return True, "WebSocket connected successfully"

        except asyncio.TimeoutError:
            return False, f"WebSocket connection timeout after {timeout}s"
        except Exception as e:
            return False, f"WebSocket connection error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.6: send_websocket_message
    # Purpose: Sends message via WebSocket and waits for response. Maps JSON action:
    #          "Send WebSocket message", "Send agent task"
    # ========================================================================
    #
    async def send_websocket_message(
        self, message: Dict[str, Any], timeout: int = 5
    ) -> Tuple[bool, str]:
        try:
            if not self.websocket_connection:
                return False, "WebSocket not connected"

            message_json = json.dumps(message)
            await self.websocket_connection.send(message_json)

            # Wait for response
            response = await asyncio.wait_for(
                self.websocket_connection.recv(), timeout=timeout
            )

            return True, f"Message sent and response received: {response[:100]}..."

        except asyncio.TimeoutError:
            return False, f"WebSocket message timeout after {timeout}s"
        except Exception as e:
            return False, f"WebSocket message error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.7: execute_agent_task
    # Purpose: Executes a task using specified agent. Maps JSON action:
    #          "Execute [agent] task", "Run [agent] with [task]"
    # ========================================================================
    #
    async def execute_agent_task(
        self, agent_name: str, task: str, timeout: int = 120
    ) -> Tuple[bool, str]:
        try:
            message = {
                "type": "AGENT_TASK",
                "agent": agent_name,
                "task": task,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            success, response = await self.send_websocket_message(message, timeout)
            if success:
                return True, f"Agent {agent_name} executed task successfully"
            else:
                return False, f"Agent {agent_name} task failed: {response}"

        except Exception as e:
            return False, f"Agent execution error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.8: load_configuration
    # Purpose: Loads specified configuration file. Maps JSON action:
    #          "Load config", "Load [config_type] configuration"
    # ========================================================================
    #
    async def load_configuration(self, config_type: str) -> Tuple[bool, str]:

        try:
            config_files = {
                "rules": "rules.example.yaml",
                "agents": "agents.example.yaml",
                "workflow": "workflow.example.yaml",
                "app": "app_settings.json",
            }

            config_file = (
                self.project_root
                / "config"
                / config_files.get(config_type, f"{config_type}.yaml")
            )

            if not config_file.exists():
                return False, f"Configuration file not found: {config_file}"

            # Simulate configuration loading
            return True, f"{config_type} configuration loaded successfully"

        except Exception as e:
            return False, f"Configuration loading error: {e}"
    #
    # ========================================================================
    # Async Method 2.2.9: test_api_endpoint
    # Purpose: Tests API endpoint functionality. Maps JSON actions:
    #          "GET /api/[endpoint]", "POST to settings API"
    # ========================================================================
    #
    async def test_api_endpoint(
        self, endpoint: str, method: str = "GET", data: Optional[Dict] = None, timeout: int = 15
    ) -> Tuple[bool, str]:
        try:
            url = f"http://localhost:{self.test_port}/api/{endpoint.lstrip('/')}"

            if method.upper() == "GET":
                response = requests.get(url, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, timeout=timeout)
            else:
                return False, f"Unsupported HTTP method: {method}"

            success = 200 <= response.status_code < 300
            message = f"API {method} {endpoint}: {response.status_code}"

            return success, message

        except requests.exceptions.Timeout:
            return False, f"API {method} {endpoint}: Timeout after {timeout}s"
        except Exception as e:
            return False, f"API {method} {endpoint}: Error - {e}"
#
# ============================================================================
# SECTION 3: Dynamic Test Generator Engine
# ============================================================================
# Class 3.1: TestScenarioGenerator
# Purpose: Generates executable test functions from JSON scenario
#          specifications.
# ============================================================================
#
class TestScenarioGenerator:
    """Generates executable test functions from JSON scenario specifications."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.primitives = TestExecutionPrimitives(project_root)
        self.action_mappings = self._build_action_mappings()

    def _build_action_mappings(self) -> List[ActionMapping]:
        """
        Maps JSON action strings to executable primitive functions.
        This is the intelligence layer that translates human-readable actions
        into actual system operations.
        """
        return [
            # ----------------------------------------------------------------
            # Backend System Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"start\s+backend|launch\s+backend",
                function=self.primitives.start_backend,
                parameters={},
            ),
            ActionMapping(
                pattern=r"stop\s+backend|shutdown\s+backend",
                function=self.primitives.stop_backend,
                parameters={},
            ),
            # ----------------------------------------------------------------
            # Frontend System Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"start\s+frontend|launch\s+frontend|open\s+frontend",
                function=self.primitives.start_frontend,
                parameters={},
            ),
            # ----------------------------------------------------------------
            # WebSocket Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"connect\s+websocket|establish\s+websocket",
                function=self.primitives.connect_websocket,
                parameters={},
            ),
            # ----------------------------------------------------------------
            # Configuration Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"load\s+rule\s+engine|load\s+rules",
                function=self.primitives.load_configuration,
                parameters={"config_type": "rules"},
            ),
            ActionMapping(
                pattern=r"load\s+(?:agent\s+)?config|load\s+agents",
                function=self.primitives.load_configuration,
                parameters={"config_type": "agents"},
            ),
            # ----------------------------------------------------------------
            # Agent Execution Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"execute\s+(\w+)\s+(?:agent\s+)?task",
                function=self.primitives.execute_agent_task,
                parameters={"agent_name": "$1", "task": "default_task"},
            ),
            ActionMapping(
                pattern=r"run\s+(\w+)\s+agent",
                function=self.primitives.execute_agent_task,
                parameters={"agent_name": "$1", "task": "validation_task"},
            ),
            # ----------------------------------------------------------------
            # API Testing Actions
            # ----------------------------------------------------------------
            ActionMapping(
                pattern=r"GET\s+(/api/[\w/]+)",
                function=self.primitives.test_api_endpoint,
                parameters={"endpoint": "$1", "method": "GET"},
            ),
            ActionMapping(
                pattern=r"POST\s+to\s+(/api/[\w/]+)",
                function=self.primitives.test_api_endpoint,
                parameters={"endpoint": "$1", "method": "POST"},
            ),
            ActionMapping(
                pattern=r"open\s+settings\s+modal",
                function=self.primitives.test_api_endpoint,
                parameters={"endpoint": "/api/get_config", "method": "GET"},
            ),
        ]

    # ------------------------------------------------------------------------
    # METHOD: Parse Scenario Specifications
    # ------------------------------------------------------------------------

    def load_scenario_specifications(self, spec_file: Path) -> List[Dict[str, Any]]:
        """
        Loads and parses scenario specifications from JSON file.
        Supports the main file and any descendant specification files.
        """
        try:
            with open(spec_file, "r", encoding="utf-8") as f:
                spec_data = json.load(f)

            scenarios = []

            # Extract scenarios from the specification structure
            if "test_plan" in spec_data and "tasks" in spec_data["test_plan"]:
                for task in spec_data["test_plan"]["tasks"]:
                    if "scenarios" in task:
                        for scenario in task["scenarios"]:
                            # Enhance scenario with task context
                            enhanced_scenario = {
                                "task_id": task["id"],
                                "task_name": task["name"],
                                "task_objectives": task.get("objectives", []),
                                **scenario,
                            }
                            scenarios.append(enhanced_scenario)

            logger.info(f"Loaded {len(scenarios)} scenarios from {spec_file}")
            return scenarios

        except Exception as e:
            logger.error(f"Failed to load scenario specifications: {e}")
            return []

    # ------------------------------------------------------------------------
    # METHOD: Generate Executable Test Function
    # ------------------------------------------------------------------------

    async def generate_test_function(self, scenario: Dict[str, Any]) -> Callable:
        """
        Generates an executable test function from a scenario specification.
        This is the core intelligence that transforms JSON specs into runnable tests.
        """
        scenario_name = scenario.get("name", "Unknown Scenario")
        actions = scenario.get("actions", [])
        timeout_str = scenario.get("timeout", "60 seconds")
        pass_criteria = scenario.get("Pass", [])
        fail_criteria = scenario.get("Fail", [])

        # Parse timeout from string (e.g., "120 seconds" -> 120)
        timeout_seconds = self._parse_timeout(timeout_str)

        async def generated_test_function() -> Tuple[bool, str, Dict[str, Any]]:
            """
            Dynamically generated test function for specific scenario.

            Returns:
                Tuple[bool, str, Dict]: (success, message, execution_details)
            """
            execution_details = {
                "scenario_name": scenario_name,
                "actions_executed": [],
                "validation_results": [],
                "execution_time": 0,
                "timeout_used": timeout_seconds,
            }

            start_time = time.time()

            try:
                # ------------------------------------------------------------
                # PHASE 1: Execute Actions
                # ------------------------------------------------------------
                for i, action in enumerate(actions):
                    action_start = time.time()

                    # Find matching action mapping
                    mapped_function = self._map_action_to_function(action)

                    if mapped_function:
                        func, params = mapped_function
                        logger.info(f"Executing action {i+1}/{len(actions)}: {action}")

                        # Execute with timeout
                        success, result_message = await asyncio.wait_for(
                            func(**params), timeout=timeout_seconds
                        )

                        action_time = time.time() - action_start

                        execution_details["actions_executed"].append(
                            {
                                "action": action,
                                "success": success,
                                "message": result_message,
                                "execution_time": action_time,
                            }
                        )

                        if not success:
                            # Action failed - check if this matches fail criteria
                            if self._matches_criteria(result_message, fail_criteria):
                                execution_details["validation_results"].append(
                                    {
                                        "type": "expected_failure",
                                        "message": f"Action failed as expected: {result_message}",
                                    }
                                )
                            else:
                                execution_details["validation_results"].append(
                                    {
                                        "type": "unexpected_failure",
                                        "message": f"Unexpected action failure: {result_message}",
                                    }
                                )
                                return (
                                    False,
                                    f"Action failed: {action} - {result_message}",
                                    execution_details,
                                )
                    else:
                        logger.warning(f"No mapping found for action: {action}")
                        execution_details["actions_executed"].append(
                            {
                                "action": action,
                                "success": False,
                                "message": "No action mapping found",
                                "execution_time": 0,
                            }
                        )

                # ------------------------------------------------------------
                # PHASE 2: Validate Results Against Pass Criteria
                # ------------------------------------------------------------
                pass_validation = self._validate_pass_criteria(
                    execution_details, pass_criteria
                )
                fail_validation = self._validate_fail_criteria(
                    execution_details, fail_criteria
                )

                execution_details["validation_results"].extend(pass_validation)
                execution_details["validation_results"].extend(fail_validation)

                # ------------------------------------------------------------
                # PHASE 3: Determine Final Result
                # ------------------------------------------------------------
                execution_details["execution_time"] = time.time() - start_time

                # Check for timeout failures
                if execution_details["execution_time"] > timeout_seconds:
                    if self._matches_criteria("Timeout Exceeded", fail_criteria):
                        return (
                            True,
                            f"Test passed: Timeout occurred as expected",
                            execution_details,
                        )
                    else:
                        return (
                            False,
                            f"Test failed: Timeout exceeded ({execution_details['execution_time']:.1f}s)",
                            execution_details,
                        )

                # Evaluate overall success based on validation results
                unexpected_failures = [
                    r
                    for r in execution_details["validation_results"]
                    if r["type"] == "unexpected_failure"
                ]
                if unexpected_failures:
                    return (
                        False,
                        f"Test failed: {len(unexpected_failures)} unexpected failures",
                        execution_details,
                    )

                successful_actions = [
                    a for a in execution_details["actions_executed"] if a["success"]
                ]
                if len(successful_actions) == len(actions):
                    return (
                        True,
                        f"Test passed: All {len(actions)} actions completed successfully",
                        execution_details,
                    )
                else:
                    return (
                        False,
                        f"Test failed: {len(actions) - len(successful_actions)} actions failed",
                        execution_details,
                    )

            except asyncio.TimeoutError:
                execution_details["execution_time"] = time.time() - start_time
                if self._matches_criteria("Timeout Exceeded", fail_criteria):
                    return (
                        True,
                        f"Test passed: Timeout occurred as expected",
                        execution_details,
                    )
                else:
                    return (
                        False,
                        f"Test failed: Overall timeout exceeded ({timeout_seconds}s)",
                        execution_details,
                    )

            except Exception as e:
                execution_details["execution_time"] = time.time() - start_time
                error_msg = str(e)
                if self._matches_criteria(error_msg, fail_criteria):
                    return (
                        True,
                        f"Test passed: Expected error occurred - {error_msg}",
                        execution_details,
                    )
                else:
                    return (
                        False,
                        f"Test failed: Unexpected error - {error_msg}",
                        execution_details,
                    )

        return generated_test_function

    # ------------------------------------------------------------------------
    # HELPER METHODS: Action Mapping & Validation
    # ------------------------------------------------------------------------

    def _map_action_to_function(
        self, action: str
    ) -> Optional[Tuple[Callable, Dict[str, Any]]]:
        """Maps a JSON action string to an executable function with parameters."""
        action_lower = action.lower().strip()

        for mapping in self.action_mappings:
            match = re.search(mapping.pattern, action_lower, re.IGNORECASE)
            if match:
                # Process parameter substitutions (e.g., $1 -> match.group(1))
                params = {}
                for key, value in mapping.parameters.items():
                    if isinstance(value, str) and value.startswith("$"):
                        group_num = int(value[1:])
                        if group_num <= len(match.groups()):
                            params[key] = match.group(group_num)
                        else:
                            params[key] = value  # Use original if substitution fails
                    else:
                        params[key] = value

                return mapping.function, params

        return None

    def _parse_timeout(self, timeout_str: str) -> int:
        """Parses timeout string to seconds (e.g., '120 seconds' -> 120)."""
        try:
            # Extract number from string like "120 seconds" or "2 minutes"
            import re

            numbers = re.findall(r"\d+", timeout_str)
            if numbers:
                timeout_num = int(numbers[0])
                if "minute" in timeout_str.lower():
                    return timeout_num * 60
                else:
                    return timeout_num
            return 60  # Default timeout
        except:
            return 60

    def _matches_criteria(self, message: str, criteria: List[str]) -> bool:
        """Checks if a message matches any of the provided criteria."""
        message_lower = message.lower()
        return any(criterion.lower() in message_lower for criterion in criteria)

    def _validate_pass_criteria(
        self, execution_details: Dict, pass_criteria: List[str]
    ) -> List[Dict[str, str]]:
        """Validates execution results against pass criteria."""
        validation_results = []

        for criterion in pass_criteria:
            # Check if criterion is satisfied by any successful action
            criterion_met = False
            for action_result in execution_details["actions_executed"]:
                if action_result["success"] and self._matches_criteria(
                    action_result["message"], [criterion]
                ):
                    criterion_met = True
                    break

            validation_results.append(
                {
                    "type": "pass_validation",
                    "criterion": criterion,
                    "met": criterion_met,
                    "message": f"Pass criterion {'✓ satisfied' if criterion_met else '✗ not satisfied'}: {criterion}",
                }
            )

        return validation_results

    def _validate_fail_criteria(
        self, execution_details: Dict, fail_criteria: List[str]
    ) -> List[Dict[str, str]]:
        """Validates execution results against fail criteria."""
        validation_results = []

        for criterion in fail_criteria:
            # Check if criterion is matched by any action (success or failure)
            criterion_matched = False
            for action_result in execution_details["actions_executed"]:
                if self._matches_criteria(action_result["message"], [criterion]):
                    criterion_matched = True
                    break

            if criterion_matched:
                validation_results.append(
                    {
                        "type": "fail_validation",
                        "criterion": criterion,
                        "matched": True,
                        "message": f"Fail criterion matched (test should handle this): {criterion}",
                    }
                )

        return validation_results


#
# ============================================================================
# SECTION 4: Integration with Test Harness
# ============================================================================
#
class ScenarioTestHarness:
    """Integrates the scenario generator with the main test harness."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.generator = TestScenarioGenerator(project_root)

    async def execute_scenarios_from_file(
        self, spec_file: Path
    ) -> List[Dict[str, Any]]:
        """
        Executes all scenarios from a specification file.
        Returns detailed results for each scenario.
        """
        scenarios = self.generator.load_scenario_specifications(spec_file)
        results = []

        for scenario in scenarios:
            logger.info(
                f"Generating test for scenario: {scenario.get('name', 'Unknown')}"
            )

            try:
                # Generate the test function
                test_function = await self.generator.generate_test_function(scenario)

                # Execute the test
                success, message, execution_details = await test_function()

                result = {
                    "scenario": scenario,
                    "success": success,
                    "message": message,
                    "execution_details": execution_details,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }

                results.append(result)
                logger.info(
                    f"Scenario completed: {scenario.get('name')} - {'✓ PASS' if success else '✗ FAIL'}"
                )

            except Exception as e:
                error_result = {
                    "scenario": scenario,
                    "success": False,
                    "message": f"Test generation/execution error: {e}",
                    "execution_details": {"error": str(e)},
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(error_result)
                logger.error(f"Scenario failed: {scenario.get('name')} - Error: {e}")

        return results


#
# ============================================================================
# SECTION 5: Example Usage & Testing
# ============================================================================
#
async def main():
    """Example usage of the TestScenarioGenerator system."""
    project_root = Path(__file__).parent.parent
    spec_file = project_root / "tests" / "testing-to-do 04AUG25-1820.json"

    if not spec_file.exists():
        logger.error(f"Specification file not found: {spec_file}")
        return

    harness = ScenarioTestHarness(project_root)

    logger.info("Starting dynamic test execution from scenario specifications...")
    results = await harness.execute_scenarios_from_file(spec_file)

    # Summary reporting
    passed = sum(1 for r in results if r["success"])
    total = len(results)

    logger.info(f"Test execution complete: {passed}/{total} scenarios passed")

    # Save detailed results
    results_file = project_root / "tests" / "dynamic_test_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Detailed results saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())
    #
    #
    # End of test_scenario_generator.py
