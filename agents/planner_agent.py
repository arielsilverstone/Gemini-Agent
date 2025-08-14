# ============================================================================
#  File: planner_agent.py
#  Version: 1.0 (Restored)
#  Purpose: Planning Agent for Gemini-Agent
#  Created: 30JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import asyncio
import logging
from typing import Any, AsyncIterator, Dict, Optional, Tuple

from agents.agent_base import AgentBase
from src.error_handling import agent_self_correct
from src.telemetry import record_telemetry

# ============================================================================
# SECTION 2: PlannerAgent Class
# ============================================================================
class PlannerAgent(AgentBase):
    """Agent responsible for creating a plan to accomplish a task."""

    def __init__(self, name: str, config: Dict[str, Any], websocket_manager=None, rule_engine=None, config_manager=None):
        super().__init__(name, config, websocket_manager, rule_engine, config_manager)

    @record_telemetry("PlannerAgent", "run")
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[str]:
        """Execute the planning task and yield output chunks."""
        context = context or {}
        self.update_context(context)
        log_message = f"[{self.name}] Starting planning task: {task}"
        logging.info(log_message)
        yield f"STREAM_CHUNK:{self.name}:{log_message}\n"

        try:
            # 1. Construct Prompt
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Constructing prompt...\n"
            template_name = self.config.get("template", "planner_template.txt")
            template_data = {
                "task": task,
                "context_summary": str(context),
                "planning_level": context.get("level", "high-level"),
            }
            prompt = self._construct_prompt(template_name, **template_data)

            # 2. Execute LLM and Buffer Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Generating plan...\n"
            full_response = ""
            async for chunk in self._execute_llm_workflow(prompt=prompt, task=task, context=context):
                full_response += chunk

            # 3. Validate Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validating plan...\n"
            if not full_response.strip() or "[ERROR]" in full_response:
                raise ValueError("LLM response was empty or contained an error.")

            rule_violations = await self._enforce_agent_rules(full_response, task, context)
            if rule_violations:
                violation_details = "; ".join([f"{v['rule_name']}: {v['message']}" for v in rule_violations])
                raise ValueError(f"Agent-specific rules violated: {violation_details}")

            # 4. Save to GDrive and Stream Validated Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validation passed. Saving plan to Google Drive...\n"
            output_filename = context.get("output_filename", "plan.md")
            parent_folder_id = context.get("parent_folder_id")
            if not parent_folder_id:
                raise ValueError("Missing 'parent_folder_id' in context for saving output.")

            file_id = await self._write_gdrive_file(output_filename, full_response, parent_folder_id)
            if not file_id:
                raise IOError("Failed to save the plan to Google Drive.")

            yield full_response
            success_msg = f"[SUCCESS] [{self.name}] Plan saved to GDrive file ID: {file_id}"
            logging.info(success_msg)
            yield f"STREAM_CHUNK:{self.name}:{success_msg}\n"

        except Exception as e:
            error_message = f"[{self.name}] Self-correction triggered due to error: {e}"
            logging.error(error_message, exc_info=True)
            yield f"STREAM_CHUNK:{self.name}:{error_message}\n"
            async for chunk in agent_self_correct(
                agent=self,
                original_task=task,
                current_context=context,
                error_details=str(e),
                error_type="agent_execution_error",
                correction_guidance="The agent failed during planning or validation. Analyze the error and context to create a valid plan."
            ):
                yield chunk




#
#
## END planner_agent.py
