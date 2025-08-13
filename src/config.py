# ============================================================================
# FILENAME: config.py
# PURPOSE: Configuration file for Gemini-Agent
# ============================================================================
# SECTION 1: Agent & Server Configuration
# ============================================================================
# Timeout for websocket connections in seconds
#
WEBSOCKET_TIMEOUT = 10

# Delay to wait for servers to start up in seconds
SERVER_STARTUP_DELAY = 5

# Timeout for individual MCP server requests
MCP_SERVER_TIMEOUT = 15

# Configuration for MCP (Modular Control Plane) servers
MCP_SERVERS = [
    {"name": "filesystem"},
    {"name": "memory"}
]
#
# ============================================================================
# SECTION 2: Logging Configuration
# ============================================================================
#
LOG_CONFIG = {
    "handlers": {
        "file": {
            "level": "DEBUG",
            "rotation": "10 MB",
            "retention": "30 days",
        }
    },
    "formatters": {
        "default": {
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        }
    }
}

#
#
## END config.py
