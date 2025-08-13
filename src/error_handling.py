# ============================================================================
#  File:    error_handling.py
#  Purpose: Agent error codes, standardized messages, and self-correction
# ============================================================================
# SECTION 1: Imports and Globals
# ============================================================================
#
from loguru import logger
from typing import Any, Dict, Optional, AsyncIterator, TYPE_CHECKING
import websockets

if TYPE_CHECKING:
    from agents.agent_base import AgentBase
    from agents.fix_agent import FixAgent

from src.config_manager import ConfigManager
#
# ============================================================================
# SECTION 2: Error Codes and Messages
# ============================================================================
ERROR_CODES = {
    'E001': 'Invalid input',
    'E002': 'Config validation failed',
    'E003': 'LLM call failed or timed out',
    'E004': 'File operation error',
    'E005': 'Agent self-correction attempt failed',
    'E999': 'Unknown error'
}
#
# ============================================================================
# SECTION 3: Error Handling Utilities
# ============================================================================
# Async Function 3.1: connect_to_windsurf
# Purpose: Connects to the Windsurf server.
# ============================================================================
#
async def connect_to_windsurf(port):

    uri = f"ws://127.0.0.1:{port}/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connection established.")
            return websocket
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
#
# ============================================================================
# Function 3.2: get_error_message
# Purpose: Formats a standardized error message from an error code.
# ============================================================================
#
def get_error_message(code, detail=None):
    """Formats a standardized error message from an error code."""
    message = ERROR_CODES.get(code, ERROR_CODES['E999'])
    if detail:
        return f"[{code}] {message}: {str(detail)}"
    return f"[{code}] {message}"
#
# ============================================================================
# SECTION 4: Agent Self-Correction Logic
# ============================================================================
# Async Function 4.1: agent_self_correct
# Purpose: Handles agent errors by initiating a self-correction workflow.
# ============================================================================
#
async def agent_self_correct(
    agent: 'AgentBase',
    original_task: str,
    current_context: Dict[str, Any],
    error_details: str,
    error_type: str,
    correction_guidance: str
) -> AsyncIterator[str]:

    try:
        log_message = f"Initiating self-correction for {agent.name} due to {error_type}. Error: {error_details}"
        logger.info(log_message)
        yield f"STREAM_CHUNK:{agent.name}:[INFO] {log_message}\n"

        # Construct a detailed task for the FixAgent
        fix_task = (
            f"The '{agent.name}' agent failed on the task: '{original_task}'.\n"
            f"Error Type: {error_type}\n"
            f"Error Details: {error_details}\n"
            f"Original Context: {current_context}\n"
        )
        if correction_guidance:
            fix_task += f"Correction Guidance: {correction_guidance}\n"
        fix_task += "Please analyze the error and provide a corrected response or solution."

        # Import FixAgent locally to avoid circular import
        from agents.fix_agent import FixAgent

        # Instantiate and run the FixAgent, passing necessary components
        fix_agent = FixAgent(
            name=agent.name,
            config=agent.config,
            websocket_manager=agent.websocket_manager,
            rule_engine=agent.rule_engine,
            config_manager=agent.config_manager
        )

        # Stream the fix agent's response back
        async for chunk in fix_agent.run(task=fix_task, context=current_context):
            yield chunk

        yield f"STREAM_CHUNK:{agent.name}:[INFO] Self-correction attempt for {agent.name} completed.\n"

    except Exception as e:
        error_message = f"A critical error occurred during the self-correction process: {e}"
        logger.error(error_message, exc_info=True)
        yield f"STREAM_CHUNK:{agent.name}:[ERROR] {error_message}\n"
#
# ============================================================================
# Function 4.2: orchestrator_recover
# Purpose: Attempts orchestrator recovery after a critical failure.
# ============================================================================
#
def orchestrator_recover(orchestrator, last_task=None):
    try:
        orchestrator.reload_config()
        if last_task:
            return orchestrator.handle_ipc(**last_task)
        return True
    except Exception as e:
        return get_error_message('E999', f"Orchestrator recovery failed: {str(e)}")
#
#
## End Script
