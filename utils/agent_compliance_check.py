# ============================================================================
# Agent Compliance Review Script
# Version: 1.00
# Purpose: Automated checklist-based review of all agent files for architectural and coding best practices.
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================

import os
import ast
from typing import Dict, List, Tuple
from loguru import logger

AGENT_FILES = [
    "planner_agent.py",
    "codegen_agent.py",
    "test_agent.py",
    "qa_agent.py",
    "fix_agent.py",
    "doc_agent.py",
]

AGENTS_DIR = r"d:\Program Files\Dev\projects\Gemini-Agent\agents"

CHECKLIST = {
    "A1": "All imports at module top?",
    "A2": "No misplaced imports?",
    "A3": "__init__ accepts config, websocket_manager, rule_engine and passes to super?",
    "B1": "run uses async for chunk in _stream_llm_response(...) pattern?",
    "B2": "No return in main try block of run?",
    "B3": "Error handling (try-except) around LLM/GDrive ops?",
    "B4": "agent_self_correct invoked in every except with all params?",
    "B5": "telemetry.record_agent_start/end at start/end of run?",
    "B6": "No yield [ERROR] outside try-except or unreachable?",
    "C1": "gdrive_integration imported?",
    "C2": "GDrive ops use await gdrive_integration.<method>()?",
    "C3": "Every GDrive call wrapped in try-except?",
    "C4": "agent_self_correct in GDrive except with correct error_type/guidance?",
    "D1": "self.rule_engine.get_agent_rules(self.agent_type) used?",
    "D2": "Rule validation after output accumulation?",
    "D3": "Rule violations trigger agent_self_correct with llm_guidance?",
    "E1": "_construct_prompt uses config_manager.get_template_content()?",
    "E2": "template_override logic present?",
    "E3": "Template formatted with variables?",
}

# ============================================================================
# SECTION 2: Utility functions for AST checks
# ============================================================================

def get_imports(tree):
    return [n for n in tree.body if isinstance(n, ast.Import) or isinstance(n, ast.ImportFrom)]

def has_import_in_function(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in node.body:
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    return True
    return False

def check_init(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            args = [a.arg for a in node.args.args]
            if all(x in args for x in ["config", "websocket_manager", "rule_engine"]):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == '__init__':
                        return True
    return False

def check_run_pattern(tree, source_code: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
            src = ast.get_source_segment(source_code, node)
            if src and "async for chunk in self._stream_llm_response" in src:
                return True
    return False

def check_return_in_run_try(tree):
    # Look for return in main try of run
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
            for sub in node.body:
                if isinstance(sub, ast.Try):
                    for stmt in sub.body:
                        if isinstance(stmt, ast.Return):
                            return True
    return False

def check_telemetry(tree, source_code: str):
    start, end = False, False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
            src = ast.get_source_segment(source_code, node)
            if src and "self.telemetry.record_agent_start()" in src:
                start = True
            if src and "self.telemetry.record_agent_end()" in src:
                end = True
    return start and end

def check_gdrive_import(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "gdrive_integration" in node.module:
                return True
    return False

def check_gdrive_await(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            if hasattr(node.value, 'attr') and 'gdrive_integration' in ast.dump(node.value):
                return True
    return False

def check_rule_engine(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == "get_agent_rules":
                return True
    return False

def check_template_content(tree, source_code: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_construct_prompt":
            src = ast.get_source_segment(source_code, node)
            if src and "config_manager.get_template_content" in src:
                return True
    return False

def check_template_override(tree, source_code: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_construct_prompt":
            src = ast.get_source_segment(source_code, node)
            if src and "template_override" in src:
                return True
    return False

def check_template_format(tree, source_code: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_construct_prompt":
            src = ast.get_source_segment(source_code, node)
            if src and (".format(" in src or "f'" in src or 'f"' in src):
                return True
    return False

# ============================================================================
# SECTION 3: Review Functions
# ============================================================================

def review_agent_file(agent_file: str) -> Dict[str, Tuple[str, str]]:
    """
    Review an agent file against compliance rules.

    Args:
        agent_file: Name of the agent file to review

    Returns:
        Dictionary of compliance check results
    """
    
    path = os.path.join(AGENTS_DIR, agent_file)

    # Read file content with proper resource management
    try:
        with open(path, "r", encoding="utf-8") as f:
            opened_code = f.read()
    except Exception as e:
        print(f"Error reading file {agent_file}: {str(e)}")
        return {}

    # Parse the file content
    try:
        tree = ast.parse(opened_code)
        results = {}

        # A. Imports & Initialization
        results["A1"] = ("Pass" if len(get_imports(tree)) > 0 else "Fail", "")
        results["A2"] = ("Fail" if has_import_in_function(tree) else "Pass", "Import inside function" if has_import_in_function(tree) else "")
        results["A3"] = ("Pass" if check_init(tree) else "Fail", "__init__ missing params or no super call")

        # B. run method
        results["B1"] = ("Pass" if check_run_pattern(tree, opened_code) else "Fail", "Pattern not found")
        results["B2"] = ("Fail" if check_return_in_run_try(tree) else "Pass", "Return in main try")
        results["B5"] = ("Pass" if check_telemetry(tree, opened_code) else "Fail", "Telemetry missing")

        # C. GDrive
        results["C1"] = ("Pass" if check_gdrive_import(tree) else "Fail", "No gdrive_integration import")
        results["C2"] = ("Pass" if check_gdrive_await(tree) else "Fail", "No await gdrive_integration call")

        # D. Rule Engine
        results["D1"] = ("Pass" if check_rule_engine(tree) else "Fail", "No rule_engine.get_agent_rules")

        # E. Template Management
        results["E1"] = ("Pass" if check_template_content(tree, opened_code) else "Fail", "No config_manager.get_template_content")
        results["E2"] = ("Pass" if check_template_override(tree, opened_code) else "Fail", "No template_override logic")
        results["E3"] = ("Pass" if check_template_format(tree, opened_code) else "Fail", "Template not formatted with variables")

        return results

    except SyntaxError as e:
        logger.error(
            f"Syntax error in {agent_file}: {str(e)}",
            extra={"file": agent_file, "error_type": "syntax_error"}
        )
        return {}
    except Exception as e:
        logger.critical(
            f"Unexpected error processing {agent_file}: {str(e)}",
            exc_info=True,
            extra={"file": agent_file, "error_type": "processing_error"}
        )
        return {}

# ============================================================================
# SECTION 4: Main Function
# ============================================================================

def main():
    summary = ""
    for agent_file in AGENT_FILES:
        summary += f"--- Agent: {agent_file} ---\n"
        results = review_agent_file(agent_file)
        for k, desc in CHECKLIST.items():
            if k in results:
                status, detail = results[k]
                summary += f"{desc}: {status}"
                if status == "Fail" and detail:
                    summary += f" - {detail}"
                summary += "\n"
        summary += "\n"
    print(summary)

if __name__ == "__main__":
    main()
#
#
## End Of Script
