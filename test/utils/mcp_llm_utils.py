# ============================================================================
# SECTION 1: Imports
# ============================================================================
import requests
from typing import Dict, Any, List

from src.config import MCP_SERVERS

# ============================================================================
# SECTION 2: Functions
# ============================================================================
def load_mcp_servers() -> Dict[str, Any]:
    """Load MCP server configurations from config."""
    print("Loading MCP servers...")
    return {server['name']: server for server in MCP_SERVERS}

def call_filesystem_rpc(endpoint: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Calls a method on the FileSystem MCP server via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=5)
        response.raise_for_status()
        return response.json().get('result')
    except requests.RequestException as e:
        print(f"Error calling filesystem RPC: {e}")
        return {}

def get_memory_tools(endpoint: str) -> Dict[str, Any]:
    """Retrieves the list of available tools from the Memory MCP."""
    try:
        response = requests.get(f"{endpoint}/tools", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting memory tools: {e}")
        return {}

def call_memory_tool(endpoint: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Calls a specific tool on the Memory MCP."""
    try:
        response = requests.post(f"{endpoint}/tools/{tool_name}/call", json=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error calling memory tool {tool_name}: {e}")
        return {}
