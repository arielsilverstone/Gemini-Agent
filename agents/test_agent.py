# ============================================================================
#  File: test_agent.py
#  Version: 1.2 (Fixed KeyError Issues)
#  Purpose: Test Generation Agent for Gemini-Agent
#  Created: 30JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import asyncio
import logging
from typing import Any, AsyncGenerator, AsyncIterator, Dict, Optional, Tuple

# Fixed imports - removed relative imports
from agents.agent_base import AgentBase
from src.error_handling import agent_self_correct
from src.telemetry import record_telemetry


# ============================================================================
# SECTION 2: TestAgent Class
# ============================================================================
class TestAgent(AgentBase):
    """Agent responsible for generating unit tests for code and writing test results."""

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

    @record_telemetry("TestAgent", "run")
    async def run(self, task: str, context: dict) -> AsyncIterator[str]:
        """
        Executes the test task by buffering the response, validating it,
        and then streaming it and saving the file if successful.
        """
        self.update_context(context)
        operation_type = context.get("operation_type", "generate_tests")
        if self.websocket_manager:
            await self.websocket_manager.send_message_to_client(
                f"STREAM_CHUNK:{self.name}:[{self.name}] Starting operation: {operation_type}...\n"
            )

        try:
            if operation_type == "generate_tests":
                prompt, file_op_details = await self._prepare_and_construct_prompt(task, context)

                full_response = ""
                async for chunk in self._execute_llm_workflow(prompt, task, context):
                    full_response += chunk

                if not full_response.strip() or "[ERROR]" in full_response:
                    error_msg = f"[{self.name}] LLM workflow failed or returned empty response."
                    yield error_msg
                    async for chunk in agent_self_correct(
                        agent=self,
                        original_task=task,
                        current_context=context,
                        error_details=error_msg,
                        error_type="llm_response_error",
                        correction_guidance="The LLM failed to generate a valid response. Please analyze the prompt and try again."
                    ):
                        yield chunk
                    return

                rule_violations = await self._enforce_agent_rules(full_response, task, context)
                if rule_violations:
                    violation_details = "; ".join([f"{v['rule_name']}: {v['message']}" for v in rule_violations])
                    error_msg = f"[RULE_VIOLATION] [{self.name}] Agent-specific rules violated: {violation_details}"
                    yield error_msg
                    async for chunk in agent_self_correct(
                        agent=self,
                        original_task=task,
                        current_context=context,
                        error_details=error_msg,
                        error_type="rule_violation",
                        correction_guidance=f"The output violated rules: {violation_details}. Please regenerate the output to comply."
                    ):
                        yield chunk
                    return

                file_id = await self._write_gdrive_file(
                    file_op_details["filename"], full_response, file_op_details["parent_id"]
                )

                yield full_response

                if file_id:
                    yield f"\n[SUCCESS] Output saved to GDrive file ID: {file_id}"

            elif operation_type == "write_test_results":
                formatted_results = self._format_test_results(context)
                output_filename = context.get("output_filename", "test_results.md")
                parent_folder_id = context.get("parent_folder_id")
                if not parent_folder_id:
                    raise ValueError("Missing 'parent_folder_id' in context for saving output.")

                file_id = await self._write_gdrive_file(
                    output_filename, formatted_results, parent_folder_id
                )

                if file_id:
                    yield f"\n[SUCCESS] Test results saved to GDrive file ID: {file_id}"
                else:
                    yield f"\n[ERROR] Failed to save test results to GDrive."

            else:
                raise ValueError(f"Unknown operation type: {operation_type}")

        except (ValueError, KeyError) as e:
            error_message = f"[ERROR] [{self.name}] Validation error: {e}"
            logging.error(error_message, exc_info=True)
            yield error_message
            async for chunk in agent_self_correct(
                agent=self,
                original_task=task,
                current_context=context,
                error_details=str(e),
                error_type="validation_error",
                correction_guidance="A data validation or key error occurred. Check the context data and the agent's logic."
            ):
                yield chunk
        except Exception as e:
            error_message = f"[ERROR] [{self.name}] Unhandled exception in run: {e}"
            logging.error(error_message, exc_info=True)
            yield error_message
            async for chunk in agent_self_correct(
                agent=self,
                original_task=task,
                current_context=context,
                error_details=str(e),
                error_type="unhandled_exception",
                correction_guidance="An unexpected error occurred. Analyze the stack trace and context to find the root cause."
            ):
                yield chunk

    async def _prepare_and_construct_prompt(self, task: str, context: Dict) -> Tuple[str, Dict[str, str]]:
        """Prepares data and constructs the prompt for test generation."""
        gdrive_file_id = context.get("gdrive_file_id")
        if not gdrive_file_id:
            raise ValueError("Missing 'gdrive_file_id' in context.")

        gdrive_content = await self._read_gdrive_file(gdrive_file_id, "code file", task, context)
        if not gdrive_content:
            raise ValueError(f"Failed to read or empty content from GDrive file: {gdrive_file_id}")

        template_name = self.config.get("generate_template", "test_agent_generate.txt")
        template_data = {
            "task": task,
            "code_to_test": gdrive_content,
            "test_framework": context.get("framework", "pytest"),
        }
        prompt = self._construct_prompt(template_name, **template_data)

        output_filename = context.get("output_filename", "test_generated.py")
        parent_folder_id = context.get("parent_folder_id")
        if not parent_folder_id:
            raise ValueError("Missing 'parent_folder_id' in context for saving output.")

        file_op_details = {"filename": output_filename, "parent_id": parent_folder_id}
        return prompt, file_op_details

    def _format_test_results(
        self, context: Dict
    ) -> str:
        """Format test results into a comprehensive report."""
        test_results = context.get("test_results", "")
        test_summary = context.get("test_summary", "")
        timestamp = context.get("timestamp", "Unknown")
        test_framework = context.get("framework", "pytest")

        formatted_results = f"""# Test Execution Results

## Summary
- **Timestamp**: {timestamp}
- **Framework**: {test_framework}
- **Test Suite**: {context.get('test_suite', 'Unknown')}

## Test Summary
{test_summary}

## Detailed Results
```
{test_results}
```

## Recommendations
{context.get('recommendations', 'No specific recommendations.')}

---
Generated by TestAgent - Gemini-Agent System
"""
        return formatted_results
