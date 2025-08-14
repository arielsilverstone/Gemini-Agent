# ============================================================================
#  File: orchestrator.py
#  Version: 1.2 (Corrected)
#  Purpose: Manages agent workflows, context, and execution.
#  Created: 30JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, AsyncIterator, AsyncGenerator, cast

from src.config_manager import ConfigManager
from src.rule_engine import RuleEngine
from src.websocket_manager import WebSocketManager

# Import all agent classes
from agents.agent_base import AgentBase
from agents.codegen_agent import CodeGenAgent
from agents.doc_agent import DocAgent
from agents.fix_agent import FixAgent
from agents.planner_agent import PlannerAgent
from agents.qa_agent import QaAgent
from agents.test_agent import TestAgent

# ============================================================================
# SECTION 2: Class Definition - Orchestrator
# ============================================================================
class Orchestrator:
    """
    The Orchestrator is the central component that manages the lifecycle and
    execution of AI agents based on a defined workflow.
    """

    def __init__(self, config_manager: ConfigManager, rule_engine: RuleEngine, websocket_manager: WebSocketManager):
        self.config_manager = config_manager
        self.rule_engine = rule_engine
        self.websocket_manager = websocket_manager
        self.context: Dict[str, Any] = {}
        self.agents: Dict[str, AgentBase] = {}
        self._load_agents() # Initial load

    def reload_config(self):
        """Reloads agent configurations and re-initializes agents."""
        logging.info("Configuration changed. Reloading agents...")
        self._load_agents()

    def _load_agents(self):
        """Loads and initializes all agents defined in the configuration."""
        agent_configs = self.config_manager.get().llm_configurations
        if not agent_configs:
            logging.error("No agent configurations found. Cannot load agents.")
            return

        agent_class_map = {
            "codegen": CodeGenAgent,
            "doc": DocAgent,
            "fix": FixAgent,
            "planner": PlannerAgent,
            "qa": QaAgent,
            "test": TestAgent,
        }

        self.agents.clear()
        for agent_name, config in agent_configs.items():
            if agent_name in agent_class_map:
                agent_class = agent_class_map[agent_name]
                try:
                    self.agents[agent_name] = agent_class(
                        name=agent_name,
                        config=config,
                        websocket_manager=self.websocket_manager,
                        rule_engine=self.rule_engine,
                        config_manager=self.config_manager,
                    )
                    logging.info(f"Successfully loaded agent: {agent_name}")
                except Exception as e:
                    logging.error(f"Failed to load agent '{agent_name}': {e}", exc_info=True)
            else:
                logging.warning(f"Agent type '{agent_name}' defined in config but no corresponding class found.")

    async def run_workflow(self, workflow: List[Dict[str, Any]]):
        """Executes a sequence of agent tasks defined in a workflow."""
        self.context = {"initial_workflow": workflow, "outputs": {}}
        await self.websocket_manager.send_message_to_client("[INFO] Starting workflow execution...")
        for i, task_def in enumerate(workflow):
            task_name = task_def.get('name', f'Task {i+1}')
            agent_type = task_def.get('agent')
            task_description = task_def.get('task')

            if not agent_type:
                await self.websocket_manager.send_message_to_client(f"[ERROR] Skipping invalid task '{task_name}': missing agent type.")
                continue
            if not task_description:
                await self.websocket_manager.send_message_to_client(f"[ERROR] Skipping invalid task '{task_name}': missing task description.")
                continue

            agent = self._get_agent(agent_type)
            if not agent:
                await self.websocket_manager.send_message_to_client(f"[ERROR] Agent '{agent_type}' not found for task '{task_name}'.")
                continue

            await self.websocket_manager.send_message_to_client(f"[INFO] Executing task '{task_name}' with agent '{agent_type}'.")

            final_output = ""
            async for chunk in self._execute_task(agent, task_description):
                await self.websocket_manager.send_message_to_client(chunk)
                if not chunk.startswith("STREAM_CHUNK:"):
                    final_output += chunk

            self.update_context({f"{agent_type}_output": final_output})

        await self.websocket_manager.send_message_to_client("[INFO] Workflow execution complete.")

    async def _execute_task(self, agent: AgentBase, task: str) -> AsyncGenerator[str, None]:
        """Executes a single agent task and yields its output chunks."""
        try:
            run_result = await agent.run(task, self.context)
            run_result = cast(AsyncIterator[str], run_result)
            async for chunk in run_result:
                yield str(chunk)
        except Exception as e:
            error_message = f"[ERROR] Unhandled exception in agent '{agent.name}': {e}"
            logging.error(error_message, exc_info=True)
            yield error_message

    def update_context(self, new_context_data: Dict[str, Any]):
        """Updates the shared context with new data."""
        self.context.update(new_context_data)
        logging.info(f"Orchestrator context updated with keys: {list(new_context_data.keys())}")

    async def handle_ipc(self, agent_type: str, task: str, **kwargs) -> str:
        """Handles a single, direct task for a specific agent."""
        agent = self._get_agent(agent_type)
        if not agent:
            error_msg = f"[ERROR] Agent '{agent_type}' not found for IPC task."
            logging.error(error_msg)
            return error_msg

        logging.info(f"Executing IPC task for agent '{agent_type}': {task}")
        try:
            run_result = await agent.run(task, self.context)
            run_result = cast(AsyncIterator[str], run_result)
            output_chunks = []
            async for chunk in run_result:
                output_chunks.append(str(chunk))
            final_output = "".join([c for c in output_chunks if not c.startswith("STREAM_CHUNK:")])
            return final_output
        except Exception as e:
            error_msg = f"[ERROR] Unhandled exception in IPC for agent '{agent.name}': {e}"
            logging.error(error_msg, exc_info=True)
            return error_msg

    def _get_agent(self, agent_type: str) -> Optional[AgentBase]:
        """Retrieves a loaded agent instance by its type name."""
        return self.agents.get(agent_type)

    async def shutdown(self):
        """Performs cleanup operations during application shutdown."""
        logging.info("Orchestrator shutting down...")
        await self.websocket_manager.disconnect_all()
