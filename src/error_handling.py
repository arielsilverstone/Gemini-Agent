# ============================================================================
#  File:    error_handling.py
#  Purpose: Agent error codes, standardized messages, and self-correction
# ============================================================================
# SECTION 1: Imports and Globals
# ============================================================================
#
from loguru import logger
from typing import Any, Dict, Optional, AsyncIterator, TYPE_CHECKING, List, Union
import asyncio
import threading
import time
from dataclasses import dataclass
from datetime import datetime
import websockets
from functools import wraps

if TYPE_CHECKING:
    from agents.agent_base import AgentBase
    from agents.fix_agent import FixAgent

from src.config_manager import ConfigManager, AsyncConfigManager
#
# ============================================================================
# SECTION 2: Error Codes and Messages
# ============================================================================
ERROR_CODES = {
    'E001': 'Invalid input',
    'E002': 'Config validation failed',
    'E003': 'LLM call failed or timed out',
    'E004': 'File operation error',
    'E005': 'Agent self-correction attempt failed',
    'E999': 'Unknown error'
}
#
# ============================================================================
# SECTION 3: Error Handling Utilities
# ============================================================================
# Async Function 3.1: connect_to_windsurf
# Purpose: Connects to the Windsurf server.
# ============================================================================
#
async def connect_to_windsurf(port):

    uri = f"ws://127.0.0.1:{port}/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connection established.")
            return websocket
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
#
# ============================================================================
# Function 3.2: get_error_message
# Purpose: Formats a standardized error message from an error code.
# ============================================================================
#
def get_error_message(code, detail=None):
    """Formats a standardized error message from an error code."""
    message = ERROR_CODES.get(code, ERROR_CODES['E999'])
    if detail:
        return f"[{code}] {message}: {str(detail)}"
    return f"[{code}] {message}"
#
# ============================================================================
# SECTION 4: Agent Self-Correction Logic
# ============================================================================
# Async Function 4.1: agent_self_correct
# Purpose: Handles agent errors by initiating a self-correction workflow.
# ============================================================================
#
async def agent_self_correct(
    agent: 'AgentBase',
    original_task: str,
    current_context: Dict[str, Any],
    error_details: str,
    error_type: str,
    correction_guidance: str
) -> AsyncIterator[str]:

    try:
        log_message = f"Initiating self-correction for {agent.name} due to {error_type}. Error: {error_details}"
        logger.info(log_message)
        yield f"STREAM_CHUNK:{agent.name}:[INFO] {log_message}\n"

        # Construct a detailed task for the FixAgent
        fix_task = (
            f"The '{agent.name}' agent failed on the task: '{original_task}'.\n"
            f"Error Type: {error_type}\n"
            f"Error Details: {error_details}\n"
            f"Original Context: {current_context}\n"
        )
        if correction_guidance:
            fix_task += f"Correction Guidance: {correction_guidance}\n"
        fix_task += "Please analyze the error and provide a corrected response or solution."

        # Import FixAgent locally to avoid circular import
        from agents.fix_agent import FixAgent

        # Instantiate and run the FixAgent, passing necessary components
        fix_agent = FixAgent(
            name=agent.name,
            config=agent.config,
            websocket_manager=agent.websocket_manager,
            rule_engine=agent.rule_engine,
            config_manager=agent.config_manager
        )

        # Stream the fix agent's response back
        async for chunk in fix_agent.run(task=fix_task, context=current_context):
            yield chunk

        yield f"STREAM_CHUNK:{agent.name}:[INFO] Self-correction attempt for {agent.name} completed.\n"

    except Exception as e:
        error_message = f"A critical error occurred during the self-correction process: {e}"
        logger.error(error_message, exc_info=True)
        yield f"STREAM_CHUNK:{agent.name}:[ERROR] {error_message}\n"
#
# ============================================================================
# Function 4.2: orchestrator_recover
# Purpose: Attempts orchestrator recovery after a critical failure.
# ============================================================================
#
def orchestrator_recover(orchestrator, last_task=None):
    try:
        orchestrator.reload_config()
        if last_task:
            return orchestrator.handle_ipc(**last_task)
        return True
    except Exception as e:
        return get_error_message('E999', f"Orchestrator recovery failed: {str(e)}")

