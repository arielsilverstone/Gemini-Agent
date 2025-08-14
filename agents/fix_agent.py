# ============================================================================
#  File: fix_agent.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: Code Fixing Agent for Gemini-Agent
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
# SECTION 2: FixAgent Class
# ============================================================================
class FixAgent(AgentBase):
    """Agent responsible for fixing errors in code, debugging, and updating existing files."""

    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        websocket_manager=None,
        rule_engine=None,
        config_manager=None,
    ):
        super().__init__(
            name, config, websocket_manager, rule_engine, config_manager
        )

    @record_telemetry("FixAgent", "run")
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[str]:
        """Execute the code fixing task and yield output chunks."""
        context = context or {}
        self.update_context(context)
        log_message = f"[{self.name}] Starting code fixing task: {task}"
        logging.info(log_message)
        yield f"STREAM_CHUNK:{self.name}:{log_message}\n"

        try:
            operation_type = context.get("operation_type", "fix_and_create")

            # 1. Prepare data and construct prompt
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Preparing data for operation: {operation_type}...\n"
            prompt, file_op_details = await self._prepare_and_construct_prompt(task, context, operation_type)

            # 2. Execute LLM and Buffer Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Generating fixed code...\n"
            full_response = ""
            async for chunk in self._execute_llm_workflow(prompt=prompt, task=task, context=context):
                full_response += chunk

            # 3. Validate Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validating response...\n"
            if not full_response.strip() or "[ERROR]" in full_response:
                raise ValueError("LLM response was empty or contained an error.")

            rule_violations = await self._enforce_agent_rules(full_response, task, context)
            if rule_violations:
                violation_details = "; ".join([f"{v['rule_name']}: {v['message']}" for v in rule_violations])
                raise ValueError(f"Agent-specific rules violated: {violation_details}")

            # 4. Perform File Operation and Stream Validated Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validation passed. Saving to Google Drive...\n"
            if operation_type == "fix_and_create":
                file_id = await self._write_gdrive_file(file_op_details['filename'], full_response, file_op_details['parent_id'])
            else:  # update_existing
                success = await self._update_gdrive_file(file_op_details['file_id'], full_response, "fixed code")
                file_id = file_op_details['file_id'] if success else None

            if not file_id:
                raise IOError("Failed to save the fixed code to Google Drive.")

            yield full_response
            success_msg = f"[SUCCESS] [{self.name}] Task completed. Fixed code saved to GDrive file ID: {file_id}"
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
                correction_guidance="The agent failed during code fixing or validation. Analyze the error and context to provide a fix."
            ):
                yield chunk

    async def _prepare_and_construct_prompt(self, task: str, context: Dict, operation_type: str) -> Tuple[str, Dict[str, Any]]:
        """Prepares data and constructs the prompt for both fix_and_create and update_existing operations."""
        if operation_type == "fix_and_create":
            gdrive_file_id = context.get("gdrive_file_id")
            if not gdrive_file_id: raise ValueError("Missing 'gdrive_file_id' in context for create operation.")
            
            gdrive_content = await self._read_gdrive_file(gdrive_file_id, "code file", task, context) or ""
            bug_report_content = ""
            if context.get("bug_report_file_id"):
                bug_report_content = await self._read_gdrive_file(context["bug_report_file_id"], "bug report", task, context) or ""

            template_name = self.config.get("create_template", "fix_agent_create.txt")
            template_data = {"task": task, "code_to_fix": gdrive_content, "bug_report": bug_report_content}
            
            output_filename = context.get("output_filename", "fixed_code.py")
            parent_folder_id = context.get("parent_folder_id")
            if not parent_folder_id: raise ValueError("Missing 'parent_folder_id' in context for saving output.")
            file_op_details = {"filename": output_filename, "parent_id": parent_folder_id}

        elif operation_type == "update_existing":
            existing_file_id = context.get("existing_file_id")
            if not existing_file_id: raise ValueError("Missing 'existing_file_id' for update operation.")

            gdrive_content = await self._read_gdrive_file(existing_file_id, "existing code file", task, context) or ""
            error_description = context.get("error_description", "No specific error description provided.")
            patch_instructions = context.get("patch_instructions", "")

            template_name = self.config.get("update_template", "fix_agent_update.txt")
            template_data = {"task": task, "existing_code": gdrive_content, "error_description": error_description, "patch_instructions": patch_instructions}
            file_op_details = {"file_id": existing_file_id}
        
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        prompt = self._construct_prompt(template_name, **template_data)
        return prompt, file_op_details
