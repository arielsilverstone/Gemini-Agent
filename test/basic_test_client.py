# ============================================================================
#  File: basic_test_client.py
#  Version: 1.00
#  Purpose: Basic test client for Gemini-Agent
#  Created: 28JUL25
# ============================================================================
# SECTION 1: Imports and Configuration
# ============================================================================
#
import asyncio
import websockets
import json
import sys
import threading
from loguru import logger
#
# ============================================================================
# SECTION 2: Test Functions
# ============================================================================
# Async Method 2.1: run_test
# ============================================================================
# Purpose: Run a test by connecting to the Gemini-Agent server and sending a task.
# Parameters:
#     port (int): The port number on which the Gemini-Agent server is running.
# Returns:
#     None
# ============================================================================
async def run_test(port):
    uri = f"ws://127.0.0.1:{port}/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connection established.")

            # Define the task for the TestAgent
            test_task = {
                "action": "ipc",
                "payload": {
                    "agent_type": "TestAgent",
                    "task": "Respond with 'Hello World from TestAgent'"
                }
            }

            print(f"Sending task to TestAgent: {json.dumps(test_task)}")
            await websocket.send(json.dumps(test_task))

            # Wait for and print the response
            response = await websocket.recv()
            print(f"Received response: {response}")

            # Validate the response
            if "Hello World from TestAgent" in response:
                print("\n*** Test Passed: Received expected response from TestAgent. ***")
                # Exit with success code
                sys.exit(0)
            else:
                print(f"\n*** Test Failed: Unexpected response. ***")
                # Exit with failure code
                sys.exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        print("\n*** Test Failed: Could not complete test due to an error. ***")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        server_port = int(sys.argv[1])
    else:
        server_port = 9106  # Default port if not provided

    asyncio.run(run_test(server_port))