# Section 5: Async Singleton Base
# Purpose: Thread-safe async singleton pattern with streaming support

class AsyncSingletonBase:
    """
    Base class for thread-safe singleton pattern with async initialization.
    
    Features:
    - Thread-safe singleton instantiation
    - Async initialization support
    - Streaming capabilities
    - Error handling integration
    - Type-safe configuration
    """
    
    _instance = None
    _lock = threading.Lock()
    _async_lock = asyncio.Lock()
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    async def async_init(self, *args, **kwargs):
        """Async initialization method to be overridden by subclasses."""
        pass
    
    @classmethod
    async def get_instance_async(cls, *args, **kwargs):
        """
        Get singleton instance with async initialization.
        
        Args:
            *args: Positional arguments for async initialization
            **kwargs: Keyword arguments for async initialization
            
        Returns:
            Singleton instance
        """
        if cls._instance is None:
            async with cls._async_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.async_init(*args, **kwargs)
                    cls._initialized = True
        elif not cls._initialized:
            async with cls._async_lock:
                if not cls._initialized:
                    await cls._instance.async_init(*args, **kwargs)
                    cls._initialized = True
        
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance (synchronous)."""
        if cls._instance is None:
            raise RuntimeError("Instance not initialized. Use get_instance_async() first.")
        return cls._instance

class StreamingSingleton(AsyncSingletonBase):
    """
    Streaming singleton with async capabilities and real-time updates.
    
    Features:
    - Real-time streaming of singleton state
    - Async configuration updates
    - Thread-safe state management
    - Error handling with context
    """
    
    def __init__(self):
        super().__init__()
        self._state = {}
        self._observers = []
        self._state_lock = asyncio.Lock()
    
    async def async_init(self, *args, **kwargs):
        """Initialize streaming singleton with async setup."""
        await self._setup_streaming_state()
    
    async def _setup_streaming_state(self):
        """Setup initial streaming state."""
        self._state = {
            'initialized': True,
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }
    
    async def stream_state_updates(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream real-time state updates.
        
        Yields:
            Dict containing current state
        """
        while True:
            async with self._state_lock:
                current_state = self._state.copy()
            
            yield {
                'state': current_state,
                'timestamp': datetime.now().isoformat(),
                'type': 'state_update'
            }
            
            await asyncio.sleep(1)  # Prevent tight loop
    
    async def update_state(self, new_state: Dict[str, Any]):
        """Update singleton state with thread safety."""
        async with self._state_lock:
            self._state.update(new_state)
            self._state['last_update'] = datetime.now().isoformat()

@dataclass
class ErrorContext:
    """Context information for error handling."""
    error_type: str
    error_message: str
    timestamp: datetime
    stack_trace: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None
    severity: str = "error"
    resolution_hint: Optional[str] = None

