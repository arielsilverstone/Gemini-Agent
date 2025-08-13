# ============================================================================
#  File: mcp_integration.py
#  Version: 2.0.0 (Deno-compatible)
# ============================================================================
import json
import os
import requests
import uuid

# Use a relative path for the configuration file for better portability
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'mcp_servers.json'))

def load_mcp_servers():
    """Loads MCP server configurations from the specified JSON file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        # Separate servers by expected port for clarity in tests
        servers = config.get('servers', [])
        return {
            'filesystem': next((s for s in servers if '9006' in s['endpoint']), None),
            'memory': next((s for s in servers if '9007' in s['endpoint']), None),
        }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing MCP config: {e}")
        return {'filesystem': None, 'memory': None}

# ============================================================================
# SECTION 2: FileSystem MCP Client (JSON-RPC)
# ============================================================================
def call_filesystem_rpc(endpoint, method, params=None):
    """Calls a method on the JSON-RPC FileSystem server."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": str(uuid.uuid4())
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        json_response = response.json()
        if "error" in json_response:
            print(f"JSON-RPC Error for method '{method}': {json_response['error']}")
            return None
        return json_response.get("result")
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error calling FileSystem RPC method '{method}': {e}")
        return None

# ============================================================================
# SECTION 3: Memory MCP Client (REST-like)
# ============================================================================
def get_memory_tools(endpoint):
    """Retrieves the list of available tools from the Memory server."""
    try:
        response = requests.get(f"{endpoint}/tools", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error getting memory tools: {e}")
        return None

def call_memory_tool(endpoint, tool_name, arguments):
    """Calls a specific tool on the Memory server."""
    payload = {
        "name": tool_name,
        "arguments": arguments
    }
    try:
        response = requests.post(f"{endpoint}/call", json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error calling memory tool '{tool_name}': {e}")
        return None

if __name__ == '__main__':
    servers = load_mcp_servers()
    print("Loaded MCP Servers:")
    print(json.dumps(servers, indent=2))
