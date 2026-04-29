# ============================================================================
#  File: evidence_verifier_agent.py
#  Purpose: Validate and normalize evidence findings for defendant-direct research.
# ============================================================================
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

from agents.agent_base import AgentBase
from src.error_handling import agent_self_correct
from src.telemetry import record_telemetry


class EvidenceVerifierAgent(AgentBase):
    """Agent that double-verifies evidence records and emits corrected findings."""

    @record_telemetry("EvidenceVerifierAgent", "run")
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[str]:
        context = context or {}
        self.update_context(context)
        yield f"STREAM_CHUNK:{self.name}:[{self.name}] Starting evidence verification workflow.\n"

        try:
            findings_payload = context.get("findings_payload", "")
            prompt = self._construct_prompt(
                "evidence_verifier_template.txt",
                task=task,
                findings_payload=(findings_payload if isinstance(findings_payload, str) else json.dumps(findings_payload, indent=2)),
            )

            full_response = ""
            async for chunk in self._execute_llm_workflow_with_rules(prompt=prompt, task=task, context=context):
                full_response += chunk
                yield chunk

            if not full_response.strip():
                raise ValueError("Evidence verification returned an empty response.")

            yield f"\n[SUCCESS] [{self.name}] Evidence verification report emitted."

        except Exception as e:
            logging.error(f"[{self.name}] Evidence verification failed: {e}", exc_info=True)
            async for chunk in agent_self_correct(
                agent=self,
                original_task=task,
                current_context=context,
                error_details=str(e),
                error_type="agent_execution_error",
                correction_guidance="Return corrected, verified evidence JSON with hallucination checks and source metadata.",
            ):
                yield chunk
