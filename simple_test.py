#!/usr/bin/env python3
"""
Simple test script to verify the fixes applied to the Gemini-Agent project
"""

import asyncio
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

async def test_imports():
    """Test basic imports"""
    try:
        # Test async_validator imports
        from src.async_validator import AsyncValidationEngine, ValidationContext
        print("PASS: async_validator imports successful")
        
        # Test rule_engine imports
        from src.rule_engine import RuleEngine
        print("PASS: rule_engine import successful")
        
        # Test agent_base imports
        from agents.agent_base import AgentBase
        print("PASS: agent_base import successful")
        
        # Test async_file_manager imports
        from src.async_file_manager import AsyncFileManager
        print("PASS: async_file_manager import successful")
        
        # Test secure_secrets imports
        from src.secure_secrets import load_secrets, get_secret, validate_secrets
        print("PASS: secure_secrets functions imported successfully")
        
        # Test error_handling imports
        from src.error_handling import AsyncErrorDecorator
        print("PASS: error_handling import successful")
        
        return True
        
    except Exception as e:
        print("FAIL: Import test failed: {}".format(str(e)))
        return False

async def main():
    """Run all tests"""
    print("Testing Gemini-Agent fixes...")
    print("=" * 50)
    
    success = await test_imports()
    
    print("=" * 50)
    if success:
        print("SUCCESS: All imports successful!")
    else:
        print("ERROR: Some imports failed.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
