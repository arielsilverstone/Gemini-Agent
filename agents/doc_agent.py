# ============================================================================
#  File: doc_agent.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: Documentation Agent for Gemini-Agent
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
# SECTION 2: DocAgent Class
# ============================================================================
class DocAgent(AgentBase):
    """Agent responsible for generating documentation for code and updating existing docs."""

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

    @record_telemetry("DocAgent", "run")
    async def run(self, task: str, context: dict) -> AsyncIterator[str]:
        """
        Executes the documentation task by buffering the response, validating it,
        and then streaming it and saving the file if successful.
        """
        self.update_context(context)
        log_message = f"[{self.name}] Starting documentation task: {task}"
        logging.info(log_message)
        yield f"STREAM_CHUNK:{self.name}:{log_message}\n"

        try:
            operation_type = context.get("operation_type", "generate_new")
            
            # 1. Prepare data and construct prompt based on operation type
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Preparing data for operation: {operation_type}...\n"
            prompt, file_operation_details = await self._prepare_and_construct_prompt(task, context, operation_type)

            # 2. Execute LLM and Buffer Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Generating documentation...\n"
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
            if operation_type == "generate_new":
                file_id = await self._write_gdrive_file(file_operation_details['filename'], full_response, file_operation_details['parent_id'])
            else: # update_existing
                success = await self._update_gdrive_file(file_operation_details['file_id'], full_response, "documentation")
                file_id = file_operation_details['file_id'] if success else None

            if not file_id:
                raise IOError("Failed to save the generated documentation to Google Drive.")

            yield full_response
            success_msg = f"[SUCCESS] [{self.name}] Task completed. Documentation saved to GDrive file ID: {file_id}"
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
                correction_guidance="The agent failed during documentation generation or validation. Analyze the error and context to provide a fix."
            ):
                yield chunk

    async def _prepare_and_construct_prompt(self, task: str, context: Dict, operation_type: str) -> Tuple[str, Dict[str, Any]]:
        """Prepares data and constructs the prompt for both generate and update operations."""
        if operation_type == "generate_new":
            gdrive_file_id = context.get("gdrive_file_id")
            if not gdrive_file_id: raise ValueError("Missing 'gdrive_file_id' in context for generate operation.")
            
            gdrive_content = await self._read_gdrive_file(gdrive_file_id, "code file", task, context) or ""
            existing_docs_content = ""
            if context.get("existing_docs_file_id"):
                existing_docs_content = await self._read_gdrive_file(context["existing_docs_file_id"], "existing documentation", task, context) or ""

            template_name = self.config.get("generate_template", "doc_agent_generate.txt")
            template_data = {"task": task, "code_to_document": gdrive_content, "existing_documentation": existing_docs_content}
            
            output_filename = context.get("output_filename", "documentation.md")
            parent_folder_id = context.get("parent_folder_id")
            if not parent_folder_id: raise ValueError("Missing 'parent_folder_id' in context for saving output.")
            file_op_details = {"filename": output_filename, "parent_id": parent_folder_id}

        elif operation_type == "update_existing":
            existing_docs_file_id = context.get("existing_docs_file_id")
            if not existing_docs_file_id: raise ValueError("Missing 'existing_docs_file_id' for update operation.")

            existing_docs_content = await self._read_gdrive_file(existing_docs_file_id, "existing documentation", task, context) or ""
            source_code_content = ""
            if context.get("source_code_file_id"):
                source_code_content = await self._read_gdrive_file(context["source_code_file_id"], "source code", task, context) or ""
            
            update_instructions = context.get("update_instructions", "Update and improve the existing documentation.")
            template_name = self.config.get("update_template", "doc_agent_update.txt")
            template_data = {"task": task, "existing_documentation": existing_docs_content, "source_code": source_code_content, "update_instructions": update_instructions}
            file_op_details = {"file_id": existing_docs_file_id}
        
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        prompt = self._construct_prompt(template_name, **template_data)
        return prompt, file_op_details
