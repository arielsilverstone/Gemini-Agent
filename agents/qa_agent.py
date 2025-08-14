# ============================================================================
#  File: qa_agent.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: QA Agent for Gemini-Agent
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
# SECTION 2: QaAgent Class
# ============================================================================
class QaAgent(AgentBase):
    """Agent responsible for answering questions about code and performing quality assurance."""

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

    @record_telemetry("QAAgent", "run")
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[str]:
        """Execute the QA task and yield output chunks."""
        context = context or {}
        self.update_context(context)
        log_message = f"[{self.name}] Starting QA task: {task}"
        logging.info(log_message)
        yield f"STREAM_CHUNK:{self.name}:{log_message}\n"

        try:
            operation_type = context.get("operation_type", "answer_with_context")

            # 1. Prepare data and construct prompt
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Preparing data for operation: {operation_type}...\n"
            prompt, file_op_details = await self._prepare_and_construct_prompt(task, context, operation_type)

            # 2. Execute LLM and Buffer Response
            yield f"STREAM_CHUNK:{self.name}:[{self.name}] Generating QA response...\n"
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

            # 4. Perform File Operation (if any) and Stream Validated Response
            if file_op_details:
                yield f"STREAM_CHUNK:{self.name}:[{self.name}] Validation passed. Saving to Google Drive...\n"
                file_id = await self._write_gdrive_file(file_op_details['filename'], full_response, file_op_details['parent_id'])
                if not file_id:
                    raise IOError("Failed to save the QA output to Google Drive.")
                success_msg = f"[SUCCESS] [{self.name}] Task completed. Output saved to GDrive file ID: {file_id}"
            else:
                success_msg = f"[SUCCESS] [{self.name}] Task completed successfully."

            yield full_response
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
                correction_guidance="The agent failed during QA processing or validation. Analyze the error and context to provide a correct response."
            ):
                yield chunk

    async def _prepare_and_construct_prompt(self, task: str, context: Dict, operation_type: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Prepares data and constructs the prompt for all QA operations."""
        template_data = {"task": task}
        file_op_details = None

        if operation_type == "answer_with_context":
            gdrive_file_id = context.get("gdrive_file_id")
            if not gdrive_file_id: raise ValueError("Missing 'gdrive_file_id' in context.")
            template_data["code_to_analyze"] = await self._read_gdrive_file(gdrive_file_id, "code file", task, context) or ""
            template_name = self.config.get("answer_with_context_template", "qa_agent_answer_with_context.txt")

        elif operation_type == "answer_without_context":
            template_name = self.config.get("answer_without_context_template", "qa_agent_answer_without_context.txt")

        elif operation_type == "generate_qa_pairs":
            gdrive_file_id = context.get("gdrive_file_id")
            if not gdrive_file_id: raise ValueError("Missing 'gdrive_file_id' for generating QA pairs.")
            template_data["code_to_analyze"] = await self._read_gdrive_file(gdrive_file_id, "code file", task, context) or ""
            template_name = self.config.get("generate_qa_pairs_template", "qa_agent_generate_qa_pairs.txt")

        elif operation_type == "review_requirements":
            req_id = context.get("requirements_file_id")
            test_id = context.get("test_results_file_id")
            template_data["requirements"] = (await self._read_gdrive_file(req_id, "requirements file", task, context) or "") if req_id else ""
            template_data["test_results"] = (await self._read_gdrive_file(test_id, "test results file", task, context) or "") if test_id else ""
            template_name = self.config.get("review_requirements_template", "qa_agent_review_requirements.txt")

        elif operation_type == "generate_qa_report":
            gdrive_file_id = context.get("gdrive_file_id")
            if not gdrive_file_id: raise ValueError("Missing 'gdrive_file_id' for generating QA report.")
            template_data["code_to_analyze"] = await self._read_gdrive_file(gdrive_file_id, "code file", task, context) or ""
            template_name = self.config.get("generate_qa_report_template", "qa_agent_generate_qa_report.txt")

        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        # Common logic for operations that save output
        if operation_type != "answer_without_context":
            output_filename = context.get("output_filename", f"{operation_type}_output.md")
            parent_folder_id = context.get("parent_folder_id")
            if not parent_folder_id: raise ValueError("Missing 'parent_folder_id' in context for saving output.")
            file_op_details = {"filename": output_filename, "parent_id": parent_folder_id}

        prompt = self._construct_prompt(template_name, **template_data)
        return prompt, file_op_details

    async def _answer_question_without_context(self, task: str, context: Dict) -> AsyncIterator[str]:
        """Answer a question without specific file context using the LLM."""
        if self.websocket_manager:
            await self.websocket_manager.send_message_to_client(
                f"STREAM_CHUNK:{self.name}:[{self.name}] Answering question without file context...\n"
            )
        # Construct the prompt
        try:
            template_name = self.config.get("answer_without_context_template", "qa_agent_answer_without_context.txt")
            template_data = {"task": task, "context_summary": str(context)}
            prompt = self._construct_prompt(template_name, **template_data)
        except ValueError as e:
            error_msg = f"[ERROR] [{self.name}] Failed to construct prompt: {e}"
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        # Execute the centralized workflow and stream the response
        full_response = ""
        async for chunk in self._execute_llm_workflow(
            prompt=prompt, task=task, context=context
        ):
            yield chunk
            full_response += chunk

        # Post-streaming actions: rule enforcement
        if not full_response.strip() or "[ERROR]" in full_response:
            yield "[INFO] Skipping rule checks due to empty or error response."
            return

        rule_violations = await self._enforce_agent_rules(full_response, task, context)
        if rule_violations:
            violation_details = "; ".join(
                [f"{v['rule_name']}: {v['message']}" for v in rule_violations]
            )
            error_msg = f"[RULE_VIOLATION] [{self.name}] Agent-specific rules violated: {violation_details}"
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        yield "\n[SUCCESS] Question answered successfully."

    async def _generate_qa_pairs(self, task: str, context: Dict) -> AsyncIterator[str]:
        """Generate question-answer pairs from a document."""
        # Read GDrive file for content
        gdrive_file_id = context.get("gdrive_file_id")
        if not gdrive_file_id:
            error_msg = f"[ERROR] [{self.name}] Missing 'gdrive_file_id' for generating QA pairs."
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        gdrive_content = await self._read_gdrive_file(
            gdrive_file_id, "source document", task, context
        )
        if gdrive_content is None:
            return  # Error handled in helper

        # Construct the prompt
        try:
            template_name = self.config.get("generate_qa_pairs_template", "qa_agent_generate_qa_pairs.txt")
            template_data = {"task": task, "gdrive_content": gdrive_content}
            prompt = self._construct_prompt(template_name, **template_data)
        except ValueError as e:
            error_msg = f"[ERROR] [{self.name}] Failed to construct prompt: {e}"
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        # Define output parameters
        output_filename = context.get("output_filename", "generated_qa_pairs.md")
        parent_folder_id = context.get("parent_folder_id")

        if not parent_folder_id:
            error_msg = f"[ERROR] [{self.name}] Missing 'parent_folder_id' in context for saving output."
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        # Execute the centralized workflow and stream the response
        full_response = ""
        async for chunk in self._execute_llm_workflow(
            prompt=prompt, task=task, context=context
        ):
            yield chunk
            full_response += chunk

        # Post-streaming actions: rule enforcement and file writing
        if not full_response.strip() or "[ERROR]" in full_response:
            yield "[INFO] Skipping rule checks and file write due to empty or error response."
            return

        rule_violations = await self._enforce_agent_rules(full_response, task, context)
        if rule_violations:
            violation_details = "; ".join(
                [f"{v['rule_name']}: {v['message']}" for v in rule_violations]
            )
            error_msg = f"[RULE_VIOLATION] [{self.name}] Agent-specific rules violated: {violation_details}"
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        # Write the final response to Google Drive
        file_id = await self._write_gdrive_file(
            output_filename, full_response, parent_folder_id
        )
        if file_id:
            yield f"\n[SUCCESS] QA pairs saved to GDrive file ID: {file_id}"

    async def _generate_qa_report(self, task: str, context: Dict) -> AsyncIterator[str]:
        """Generate comprehensive QA report based on analysis results."""
        qa_findings = context.get("qa_findings")
        if not qa_findings:
            error_msg = f"[ERROR] [{self.name}] No 'qa_findings' provided in context."
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        bug_reports = context.get("bug_reports", "")
        yield f"STREAM_CHUNK:{self.name}:[{self.name}] Formatting QA report...\n"
        report_content = self._format_qa_report(qa_findings, bug_reports, context)

        # Define output parameters
        output_filename = context.get("output_filename", "qa_report.md")
        parent_folder_id = context.get("parent_folder_id")

        if not parent_folder_id:
            error_msg = f"[ERROR] [{self.name}] Missing 'parent_folder_id' in context for saving report."
            if self.websocket_manager:
                await self.websocket_manager.send_message_to_client(error_msg)
            yield error_msg
            return

        # Write report directly to Google Drive
        file_id = await self._write_gdrive_file(
            output_filename, report_content, parent_folder_id
        )

        if file_id:
            yield f"\n[SUCCESS] QA report saved to GDrive file ID: {file_id}"
        else:
            yield f"\n[ERROR] Failed to save QA report to GDrive."

    def _format_qa_report(
        self, qa_findings: str, bug_reports: str, context: Dict
    ) -> str:
        """Format QA findings into a comprehensive report."""
        timestamp = context.get("timestamp", "Unknown")
        project_name = context.get("project_name", "Unknown Project")

        default_next_steps = (
            "1. Address critical issues\n"
            "2. Review medium priority items\n"
            "3. Schedule follow-up QA review"
        )
        formatted_report = f"""# Quality Assurance Report - {project_name}

## Report Information
- **Generated**: {timestamp}
- **QA Agent**: Gemini-Agent System
- **Scope**: {context.get('qa_scope', 'Full codebase analysis')}

## Executive Summary
{context.get('executive_summary', 'Comprehensive quality assurance analysis completed.')}

## Quality Findings
{qa_findings}

## Bug Reports
{bug_reports}

## Code Quality Metrics
- **Compliance Score**: {context.get('compliance_score', 'Not measured')}
- **Test Coverage**: {context.get('test_coverage', 'Not measured')}
- **Security Issues**: {context.get('security_issues_count', '0')} found

## Recommendations
{context.get('recommendations', 'No specific recommendations at this time.')}

## Next Steps
{context.get('next_steps', default_next_steps)}

---
Generated by QAAgent - Gemini-Agent System
"""
        return formatted_report

    def _get_prompt_template_data(
        self, task: str, context: Dict, gdrive_content: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Provides the data for the QA agent's prompt template.
        This implementation returns a default template name and a data dictionary
        with common QA parameters.
        """
        template_name = self.config.get("template", "qa_template.txt")
        template_data = {
            "task": task,
            "context_summary": str(context),
            "gdrive_content": gdrive_content,
            "qa_scope": context.get("qa_scope", "Full codebase analysis"),
            "compliance_rules": context.get("compliance_rules", "No specific compliance rules provided."),
        }
        return template_name, template_data
#
#
## End of Script
