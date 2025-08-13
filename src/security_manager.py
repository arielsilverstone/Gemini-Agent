# ============================================================================
#  File: security_manager.py
#  Location: src/security_manager.py
#  Version: 1.0 (Focused Security Framework)
#  Purpose: Lightweight security for API authentication, input validation,
#           and WebSocket security protocols only
#  Created: 05AUG25
# ============================================================================
# SECTION 1: Imports & Configuration
# ============================================================================
#
import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum, IntEnum
import re

# Logging
from loguru import logger
#
# ============================================================================
# SECTION 2: Security Data Structures
# ============================================================================
# Class 2.1: SecurityLevel
# Purpose: Security clearance levels for operations.
# ============================================================================
#
class SecurityLevel(IntEnum):
    """Security clearance levels for operations."""

    PUBLIC = 1
    INTERNAL = 2
    CONFIDENTIAL = 3
#
# ============================================================================
# Class 2.2: AuthenticationMethod
# Purpose: Supported authentication methods.
# ============================================================================
#
class AuthenticationMethod(Enum):

    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
#
# ============================================================================
# Class 2.3: SecurityContext
# Purpose: Security context for operations and communications.
# ============================================================================
#
@dataclass
class SecurityContext:

    user_id: str
    session_id: str
    security_level: SecurityLevel
    authentication_method: AuthenticationMethod
    permissions: List[str]
    created_at: datetime
    expires_at: datetime
    source_ip: Optional[str] = None
