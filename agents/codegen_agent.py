# ============================================================================
#  File: codegen_agent.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: Code Generation Agent for Gemini-Agent
#  Created: 30JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import asyncio
import logging
from typing import Any, AsyncIterator, Dict, Optional, Tuple

# Fixed imports - removed relative imports
from agents.agent_base import AgentBase
from src.error_handling import agent_self_correct
from src.telemetry import record_telemetry


# ============================================================================
# SECTION 2: CodeGenAgent Class
# ============================================================================
class CodeGenAgent(AgentBase):
    """
    Agent responsible for generating code based on a given task and context.
    """
    def __init__(self, name: str, config: Dict[str, Any], websocket_manager=None, rule_engine=None, config_manager=None):
        super().__init__(name, config, websocket_manager, rule_engine, config_manager)

    @record_telemetry("CodeGenAgent", "run")
    async def run(self, task: str, context: dict) -> AsyncIterator[str]:
        """
        Executes the code generation task by buffering the response, validating it,
        and then streaming it if successful. Triggers self-correction on failure.
        """
        self.update_context(context)
        log_message = f"[{self.name}] Starting code generation task: {task}"
        logging.info(log_message)
        yield f"STREAM_CHUNK:{self.name}:{log_message}\n"

        try:
            # 1. Construct Prompt
            template_name = self.config.get("codegen_template", "base_codegen_prompt.txt")
            template_data = {
                "task": task,
                "current_context": context.get("current_context", ""),
                "requirements": context.get("requirements", ""),
                "language": context.get("language", "Python"),
                "file_to_modify": context.get("file_to_modify", "")
            }
            prompt = self._construct_prompt(template_name, **template_data)

            # 2. Execute LLM and Buffer Response
            full_response = ""
            logging.info(f"[{self.name}] Generating code... (buffering response)")
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Generating code...\n"
            async for chunk in self._execute_llm_workflow(prompt=prompt, task=task, context=context):
                full_response += chunk

            # 3. Validate Response
            logging.info(f"[{self.name}] Validating buffered response...")
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validating response...\n"
            if not full_response.strip() or "[ERROR]" in full_response:
                raise ValueError("LLM response was empty or contained an error.")

            rule_violations = await self._enforce_agent_rules(full_response, task, context)
            if rule_violations:
                violation_details = "; ".join([f"{v['rule_name']}: {v['message']}" for v in rule_violations])
                raise ValueError(f"Agent-specific rules violated: {violation_details}")

            # 4. Stream Validated Response
            logging.info(f"[{self.name}] Validation passed. Streaming response.")
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validation passed. Streaming now...\n"
            yield full_response

            success_msg = f"[SUCCESS] [{self.name}] Task completed successfully."
            logging.info(success_msg)
            yield f"STREAM_CHUNK:{self.name}:{success_msg}\n"

        except Exception as e:
            error_message = f"[{self.name}] Self-correction triggered due to error: {e}"
            logging.error(error_message, exc_info=True)
            yield f"STREAM_CHUNK:{self.name}:{error_message}\n"
            
            # Trigger self-correction and stream its output
            async for chunk in agent_self_correct(
                agent=self,
                original_task=task,
                current_context=context,
                error_details=str(e),
                error_type="agent_execution_error",
                correction_guidance="The agent failed during code generation or validation. Analyze the error and context to provide a fix."
            ):
                yield chunk
