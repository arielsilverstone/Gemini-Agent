"""
Test script to verify the fixes applied to the Gemini-Agent project
"""

import asyncio
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

async def test_async_validator():
    """Test the async validator imports"""
    try:
        from src.async_validator import AsyncValidationEngine, ValidationContext
        print("PASS: async_validator imports successful")

        # Test basic instantiation
        validator = AsyncValidationEngine()
        context = ValidationContext(data={}, rules=[])
        print("PASS: AsyncValidationEngine and ValidationContext instantiated")

    except Exception as e:
        print(f"FAIL: async_validator test failed: {e}")
        return False
    return True

async def test_rule_engine():
    """Test the rule engine functionality"""
    try:
        from src.rule_engine import RuleEngine
        print("PASS: rule_engine import successful")

        # Test basic instantiation
        engine = RuleEngine()
        print("PASS: RuleEngine instantiated")

        # Test the documentation and template methods exist
        assert hasattr(engine, 'check_documentation_rule')
        assert hasattr(engine, 'check_template_adherence_rule')
        print("PASS: RuleEngine methods verified")

    except Exception as e:
        print(f"FAIL: rule_engine test failed: {e}")
        return False
    return True

async def test_agent_base():
    """Test the agent base functionality"""
    try:
        from agents.agent_base import AgentBase
        print("PASS: agent_base import successful")

        # Test that _enforce_agent_rules method exists
        assert hasattr(AgentBase, '_enforce_agent_rules')
        print("PASS: AgentBase._enforce_agent_rules method verified")

    except Exception as e:
        print(f"FAIL: agent_base test failed: {e}")
        return False
    return True

async def main():
    """Run all tests"""
    print("Testing Gemini-Agent fixes...")
    print("=" * 50)

    tests = [
        test_async_validator,
        test_rule_engine,
        test_agent_base
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)
        print()

    print("=" * 50)
    if all(results):
        print("SUCCESS: All tests passed! The fixes are working correctly.")
    else:
        print("ERROR: Some tests failed. Check the output above for details.")

    return all(results)

if __name__ == "__main__":
    asyncio.run(main())