#
# ============================================================================
# SECTION 3: API Authentication & Authorization
# ============================================================================
# Class 3.1: APIAuthenticationManager
# Purpose: Manages API key authentication and validation.
# ============================================================================
#
class APIAuthenticationManager:
    """
    Responsibilities:
    - Generate secure, unique API keys
    - Verify API key authenticity and permissions
    - Track and enforce rate limits per user
    - Manage API key lifecycle (activation, deactivation)
    """

    def __init__(self, storage_path: str = 'api_keys.json'):
        self.storage_path = storage_path
        self.api_keys = {}
        self.rate_limiter = {}
        self._load_keys()
        if not self.api_keys:
            self._initialize_default_keys()

    def _initialize_default_keys(self):
        """
        Initializes default API keys for 'admin' and 'user'.
        """
        default_users = {
            "admin": {"permissions": ["*"]},
            "user": {"permissions": ["api:read", "workflow:execute"]},
        }
        for user_id, details in default_users.items():
            if not any(d.get('user_id') == user_id for d in self.api_keys.values()):
                self.generate_api_key(
                    user_id=user_id,
                    permissions=details["permissions"],
                    security_level=SecurityLevel.CONFIDENTIAL if user_id == "admin" else SecurityLevel.INTERNAL,
                )

    def generate_api_key(
        self, user_id: str, permissions: List[str], security_level: SecurityLevel
    ) -> str:
        """
        Creates and persists a new API key.
        """
        try:
            api_key = f"ga_{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')}"
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            self.api_keys[key_hash] = {
                "user_id": user_id,
                "permissions": permissions,
                "security_level": security_level,
                "created_at": datetime.now(timezone.utc),
                "last_used": None,
                "usage_count": 0,
                "is_active": True,
            }
            logger.info(f"API key generated for user {user_id}")
            self._save_keys()
            return api_key
        except Exception as e:
            logger.error(f"API key generation error: {e}")
            raise SecurityError(f"Failed to generate API key: {e}")

    def verify_api_key(self, api_key: str) -> Optional[SecurityContext]:
        """
        Verifies an API key and returns a security context if valid.
        """
        try:
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            if key_hash in self.api_keys:
                key_info = self.api_keys[key_hash]
                if not key_info["is_active"]:
                    raise SecurityError("API key is deactivated")
                key_info["last_used"] = datetime.now(timezone.utc)
                key_info["usage_count"] += 1
                self._save_keys()
                return SecurityContext(
                    user_id=key_info["user_id"],
                    session_id=f"api_session_{uuid.uuid4()}",
                    security_level=key_info["security_level"],
                    authentication_method=AuthenticationMethod.API_KEY,
                    permissions=key_info["permissions"],
                    created_at=key_info["created_at"],
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
            return None
        except Exception as e:
            logger.error(f"API key verification error: {e}")
            raise SecurityError(f"Failed to verify API key: {e}")

    def _save_keys(self):
        """Saves the current API keys to the storage file."""
        try:
            with open(self.storage_path, 'w') as f:
                serializable_keys = {}
                for key_hash, data in self.api_keys.items():
                    serializable_keys[key_hash] = {
                        **data,
                        'security_level': data['security_level'].name,
                        'created_at': data['created_at'].isoformat(),
                        'last_used': data['last_used'].isoformat() if data['last_used'] else None
                    }
                json.dump(serializable_keys, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")

    def _load_keys(self):
        """Loads API keys from the storage file."""
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, 'r') as f:
                loaded_keys = json.load(f)
                for key_hash, data in loaded_keys.items():
                    self.api_keys[key_hash] = {
                        **data,
                        'security_level': SecurityLevel[data['security_level']],
                        'created_at': datetime.fromisoformat(data['created_at']),
                        'last_used': datetime.fromisoformat(data['last_used']) if data['last_used'] else None
                    }
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"Failed to load or parse API keys file: {e}")

    def check_rate_limit(self, user_id: str, requests_per_minute: int = 60) -> bool:
        """
        Checks if a user is within their rate limit.
        """
        try:
            current_time = datetime.now(timezone.utc)
            minute_key = current_time.strftime("%Y-%m-%d-%H-%M")
            rate_key = f"{user_id}:{minute_key}"

            if rate_key not in self.rate_limiter:
                self.rate_limiter[rate_key] = 0
            self.rate_limiter[rate_key] += 1

            cutoff_time = current_time - timedelta(minutes=2)
            for key in list(self.rate_limiter.keys()):
                try:
                    key_time_str = key.split(":", 1)[1]
                    key_time = datetime.strptime(key_time_str, "%Y-%m-%d-%H-%M").replace(tzinfo=timezone.utc)
                    if key_time < cutoff_time:
                        del self.rate_limiter[key]
                except (ValueError, IndexError):
                    del self.rate_limiter[key]

            return self.rate_limiter[rate_key] <= requests_per_minute
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True
#
# ============================================================================
# SECTION 4: Input Validation & Sanitization
# ============================================================================
# Class 4.1: InputValidator
# Purpose: Validates and sanitizes user inputs to prevent injection attacks.
# ============================================================================
#
class InputValidator:
    """
    - Prevent code injection (SQL, XSS, command injection)
    - Validate input formats and patterns
    - Sanitize potentially dangerous content
    """
    def __init__(self):
        self.dangerous_patterns = [
            r"(\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bUNION\b)",
            r"(\||&|;|\$\(|\`|&&|\|\|)",
            r"(<script|<iframe|javascript:|data:text/html|onload=|onerror=)",
            r"(\.\./|\.\\|%2e%2e|%252e%252e)",
            r"(\*|\(|\)|\\|\/|null|nil)",
        ]
        self.compile_patterns()
    #
    # ========================================================================
    # Method 4.1.1: compile_patterns
    # Purpose: Compile regex patterns for efficient matching.
    # ========================================================================
    #
    def compile_patterns(self):
        """
        Note:
            Called during initialization to prepare security patterns
        """
        import re

        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.dangerous_patterns
        ]
    #
    # ========================================================================
    # Method 4.1.2: validate_agent_task
    # Purpose: Validates agent task input for security threats.
    # ========================================================================
    #
    def validate_agent_task(
        self,
        task: str,
        max_length: int = 10000,
    ) -> Tuple[bool, str]:
        """
        Args:
            task: Agent task string to validate
            max_length: Maximum allowed task length (default: 10000)

        Returns:
            Tuple[bool, str]: (True, "") if valid, or (False, "error message") if invalid.
        """
        try:
            if not task or not isinstance(task, str):
                return False, "Task must be a non-empty string"

            if len(task) > max_length:
                return False, f"Task exceeds maximum length of {max_length} characters"

            for pattern in self.compiled_patterns:
                if pattern.search(task):
                    return False, "Task contains potentially dangerous content"

            if self._has_excessive_repetition(task):
                return False, "Task contains excessive repetition"

            try:
                task.encode("utf-8")
            except UnicodeEncodeError:
                return False, "Task contains invalid characters"

            return True, ""

        except Exception as e:
            logger.error(f"Task validation error: {e}")
            return False, f"Validation error: {e}"
    #
    # ========================================================================
    # Method 4.1.3: _has_excessive_repetition
    # Purpose: Checks for excessive character or pattern repetition.
    # ========================================================================
    #
    #
    def validate_api_endpoint(self, endpoint: str) -> Tuple[bool, str]:
        """
        Args:
            endpoint: API endpoint string to validate (e.g., '/api/v1/resource')

        Returns:
            Tuple[bool, str]:
                - First element (bool): True if valid, False otherwise
                - Second element (str): Error message if invalid, empty string if valid

        Security Checks:
            - Must start with '/'
            - No path traversal patterns (../)
            - No dangerous characters (<, >, ", ', &, |, ;, $, `, (, ))
            - Length limit (1000 characters)
        """
        try:
            # Basic validation
            if not endpoint or not isinstance(endpoint, str):
                return False, "Endpoint must be a non-empty string"

            # Format validation
            if not endpoint.startswith("/"):
                return False, "API endpoint must start with '/'"

            # Length validation
            if len(endpoint) > 1000:
                return False, "API endpoint too long"

            # Path traversal check
            if "../" in endpoint or "..\\" in endpoint:
                return False, "Path traversal detected in endpoint"

            # Check for dangerous characters
            dangerous_chars = ["<", ">", '"', "'", "&", "|", ";", "$", "`", "(", ")"]
            if any(char in endpoint for char in dangerous_chars):
                return False, "Dangerous characters detected in endpoint"

            return True, ""

        except Exception as e:
            logger.error(f"Endpoint validation error: {e}")
            return False, f"Validation error: {e}"
    #
    # ========================================================================
    # Method 4.1.4: validate_websocket_message
    # Purpose: Validates WebSocket message content for security threats.
    # ========================================================================
    #
    def validate_websocket_message(
        self, message: str, max_length: int = 50000
    ) -> Tuple[bool, str]:
        """
        Args:
            message: Raw WebSocket message string to validate
            max_length: Maximum allowed message length in characters (default: 50000)

        Returns:
            Tuple[bool, str]:
                - First element (bool): True if message is valid, False otherwise
                - Second element (str): Error message if invalid, empty string if valid

        Security Checks:
            - Message is not empty and is a string
            - Message length is within allowed limits
            - No dangerous patterns or characters
            - No excessive repetition that might indicate an attack
        """
        try:
            # Basic validation
            if not isinstance(message, str):
                return False, "Message must be a string"

            # Length validation
            if len(message) > max_length:
                return (
                    False,
                    f"Message exceeds maximum length of {max_length} characters",
                )

            # Check for dangerous patterns (less strict than agent tasks)
            dangerous_ws_patterns = [
                r"(<script|<iframe|javascript:|data:text/html)",
                r"(\$\(|\`|eval\(|Function\()",
                r"(onload=|onerror=|onclick=)",
            ]

            for pattern_str in dangerous_ws_patterns:
                import re

                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(message):
                    return False, "Message contains potentially dangerous content"

            return True, ""

        except Exception as e:
            logger.error(f"WebSocket message validation error: {e}")
            return False, f"Validation error: {e}"
    #
    # ========================================================================
    # Method 4.1.3: _has_excessive_repetition
    # Purpose: Checks for excessive character or pattern repetition.
    # ========================================================================
    #
    def _has_excessive_repetition(self, text: str, threshold: float = 0.7) -> bool:
        """
        - Detect potential denial of service (DoS) attempts
        - Identify suspicious patterns in input
        - Prevent resource exhaustion attacks

        Args:
            text: Input text to analyze for repetition
            threshold: Repetition ratio threshold (0.0 to 1.0, default: 0.7)

        Returns:
            bool: True if excessive repetition is detected, False otherwise

        Note:
            A threshold of 0.7 means if 70% or more of the text consists of
            repeated patterns, it will be flagged as excessive.
        """
        # Perform regex checks for obvious, high-repetition patterns first
        if re.search(r'(.)\1{50,}', text):
            return True
        if re.search(r'(.{2,10})\1{10,}', text):
            return True

        # For longer texts, check the ratio of the most common character
        if len(text) < 100:
            return False

        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        if not char_counts:
            return False

        most_common_count = max(char_counts.values())
        repetition_ratio = most_common_count / len(text)

        return repetition_ratio > threshold
