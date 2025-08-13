# ============================================================================
#  File:    test_client.py
#  Version: 1.02
#  Purpose: Test client for Gemini-Agent
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
#
import asyncio
import websockets
import json
from loguru import logger
#
# ============================================================================
# SECTION 2: Function Definitions
# ============================================================================
# Async Function 2.1: test_workflow()
# This function tests the workflow by connecting to the WebSocket server and
# sending a workflow request.
# ============================================================================

async def test_workflow():
    api_key = "ga_ZNQGpmtdX_lx_-30GN5-9YO-E4jXg0IO3iRRMe7qZzs="
    uri = f"ws://127.0.0.1:9102/ws?token={api_key}"
    logger.info(f"Connecting to {uri}")

    try:
        # Set an overall timeout for the workflow execution
        async with asyncio.timeout(150):  # 2.5 minutes total timeout
            # Use a timeout for the entire connection attempt
            async with asyncio.timeout(60):
                async with websockets.connect(uri) as websocket:
                    # 1. Wait for authentication confirmation
                    auth_response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    logger.info(f"< Auth Response: {auth_response}")
                    response_data = json.loads(auth_response)

                    if not response_data.get("authenticated"):
                        logger.error("Authentication failed.")
                        print(f"< Auth Response: {auth_response}")
                        print("Authentication failed.")
                        return

                    # 2. Execute workflow (with a 120-second timeout for the entire process)
                    workflow_request = {
                        "type": "command",
                        "command": "execute_workflow",
                        "payload": {
                            "workflow_name": "codegen_forbidden_import_test",
                            "context": {
                                "initial_task": "Create a Python script that lists files in the current directory using the 'os' module."
                            }
                        }
                    }
                    await websocket.send(json.dumps(workflow_request))
                    print(f"> Sent workflow request: {json.dumps(workflow_request)}")
                    logger.info(f"> Sent workflow request: {json.dumps(workflow_request)}")

                    # 3. Listen for responses (with a 60-second timeout for each message)
                    while True:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                            print(f"< Received: {message}")
                            logger.info(f"< Received: {message}")
                            data = json.loads(message)
                            if data.get("status") in ["completed", "failed", "error"]:
                                print("Workflow finished.")
                                logger.info("Workflow finished.")
                                break
                        except asyncio.TimeoutError:
                            print("Timeout waiting for message. Closing connection.")
                            logger.error("Timeout waiting for message. Closing connection.")
                            break
                        except websockets.exceptions.ConnectionClosed:
                            print("Connection closed by server.")
                            logger.error("Connection closed by server.")
                            break

    except asyncio.TimeoutError:
        print("Overall workflow execution timed out.")
        logger.error("Overall workflow execution timed out.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
#
# ============================================================================
# SECTION 3: Main Entry Point
# ============================================================================
#
if __name__ == "__main__":
    asyncio.run(test_workflow())
    logger.info("Test client finished.")
#
#
## End of test_client.py
