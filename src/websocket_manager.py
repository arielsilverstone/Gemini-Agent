# ============================================================================
#  File: websocket_manager.py
#  Purpose: WebSocket connection and streaming message manager for backend
#  Created: 29JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================

import asyncio
from fastapi import WebSocket
from typing import List
from loguru import logger

# ============================================================================
# SECTION 2: Class Definition - WebSocketManager
# ============================================================================

class WebSocketManager:
    """
    Manages active websocket connections and streaming message delivery.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    # ========================================================================
    # Async Function 2.1: connect
    # ========================================================================
    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept a new WebSocket connection and add it to active connections.

        Args:
            websocket: The WebSocket connection to add
        """
        try:
            client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown_client"

            async with self._lock:
                self.active_connections.append(websocket)

            logger.info(f"New WebSocket connection established: {client}")
            logger.debug(f"Active connections: {len(self.active_connections)}")

        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {str(e)}", exc_info=True)
            raise

    # =========================================================================
    # Async Function 2.2: disconnect
    # =========================================================================
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from active connections.

        Args:
            websocket: The WebSocket connection to remove
        """
        try:
            client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown_client"

            async with self._lock:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)
                    logger.info(f"WebSocket connection closed: {client}")
                    logger.debug(f"Remaining connections: {len(self.active_connections)}")

        except Exception as e:
            logger.error(f"Error during WebSocket disconnection: {str(e)}", exc_info=True)

    # =========================================================================
    # Async Function 2.3: disconnect_all
    # =========================================================================
    async def disconnect_all(self):
        """Closes all active WebSocket connections."""
        for websocket in self.active_connections:
            await websocket.close(code=1000)
        self.active_connections.clear()

    # =========================================================================
    # Async Function 2.4: send_message_to_client
    # =========================================================================
    async def send_message_to_client(self, message: str) -> None:
        """
        Send a message to all connected WebSocket clients.

        Args:
            message: The message to send
        """
        if not message:
            logger.warning("Attempted to send empty message to WebSocket clients")
            return

        to_remove = []

        try:
            async with self._lock:
                if not self.active_connections:
                    logger.warning("No active WebSocket connections to send message to")
                    return

                for connection in self.active_connections:
                    client = f"{connection.client.host}:{connection.client.port}" if connection.client else "unknown_client"
                    try:
                        await connection.send_text(message)
                        logger.debug(f"Message sent to {client}")
                    except Exception as e:
                        logger.error(f"Failed to send message to {client}: {str(e)}")
                        to_remove.append(connection)

                if to_remove:
                    logger.warning(f"Removing {len(to_remove)} dead WebSocket connections")
                    for connection in to_remove:
                        try:
                            self.active_connections.remove(connection)
                        except ValueError:
                            pass  # Connection already removed

        except Exception as e:
            logger.error(f"Unexpected error in send_message_to_client: {str(e)}", exc_info=True)
            raise

#
#
## End of Script
