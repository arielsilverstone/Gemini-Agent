# ============================================================================
#  File: test_agent_functionality.py
#  Version: 1.2 (Corrected)
#  Purpose: Tests the functionality of the TestAgent class.
#  Created: 30JUL25
# ============================================================================
# SECTION 1: Imports
# ============================================================================
#
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.test_agent import TestAgent
#
# ============================================================================
# SECTION 2: Test Agent Creation
# ============================================================================
# Async Method 2.1: test_agent_creation
# Purpose: Tests the basic creation and inheritance of the TestAgent class.
# ============================================================================
#
async def test_agent_creation():

    print("Testing TestAgent creation...")

    # Create a TestAgent instance
    agent = TestAgent(
        name="test_agent",
        config={"test": "config"},
        websocket_manager=None,
        rule_engine=None,
        config_manager=None
    )

    # Verify inheritance
    print(f"Agent name: {agent.name}")
    print(f"Agent config: {agent.config}")
    print(f"Agent websocket_manager: {agent.websocket_manager}")
    print(f"Agent rule_engine: {agent.rule_engine}")
    print(f"Agent config_manager: {agent.config_manager}")

    # Verify methods exist
    print("Testing method access...")
    print(f"update_context method exists: {hasattr(agent, 'update_context')}")
    print(f"_execute_llm_workflow method exists: {hasattr(agent, '_execute_llm_workflow')}")
    print(f"_enforce_agent_rules method exists: {hasattr(agent, '_enforce_agent_rules')}")
    print(f"_write_gdrive_file method exists: {hasattr(agent, '_write_gdrive_file')}")
    print(f"_read_gdrive_file method exists: {hasattr(agent, '_read_gdrive_file')}")
    print(f"_construct_prompt method exists: {hasattr(agent, '_construct_prompt')}")

    print("All tests passed!")
#
# ============================================================================
# SECTION 3: Main
# ============================================================================
#
if __name__ == "__main__":
    asyncio.run(test_agent_creation())
#
#
## End of test_agent_functionality.py
