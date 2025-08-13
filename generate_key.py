# ============================================================================
#  File: generate_key.py
#  Version: 1.0 (Focused Security Framework)
#  Purpose: Lightweight security for API authentication, input validation,
#           and WebSocket security protocols only
# ============================================================================
# SECTION 1: Imports & Configuration
# ============================================================================
#
import sys
import os

from src.security_manager import APIAuthenticationManager, SecurityLevel

# --- PATH FIX ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- END PATH FIX ---
#
# ============================================================================
# SECTION 2: Main Execution
# ============================================================================
#
if __name__ == "__main__":
    auth_manager = APIAuthenticationManager()
    # Generate a key for a test user with standard permissions
    api_key = auth_manager.generate_api_key(
        user_id="test_user",
        permissions=["api:read_status"],  # Grant permission to read status
        security_level=SecurityLevel.INTERNAL
    )
    print(f"Generated API Key: {api_key}")
#
#
## End of generate_key.py