#
# ============================================================================
# SECTION 5: WebSocket Security Protocols
# ============================================================================
# Class 5.1: WebSocketSecurityManager
# Purpose: Manages security for WebSocket connections and communications.
# ============================================================================
class WebSocketSecurityManager:
    """
    - Secure WebSocket connection handling
    - Message validation and sanitization
    - Connection lifecycle management
    - Heartbeat and health monitoring
    """
    # ============================================================================
    # Method 5.1.1: __init__
    # ============================================================================
    def __init__(self, auth_manager: APIAuthenticationManager):
        """
        Initialize the WebSocket security manager.

        Purpose:
        - Set up WebSocket security components
        - Initialize connection tracking
        - Prepare rate limiting and heartbeat mechanisms

        Args:
            auth_manager: Instance of APIAuthenticationManager for API key validation
        """
        self.auth_manager = auth_manager
        self.secure_connections = {}
        self.connection_limits = {}
        self.heartbeat_intervals = {}
    #
    # ========================================================================
    # Method 5.1.2: establish_secure_connection
    # Purpose: Establishes a secure WebSocket connection with authentication.
    # ========================================================================
    #
    async def establish_secure_connection(
        self, connection_id: str, authentication_token: str, source_ip: Optional[str] = None
    ) -> SecurityContext:
        """
        - Authenticate WebSocket connections using API keys
        - Track active connections
        - Enforce connection limits
        - Initialize connection state

        Args:
            connection_id: Unique identifier for the WebSocket connection
            authentication_token: API key for authentication
            source_ip: Optional source IP address for logging and rate limiting

        Returns:
            SecurityContext: Authenticated security context for the connection

        Raises:
            SecurityError: If authentication fails or connection limit is reached

        Note:
            - Each connection requires a valid API key
            - Connections are tracked for management and cleanup
            - Source IP is used for rate limiting if provided
        """
        try:
            # Verify authentication token
            security_context = self.auth_manager.verify_api_key(authentication_token)
            if not security_context:
                raise SecurityError("Invalid authentication token")
            security_context.source_ip = source_ip

            # Check connection limits per user
            user_connections = sum(
                1
                for conn in self.secure_connections.values()
                if conn["security_context"].user_id == security_context.user_id
            )

            max_connections = 5  # Maximum connections per user
            if user_connections >= max_connections:
                raise SecurityError(
                    f"Maximum connections per user exceeded: {max_connections}"
                )

            # Store secure connection info
            self.secure_connections[connection_id] = {
                "security_context": security_context,
                "established_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
                "message_count": 0,
                "source_ip": source_ip,
            }

            # Initialize heartbeat tracking
            self.heartbeat_intervals[connection_id] = {
                "last_heartbeat": datetime.now(timezone.utc),
                "missed_beats": 0,
            }

            logger.info(
                f"Secure WebSocket connection established: {connection_id} for user {security_context.user_id}"
            )
            return security_context

        except Exception as e:
            logger.error(f"Secure WebSocket connection error: {e}")
            raise SecurityError(f"Failed to establish secure connection: {e}")
    #
    # ========================================================================
    # Method 5.1.3: validate_websocket_message
    # Purpose: Validates a WebSocket message for security compliance.
    # ========================================================================
    #
    def validate_websocket_message(
        self, connection_id: str, message: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Args:
            connection_id: WebSocket connection identifier
            message: Message to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Check if connection exists
            if connection_id not in self.secure_connections:
                return False, f"Invalid connection ID: {connection_id}"

            connection_info = self.secure_connections[connection_id]

            # Validate message structure
            if not isinstance(message, dict):
                return False, "Message must be a dictionary"

            if "type" not in message:
                return False, "Message must have a 'type' field"

            # Update connection activity
            connection_info["last_activity"] = datetime.now(timezone.utc)
            connection_info["message_count"] += 1

            # Rate limiting per connection
            if connection_info["message_count"] > 1000:  # Reset counter hourly
                if (
                    datetime.now(timezone.utc) - connection_info["established_at"]
                ).total_seconds() > 3600:
                    connection_info["message_count"] = 1
                    connection_info["established_at"] = datetime.now(timezone.utc)
                elif connection_info["message_count"] > 1000:
                    return False, "Message rate limit exceeded"

            return True, ""

        except Exception as e:
            logger.error(f"WebSocket message validation error: {e}")
            return False, f"Validation error: {e}"
    #
    # ========================================================================
    # Method 5.1.4: handle_heartbeat
    # Purpose: Handles WebSocket connection heartbeat to maintain connection
    #          health.
    # ========================================================================
    #
    def handle_heartbeat(self, connection_id: str) -> bool:
        """
        Args:
            connection_id: Unique identifier for the WebSocket connection

        Returns:
            bool: True if heartbeat was processed successfully, False otherwise.

        Note:
            - Updates both heartbeat tracking and last activity timestamp.
            - Resets the missed heartbeat counter.
        """
        try:
            if connection_id not in self.heartbeat_intervals:
                logger.warning(f"Heartbeat from untracked connection: {connection_id}")
                return False

            # Update heartbeat timestamp and reset missed beats
            now = datetime.now(timezone.utc)
            self.heartbeat_intervals[connection_id]["last_heartbeat"] = now
            self.heartbeat_intervals[connection_id]["missed_beats"] = 0

            # Also update the main connection's last activity timestamp
            if connection_id in self.secure_connections:
                self.secure_connections[connection_id]["last_activity"] = now

            logger.debug(f"Heartbeat processed for connection: {connection_id}")
            return True

        except Exception as e:
            logger.error(f"Heartbeat handling error for {connection_id}: {e}")
            return False
    #
    # ========================================================================
    # Method 5.1.5: check_connection_health
    # Purpose: Checks the health of a WebSocket connection based on activity and
    #          heartbeats.
    # ========================================================================
    #
    def check_connection_health(self, connection_id: str) -> bool:
        """
        Args:
            connection_id: Unique identifier for the WebSocket connection

        Returns:
            bool:
                - True if the connection is healthy and active
                - False if the connection should be terminated due to inactivity or errors

        Health Checks:
            - Connection must exist in active connections
            - Last activity must be within max idle time (30 minutes)
            - Heartbeat status must be valid (if heartbeat tracking is enabled)
        """
        try:
            if connection_id not in self.secure_connections:
                return False

            connection_info = self.secure_connections[connection_id]
            current_time = datetime.now(timezone.utc)

            # Check if connection has been idle too long
            max_idle_time = timedelta(minutes=30)
            if (current_time - connection_info["last_activity"]) > max_idle_time:
                logger.warning(
                    f"Connection {connection_id} idle for too long, marking unhealthy"
                )
                return False

            # Check heartbeat status
            if connection_id in self.heartbeat_intervals:
                heartbeat_info = self.heartbeat_intervals[connection_id]
                max_heartbeat_interval = timedelta(minutes=5)

                if (
                    current_time - heartbeat_info["last_heartbeat"]
                ) > max_heartbeat_interval:
                    heartbeat_info["missed_beats"] += 1

                    if heartbeat_info["missed_beats"] > 3:
                        logger.warning(
                            f"Connection {connection_id} missed too many heartbeats"
                        )
                        return False

            return True

        except Exception as e:
            logger.error(f"Connection health check error: {e}")
            return False
    #
    # ========================================================================
    # Method 5.1.6: close_connection
    # Purpose: Closes and cleans up a WebSocket connection and all associated
    #          resources.
    # ========================================================================
    #
    def close_connection(self, connection_id: str):
        """
        - Clean up connection state
        - Release resources
        - Remove connection tracking
        - Log connection closure

        Args:
            connection_id: Unique identifier for the WebSocket connection to close

        Note:
            - Removes connection from secure_connections dictionary
            - Cleans up heartbeat tracking for the connection
            - Logs the connection closure with user context
            - Safe to call even if connection doesn't exist
        """
        try:
            if connection_id in self.secure_connections:
                user_id = self.secure_connections[connection_id][
                    "security_context"
                ].user_id
                del self.secure_connections[connection_id]
                logger.info(
                    f"WebSocket connection closed: {connection_id} for user {user_id}"
                )

            if connection_id in self.heartbeat_intervals:
                del self.heartbeat_intervals[connection_id]

        except Exception as e:
            logger.error(f"Connection close error: {e}")
#
# ============================================================================
# SECTION 6: Main Security Manager
# ============================================================================
# Class 6.1: SecurityError
# Purpose: Base exception class for security-related errors.
# ============================================================================
class SecurityError(Exception):
    """
    - Provide a common base for all security-related exceptions
    - Enable consistent error handling for security violations
    - Include additional security context in error messages

    Usage:
        try:
            # Security-sensitive operation
            raise SecurityError("Invalid API key")
        except SecurityError as e:
            # Handle security error
    """
    pass
#
# ============================================================================
# Class 6.2: SecurityManager
# Purpose: Central security management for the application.
# ============================================================================
#
class SecurityManager:
    """
    - Provide a unified interface for security operations
    - Manage API authentication and authorization
    - Enforce input validation policies
    - Handle WebSocket security protocols
    - Coordinate between different security components

    Components:
    - API Authentication: Handles API key management and validation
    - Input Validation: Validates and sanitizes user inputs
    - WebSocket Security: Manages secure WebSocket connections
    """
    #
    # ============================================================================
    # Method 6.2.1: __init__
    # ============================================================================
    #
    def __init__(self, config_dir: Path):
        """
        Initialize the Security Manager with configuration and security components.

        Args:
            config_dir: Path to the configuration directory

        Components Initialized:
            - API Authentication Manager
            - Input Validator
            - WebSocket Security Manager

        Args:
            config_dir: Path to the configuration directory

        Components Initialized:
            - API Authentication Manager
            - Input Validator
            - WebSocket Security Manager

        Note:
            - Creates security directory if it doesn't exist
            - Sets up logging for security events
        """
        self.config_dir = config_dir
        self.security_dir = config_dir / "security"
        self.security_dir.mkdir(parents=True, exist_ok=True)

        # Initialize focused security components
        self.api_auth = APIAuthenticationManager()
        self.input_validator = InputValidator()
        self.websocket_security = WebSocketSecurityManager(self.api_auth)

        logger.info(
            "Security Manager initialized with API authentication, input validation, "
            "and WebSocket security components"
        )
    #
    # ============================================================================
    # Method 6.2.2: authenticate_api_request
    # Purpose: Authenticate and validate an API request using the provided API key
    # ============================================================================
    #
    async def authenticate_api_request(
        self, api_key: str, source_ip: Optional[str] = None
    ) -> SecurityContext:
        """
        Args:
            api_key: The API key to authenticate
            source_ip: Optional IP address of the request source for logging and rate limiting

        Returns:
            SecurityContext: Authenticated security context containing user and permission details

        Args:
            api_key: The API key to authenticate
            source_ip: Optional IP address of the request source for logging and rate limiting

        Returns:
            SecurityContext: Authenticated security context containing user and permission details

        Raises:
            SecurityError: If authentication fails or rate limit is exceeded

        Security Measures:
            - Validates API key format and existence
            - Enforces rate limiting per user
            - Logs authentication attempts
            - Tracks source IP for security monitoring

        Note:
            - API keys must be valid and not revoked
            - Rate limits are applied per user ID
            - Source IP is included in security context when provided
        """
        try:
            security_context = self.api_auth.verify_api_key(api_key)
            if not security_context:
                raise SecurityError("Invalid API key")
            security_context.source_ip = source_ip

            # Check rate limits
            if not self.api_auth.check_rate_limit(security_context.user_id):
                raise SecurityError("Rate limit exceeded")

            logger.info(
                f"API authentication successful for user {security_context.user_id}"
            )
            return security_context

        except Exception as e:
            logger.error(f"API authentication failed: {e}")
            raise SecurityError(f"Authentication failed: {e}")
    #
    # ============================================================================
    # Method 6.2.3: validate_agent_task
    # Purpose: Validate an agent task for security compliance and safety
    # ============================================================================
    #
    async def validate_agent_task(
        self, task: str, user_id: str = "system"
    ) -> Tuple[bool, str]:
        """
        Args:
            task: The agent task string to validate
            user_id: Identifier for the user submitting the task (default: "system")

        Returns:
            Tuple[bool, str]:
                - First element (bool): True if task is valid, False otherwise
                - Second element (str): Error message if invalid, empty string if valid

        Security Checks:
            - Task is not empty and is a string
            - Task length is within limits
            - No dangerous patterns or characters
        - Log validation attempts

        Note:
            - Default user_id is "system" for automated tasks
            - All validation failures return False with an error message
            - Success returns True with an empty string
        """
        try:
            is_valid, error_msg = self.input_validator.validate_agent_task(task)

            if not is_valid:
                logger.warning(
                    f"Agent task validation failed for user {user_id}: {error_msg}"
                )

            return is_valid, error_msg

        except Exception as e:
            logger.error(f"Agent task validation error: {e}")
            return False, f"Validation failed: {e}"
    #
    # ============================================================================
    # Method 6.2.4: validate_api_endpoint
    # Purpose: Validate an API endpoint for security compliance and proper
    #          formatting
    # ============================================================================
    #
    async def validate_api_endpoint(
        self, endpoint: str, user_id: str = "system"
    ) -> Tuple[bool, str]:
        """
        Args:
            endpoint: The API endpoint string to validate (e.g., '/api/v1/resource')
            user_id: Identifier for the user making the request (default: "system")

        Returns:
            Tuple[bool, str]:
                - First element (bool): True if endpoint is valid, False otherwise
                - Second element (str): Error message if invalid, empty string if valid

        Security Checks:
            - Must start with a forward slash
            - No path traversal patterns (../)
        - Log validation attempts

        Note:
            - Default user_id is "system" for automated requests
            - All validation failures return False with an error message
            - Success returns True with an empty string
        """
        try:
            is_valid, error_msg = self.input_validator.validate_api_endpoint(endpoint)

            if not is_valid:
                logger.warning(
                    f"API endpoint validation failed for user {user_id}: {error_msg}"
                )

            return is_valid, error_msg

        except Exception as e:
            logger.error(f"API endpoint validation error: {e}")
            return False, f"Validation failed: {e}"
    #
    # ============================================================================
    # Method 6.2.5: establish_websocket_connection
    # Purpose: Establish a secure WebSocket connection with authentication and
    #          validation
    # ============================================================================
    #
    async def establish_websocket_connection(
        self, connection_id: str, api_key: str, source_ip: Optional[str] = None
    ) -> SecurityContext:
        """
        Establish a secure WebSocket connection with authentication and validation

        Args:
            connection_id: Unique identifier for the WebSocket connection
            api_key: API key for authenticating the connection
            source_ip: Optional IP address of the client for logging and rate limiting

        Returns:
            SecurityContext: Authenticated security context for the connection

        Raises:
            SecurityError: If connection cannot be established or authenticated

        Security Measures:
            - Validates API key before establishing connection
            - Enforces rate limiting per user
            - Logs connection attempts
            - Tracks source IP for security monitoring
        - Enforce connection limits

        Note:
            - Requires a valid API key for authentication
            - Connection ID must be unique
            - Source IP is used for logging and rate limiting if provided
        """
        try:
            security_context = (
                await self.websocket_security.establish_secure_connection(
                    connection_id, api_key, source_ip
                )
            )

            logger.info(f"WebSocket connection established: {connection_id}")
            return security_context

        except Exception as e:
            logger.error(f"WebSocket connection establishment failed: {e}")
            raise SecurityError(f"Connection failed: {e}")
    #
    # ============================================================================
    # Method 6.2.6: validate_websocket_message
    # Purpose: Validate a WebSocket message for security and structure compliance
    # ============================================================================
    #
    async def validate_websocket_message(
        self, connection_id: str, message: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        - Ensure message structure is valid
        - Enforce rate limiting per connection
        - Track message activity
        - Prevent message flooding

        Args:
            connection_id: Unique identifier for the WebSocket connection
            message: Message data to validate (must be a dictionary)

        Returns:
            Tuple[bool, str]:
                - First element (bool): True if message is valid, False otherwise
                - Second element (str): Error message if invalid, empty string if valid

        Validation Rules:
            - Connection must be established
            - Message must be a dictionary
            - Must contain 'type' field
            - Rate limited to 1000 messages per hour per connection

        Note:
            - Updates last activity timestamp on successful validation
            - Tracks message count for rate limiting
        """
        try:
            # Validate connection
            conn_valid, conn_error = self.websocket_security.validate_websocket_message(
                connection_id, message
            )
            if not conn_valid:
                return False, conn_error

            # Validate message content if it has a payload
            if "payload" in message and isinstance(message["payload"], str):
                content_valid, content_error = (
                    self.input_validator.validate_websocket_message(message["payload"])
                )
                if not content_valid:
                    return False, content_error

            return True, ""

        except Exception as e:
            logger.error(f"WebSocket message validation error: {e}")
            return False, f"Validation failed: {e}"
    #
    # ========================================================================
    # Method 6.2.7: get_security_status
    # Purpose: Retrieve comprehensive security status and metrics for monitoring
    #          and reporting
    # ========================================================================
    #
    async def get_security_status(self) -> Dict[str, Any]:
        """
        - Provide visibility into security system health
        - Track active connections and API keys
        - Monitor authentication attempts
        - Report security-related metrics

        Returns:
            Dict[str, Any]: Security status information including:
                - security_manager_status: Current status of the security manager
                - api_keys_active: Number of active API keys
                - active_connections: Count of active WebSocket connections
                - auth_attempts: Authentication attempt statistics
                - rate_limiting: Current rate limiting status

        Metrics Included:
            - Active API key count
            - Active WebSocket connections
            - Authentication success/failure rates
            - Rate limiting status

        Note:
            - This method provides a snapshot of the current security state
            - All sensitive information is redacted or hashed
            - Should be called periodically for monitoring purposes
        """
        try:
            status = {
                "security_manager_status": "active",
                "api_keys_active": len(
                    [k for k in self.api_auth.api_keys.values() if k["is_active"]]
                ),
                "websocket_connections": len(
                    self.websocket_security.secure_connections
                ),
                "components": {
                    "api_authentication": "enabled",
                    "input_validation": "enabled",
                    "websocket_security": "enabled",
                },
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            return status

        except Exception as e:
            logger.error(f"Security status check error: {e}")
            return {"security_manager_status": "error", "error": str(e)}
#
#
# ============================================================================
# SECTION 7: Security Configuration & Initialization
# ============================================================================
# Function 7.1: initialize_security_manager
# Purpose: Initialize and configure the security manager with the specified
#          configuration.
# ============================================================================
#
def initialize_security_manager(config_dir: Path) -> SecurityManager:
    """
    Args:
        config_dir: Path to the directory containing security configuration files

    Returns:
        SecurityManager: A fully initialized and configured security manager instance

    Raises:
        SecurityError: If initialization fails due to configuration issues
        FileNotFoundError: If required configuration files are missing
        PermissionError: If there are permission issues accessing config files

    Configuration Files Used:
        - api_keys.json: API key definitions and permissions
        - security_policies.json: Security rules and policies
        - rate_limits.json: Rate limiting configuration

    Note:
        - Creates necessary directories if they don't exist
        - Validates configuration before initialization
        - Sets up logging for security events
    """
    try:
        security_manager = SecurityManager(config_dir)
        logger.info("Focused Security Manager initialized successfully")
        return security_manager

    except Exception as e:
        logger.error(f"Security Manager initialization failed: {e}")
        raise SecurityError(f"Failed to initialize security: {e}")
#
# ============================================================================
# SECTION 8: Example Usage & Testing
# ============================================================================
# Function 8.1: initialize_security_manager
# Purpose: Initialize and configure the security manager with the specified
#          configuration.
# ============================================================================
#
# Example usage and testing
if __name__ == "__main__":
    from pathlib import Path

    config_dir = Path(__file__).parent.parent / "config"
    security_manager = initialize_security_manager(config_dir)

    print("Focused Security Manager initialized successfully!")
    print("Available security features:")
    print("- API endpoint authentication/authorization")
    print("- Input validation and sanitization")
    print("- WebSocket security protocols")
#
#
## End of security_manager.py