class AsyncApplicationError(Exception):
    """
    Async application error with streaming support.
    
    Features:
    - Rich error context
    - Streaming error reporting
    - Thread-safe error aggregation
    - Resolution hints
    """
    
    def __init__(self, message: str, error_type: str = "E999", context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.context = context or {}
        self.timestamp = datetime.now()
        
    def to_error_context(self) -> ErrorContext:
        """Convert to error context for streaming."""
        return ErrorContext(
            error_type=self.error_type,
            error_message=str(self),
            timestamp=self.timestamp,
            context_data=self.context,
            severity="error",
            resolution_hint=ERROR_CODES.get(self.error_type, "Unknown error")
        )

class StreamingErrorHandler(StreamingSingleton):
    """
    Singleton error handler with streaming capabilities.
    
    Features:
    - Real-time error streaming
    - Thread-safe error aggregation
    - Context-rich error reporting
    - Resolution hints
    """
    
    def __init__(self):
        super().__init__()
        self._error_queue = asyncio.Queue()
        self._error_cache = []
        self._cache_lock = asyncio.Lock()
        self._max_cache_size = 1000
    
    async def _setup_streaming_state(self):
        """Setup error handler state."""
        await super()._setup_streaming_state()
        self._state.update({
            'total_errors': 0,
            'last_error': None,
            'error_rate': 0.0
        })
    
    async def handle_error_async(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """
        Handle error with async processing and context enrichment.
        
        Args:
            error: Exception to handle
            context: Additional context information
            
        Returns:
            ErrorContext with enriched information
        """
        if error is None:
            error = AsyncApplicationError("Unknown error")
        
        error_context = ErrorContext(
            error_type=getattr(error, 'error_type', 'E999'),
            error_message=str(error),
            timestamp=datetime.now(),
            context_data=context or {},
            severity="error"
        )
        
        # Add to queue for streaming
        await self._error_queue.put(error_context)
        
        # Update cache
        async with self._cache_lock:
            self._error_cache.append(error_context)
            if len(self._error_cache) > self._max_cache_size:
                self._error_cache.pop(0)
            
            # Update state
            await self.update_state({
                'total_errors': len(self._error_cache),
                'last_error': error_context.error_message,
                'last_error_time': error_context.timestamp.isoformat()
            })
        
        return error_context
    
    async def stream_errors(self) -> AsyncIterator[ErrorContext]:
        """
        Stream errors in real-time.
        
        Yields:
            ErrorContext objects as errors occur
        """
        while True:
            try:
                # Wait for new errors
                error_context = await asyncio.wait_for(self._error_queue.get(), timeout=1.0)
                yield error_context
            except asyncio.TimeoutError:
                # Yield heartbeat every second
                yield ErrorContext(
                    error_type="HEARTBEAT",
                    error_message="System heartbeat",
                    timestamp=datetime.now(),
                    severity="info"
                )
    
    async def get_recent_errors(self, limit: int = 10) -> List[ErrorContext]:
        """Get recent errors from cache."""
        async with self._cache_lock:
            return self._error_cache[-limit:] if self._error_cache else []
    
    async def clear_errors(self):
        """Clear error cache."""
        async with self._cache_lock:
            self._error_cache.clear()
            await self.update_state({
                'total_errors': 0,
                'last_error': None
            })

class AsyncErrorDecorator:
    """
    Decorator for async error handling with streaming support.
    
    Features:
    - Automatic error handling
    - Context enrichment
    - Retry mechanisms
    - Performance tracking
    """
    
    def __init__(self, max_retries: int = 3, error_handler: Optional[StreamingErrorHandler] = None):
        self.max_retries = max_retries
        self.error_handler = error_handler or StreamingErrorHandler()
    
    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    
                    # Log successful execution
                    execution_time = time.time() - start_time
                    logger.info(f"Function {func.__name__} executed successfully in {execution_time:.3f}s")
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    context = {
                        'function': func.__name__,
                        'attempt': attempt + 1,
                        'max_retries': self.max_retries,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }
                    
                    # Handle error with streaming
                    error_context = await self.error_handler.handle_error_async(e, context)
                    
                    if attempt == self.max_retries - 1:
                        raise AsyncApplicationError(
                            f"Max retries ({self.max_retries}) exceeded for {func.__name__}: {str(e)}",
                            context=context
                        ) from e
                    
                    # Wait before retry with exponential backoff
                    await asyncio.sleep(2 ** attempt)
            
            raise last_error or Exception("Unknown error occurred after max retries")
        
        return wrapper

class StreamingUnifiedLogger(StreamingSingleton):
    """
    Unified logging with streaming capabilities.
    
    Features:
    - Real-time log streaming
    - Thread-safe log aggregation
    - Multiple log levels
    - Context enrichment
    """
    
    def __init__(self):
        super().__init__()
        self._log_queue = asyncio.Queue()
        self._log_cache = []
        self._cache_lock = asyncio.Lock()
        self._max_cache_size = 1000
    
    async def _setup_streaming_state(self):
        """Setup logger state."""
        await super()._setup_streaming_state()
        self._state.update({
            'total_logs': 0,
            'last_log': None,
            'log_levels': {
                'debug': 0,
                'info': 0,
                'warning': 0,
                'error': 0,
                'critical': 0
            }
        })
    
    async def log_operation_async(self, operation: str, message: str, level: str = "info", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Log operation with async processing and context.
        
        Args:
            operation: Operation name
            message: Log message
            level: Log level (debug, info, warning, error, critical)
            context: Additional context
            
        Returns:
            Log entry with metadata
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'message': message,
            'level': level,
            'context': context or {},
            'thread_id': threading.current_thread().ident
        }
        
        # Add to queue for streaming
        await self._log_queue.put(log_entry)
        
        # Update cache
        async with self._cache_lock:
            self._log_cache.append(log_entry)
            if len(self._log_cache) > self._max_cache_size:
                self._log_cache.pop(0)
            
            # Update state
            level_counts = self._state.get('log_levels', {})
            level_counts[level] = level_counts.get(level, 0) + 1
            
            await self.update_state({
                'total_logs': len(self._log_cache),
                'last_log': log_entry,
                'log_levels': level_counts
            })
        
        # Log to file/console
        logger.log(level.upper(), f"{operation}: {message}")
        
        return log_entry
    
    async def stream_logs(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream logs in real-time.
        
        Yields:
            Log entries as they occur
        """
        while True:
            try:
                log_entry = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                yield log_entry
            except asyncio.TimeoutError:
                # Yield heartbeat
                yield {
                    'timestamp': datetime.now().isoformat(),
                    'type': 'heartbeat',
                    'message': 'Logger heartbeat'
                }
    
    async def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent logs from cache."""
        async with self._cache_lock:
            return self._log_cache[-limit:] if self._log_cache else []

class AsyncErrorMessageSystem(StreamingSingleton):
    """
    Unified async error message system with streaming support.
    
    Features:
    - Real-time error message streaming
    - Thread-safe error aggregation
    - Template-based error formatting
    - Context enrichment
    """
    
    def __init__(self):
        super().__init__()
        self._error_templates = {
            'E001': 'Invalid input: {details}',
            'E002': 'Configuration validation failed: {details}',
            'E003': 'LLM call failed or timed out: {details}',
            'E004': 'File operation error: {details}',
            'E005': 'Agent self-correction attempt failed: {details}',
            'E999': 'Unknown error: {details}'
        }
        self._error_cache = []
        self._cache_lock = asyncio.Lock()
    
    async def _setup_streaming_state(self):
        """Setup error message system state."""
        await super()._setup_streaming_state()
        self._state.update({
            'total_messages': 0,
            'message_templates': len(self._error_templates),
            'last_message': None
        })
    
    async def format_error_streaming(self, error_type: str, context: Dict[str, Any]) -> AsyncIterator[str]:
        """
        Format error messages with streaming support.
        
        Args:
            error_type: Error type code
            context: Error context
            
        Yields:
            Formatted error messages
        """
        template = self._error_templates.get(error_type, self._error_templates['E999'])
        
        # Stream formatted message
        formatted_message = template.format(**context)
        yield formatted_message
        
        # Stream context details
        if context.get('details'):
            yield f"Details: {context['details']}"
        
        # Stream resolution hints
        if context.get('resolution_hint'):
            yield f"Resolution: {context['resolution_hint']}"
    
    async def process_error_streaming(self, error_data: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Process error data with streaming output.
        
        Args:
            error_data: Raw error data
            
        Yields:
            Processed error information
        """
        error_type = error_data.get('error_type', 'E999')
        context = error_data.get('context', {})
        
        # Format error message
        async for message in self.format_error_streaming(error_type, context):
            error_info = {
                'error_type': error_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'severity': error_data.get('severity', 'error'),
                'context': context
            }
            
            # Cache error
            async with self._cache_lock:
                self._error_cache.append(error_info)
                if len(self._error_cache) > 1000:
                    self._error_cache.pop(0)
                
                # Update state
                await self.update_state({
                    'total_messages': len(self._error_cache),
                    'last_message': error_info
                })
            
            yield error_info

## End Script
