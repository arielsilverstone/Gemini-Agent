# Gemini-Agent Agents Directory

This directory contains all specialized AI agent modules for the Gemini-Agent project. Each agent is a Python module implementing a specific role (e.g., CodeGen, QA, Test, Fix, Planner).

* All agents are now fully implemented.
* No mock logic remains; all LLM and GDrive operations are real.
* Production-ready as of 29JUL25.

* Structure: `agents/<agent_name>.py `
* Base class: `agent_base.py `
* All agents must strictly adhere to user rules and templates.

---
Created: 28JUL25
