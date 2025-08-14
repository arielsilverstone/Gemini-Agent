#
# ============================================================================
#  File: security_test_scenario_generator.py
#  Version: 1.0 (Focused Security Test Generation)
#  Purpose: FOCUSED generator for ONLY 3 security areas: API authentication,
#           input validation, and WebSocket security testing scenarios
#  Created: 05AUG25
# ============================================================================
# SECTION 1: Imports & Configuration
# ============================================================================
#
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

# Import security manager for validation
from src.security_manager import SecurityLevel, AuthenticationMethod


#
# ============================================================================
# SECTION 2: Security Test Scenario Templates
# ============================================================================
#
class SecurityTestScenarioGenerator:
    """
    Generates focused test scenarios for the 3 core security areas:
    - API authentication and authorization
    - Input validation and sanitization
    - WebSocket security protocols
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent
        self.scenarios = []

    #
    # ========================================================================
    # Method 2.1: generate_api_authentication_scenarios
    # ========================================================================
    #
    def generate_api_authentication_scenarios(self) -> List[Dict[str, Any]]:
        """Generate API authentication test scenarios."""
        scenarios = []

        # Valid API key authentication test
        scenarios.append(
            {
                "id": "api_auth_001",
                "name": "Valid API Key Authentication",
                "category": "api_authentication",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "authentication",
                "description": "Test successful API authentication with valid key",
                "actions": [
                    "Generate valid API key with basic permissions",
                    "Authenticate API request with valid key",
                    "Verify security context creation",
                ],
                "expected_results": {
                    "authentication_success": True,
                    "security_context_created": True,
                    "user_permissions_verified": True,
                },
                "validation_criteria": [
                    "Security context contains user_id",
                    "Authentication method is API_KEY",
                    "Permissions include basic_access",
                ],
            }
        )

        # Invalid API key authentication test
        scenarios.append(
            {
                "id": "api_auth_002",
                "name": "Invalid API Key Authentication",
                "category": "api_authentication",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "authentication_failure",
                "description": "Test failed authentication with invalid key",
                "actions": [
                    "Attempt authentication with invalid API key",
                    "Verify security error is raised",
                    "Confirm no security context created",
                ],
                "expected_results": {
                    "authentication_success": False,
                    "security_error_raised": True,
                    "security_context_created": False,
                },
                "validation_criteria": [
                    "SecurityError exception raised",
                    "No security context in response",
                    "Error message indicates invalid key",
                ],
            }
        )

        # Rate limiting test
        scenarios.append(
            {
                "id": "api_auth_003",
                "name": "API Rate Limiting Enforcement",
                "category": "api_authentication",
                "type": "security_test",
                "enabled": True,
                "priority": 2,
                "timeout": 60,
                "retry_count": 1,
                "security_focus": "rate_limiting",
                "description": "Test API rate limiting prevents abuse",
                "actions": [
                    "Generate valid API key",
                    "Send 70 rapid API requests (above 60/minute limit)",
                    "Verify rate limiting triggers after 60 requests",
                ],
                "expected_results": {
                    "first_60_requests_succeed": True,
                    "rate_limit_triggered": True,
                    "excess_requests_blocked": True,
                },
                "validation_criteria": [
                    "Rate limit error after 60 requests",
                    "SecurityError with rate_limit message",
                    "Subsequent requests blocked for remainder of minute",
                ],
            }
        )

        return scenarios

    #
    # ========================================================================
    # Method 2.2: generate_input_validation_scenarios
    # ========================================================================
    #
    def generate_input_validation_scenarios(self) -> List[Dict[str, Any]]:
        """Generate input validation test scenarios."""
        scenarios = []

        # Valid input validation test
        scenarios.append(
            {
                "id": "input_val_001",
                "name": "Valid Input Validation",
                "category": "input_validation",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "input_validation",
                "description": "Test valid inputs pass validation",
                "actions": [
                    "Validate normal agent task: 'Generate Python function'",
                    "Validate normal WebSocket message: 'Status update'",
                    "Verify all inputs accepted",
                ],
                "expected_results": {
                    "agent_task_valid": True,
                    "websocket_message_valid": True,
                    "no_security_errors": True,
                },
                "validation_criteria": [
                    "validate_agent_task returns True",
                    "validate_websocket_message returns True",
                    "No injection patterns detected",
                ],
            }
        )

        # SQL injection prevention test
        scenarios.append(
            {
                "id": "input_val_002",
                "name": "SQL Injection Prevention",
                "category": "input_validation",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "injection_prevention",
                "description": "Test SQL injection attempts are blocked",
                "actions": [
                    "Attempt agent task with SQL injection: '; DROP TABLE users; --'",
                    "Attempt WebSocket message with SQL injection",
                    "Verify injection attempts blocked",
                ],
                "expected_results": {
                    "sql_injection_blocked": True,
                    "security_error_raised": True,
                    "malicious_input_rejected": True,
                },
                "validation_criteria": [
                    "validate_agent_task returns False for injection",
                    "Error message indicates injection attempt",
                    "Input marked as dangerous",
                ],
            }
        )

        # XSS prevention test
        scenarios.append(
            {
                "id": "input_val_003",
                "name": "XSS Script Prevention",
                "category": "input_validation",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "xss_prevention",
                "description": "Test XSS script attempts are blocked",
                "actions": [
                    "Attempt task with XSS: '<script>alert(\"xss\")</script>'",
                    "Attempt WebSocket with JavaScript: 'javascript:evil()'",
                    "Verify XSS attempts blocked",
                ],
                "expected_results": {
                    "xss_blocked": True,
                    "script_tags_rejected": True,
                    "javascript_urls_blocked": True,
                },
                "validation_criteria": [
                    "Script tags detected and blocked",
                    "JavaScript URLs flagged as dangerous",
                    "Security validation fails for XSS content",
                ],
            }
        )

        return scenarios

    #
    # ========================================================================
    # Method 2.3: generate_websocket_security_scenarios
    # ========================================================================
    #
    def generate_websocket_security_scenarios(self) -> List[Dict[str, Any]]:
        """Generate WebSocket security test scenarios."""
        scenarios = []

        # Valid WebSocket connection test
        scenarios.append(
            {
                "id": "ws_sec_001",
                "name": "Secure WebSocket Connection",
                "category": "websocket_security",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "websocket_authentication",
                "description": "Test secure WebSocket connection establishment",
                "actions": [
                    "Generate valid API key",
                    "Establish WebSocket connection with key",
                    "Verify security context propagated",
                ],
                "expected_results": {
                    "connection_established": True,
                    "security_context_valid": True,
                    "authentication_verified": True,
                },
                "validation_criteria": [
                    "WebSocket connection ID tracked",
                    "Security context contains user_id",
                    "Connection registered in secure_connections",
                ],
            }
        )

        # Connection limit enforcement test
        scenarios.append(
            {
                "id": "ws_sec_002",
                "name": "WebSocket Connection Limits",
                "category": "websocket_security",
                "type": "security_test",
                "enabled": True,
                "priority": 2,
                "timeout": 60,
                "retry_count": 1,
                "security_focus": "connection_limits",
                "description": "Test WebSocket connection limits per user",
                "actions": [
                    "Generate valid API key",
                    "Establish 5 WebSocket connections (limit)",
                    "Attempt 6th connection and verify rejection",
                ],
                "expected_results": {
                    "first_5_connections_succeed": True,
                    "6th_connection_rejected": True,
                    "limit_error_message": True,
                },
                "validation_criteria": [
                    "First 5 connections established successfully",
                    "6th connection raises SecurityError",
                    "Error message mentions connection limit",
                ],
            }
        )

        # Message validation test
        scenarios.append(
            {
                "id": "ws_sec_003",
                "name": "WebSocket Message Validation",
                "category": "websocket_security",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 30,
                "retry_count": 1,
                "security_focus": "message_validation",
                "description": "Test WebSocket message structure validation",
                "actions": [
                    "Establish WebSocket connection",
                    "Send valid message with type and payload",
                    "Send invalid message missing required fields",
                    "Verify validation results",
                ],
                "expected_results": {
                    "valid_message_accepted": True,
                    "invalid_message_rejected": True,
                    "validation_error_provided": True,
                },
                "validation_criteria": [
                    "Valid message validation returns True",
                    "Invalid message validation returns False",
                    "Error explains missing required fields",
                ],
            }
        )

        return scenarios

    #
    # ========================================================================
    # Method 2.4: generate_integration_scenarios
    # ========================================================================
    #
    def generate_integration_scenarios(self) -> List[Dict[str, Any]]:
        """Generate integration test scenarios combining multiple security areas."""
        scenarios = []

        # Full security workflow test
        scenarios.append(
            {
                "id": "integration_001",
                "name": "Complete Security Workflow",
                "category": "security_integration",
                "type": "security_test",
                "enabled": True,
                "priority": 1,
                "timeout": 120,
                "retry_count": 1,
                "security_focus": "full_workflow",
                "description": "Test complete security workflow from auth to execution",
                "actions": [
                    "Generate API key with agent execution permissions",
                    "Authenticate API request",
                    "Validate agent task input",
                    "Establish WebSocket connection",
                    "Send validated message through WebSocket",
                    "Verify end-to-end security",
                ],
                "expected_results": {
                    "api_authentication_success": True,
                    "input_validation_success": True,
                    "websocket_connection_success": True,
                    "message_validation_success": True,
                    "security_workflow_complete": True,
                },
                "validation_criteria": [
                    "All security checkpoints pass",
                    "Security context maintained throughout",
                    "No security errors in workflow",
                ],
            }
        )

        return scenarios

    #
    # ========================================================================
    # Method 2.5: generate_all_scenarios
    # ========================================================================
    #
    def generate_all_scenarios(self) -> List[Dict[str, Any]]:
        """Generate all focused security test scenarios."""
        all_scenarios = []

        # Generate scenarios for each security area
        all_scenarios.extend(self.generate_api_authentication_scenarios())
        all_scenarios.extend(self.generate_input_validation_scenarios())
        all_scenarios.extend(self.generate_websocket_security_scenarios())
        all_scenarios.extend(self.generate_integration_scenarios())

        logger.info(f"Generated {len(all_scenarios)} focused security test scenarios")
        return all_scenarios

    #
    # ========================================================================
    # Method 2.6: save_scenarios_to_file
    # ========================================================================
    #
    def save_scenarios_to_file(
        self, filename: str = "security_test_scenarios.json"
    ) -> Path:
        """Save generated scenarios to JSON file."""
        scenarios = self.generate_all_scenarios()

        # Create security test specification
        security_spec = {
            "metadata": {
                "generator": "SecurityTestScenarioGenerator",
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "focus_areas": [
                    "API authentication",
                    "Input validation",
                    "WebSocket security",
                ],
                "scenario_count": len(scenarios),
            },
            "scenarios": scenarios,
        }

        # Save to file
        output_file = self.output_dir / filename
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(security_spec, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(scenarios)} security scenarios to {output_file}")
        return output_file


#
# ============================================================================
# SECTION 3: CLI and Integration Support
# ============================================================================
#
def main():
    """Generate security test scenarios for the focused security framework."""
    generator = SecurityTestScenarioGenerator()

    # Generate and save scenarios
    output_file = generator.save_scenarios_to_file()

    print(f"✅ Generated focused security test scenarios")
    print(f"📁 Saved to: {output_file}")
    print(f"🔒 Focus areas: API auth, input validation, WebSocket security")
    print(f"📊 Total scenarios: {len(generator.generate_all_scenarios())}")


if __name__ == "__main__":
    main()
#
#
## End of security_test_scenario_generator.py
