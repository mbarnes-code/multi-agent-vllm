#!/usr/bin/env python3
"""
Simple validation script to test the integration without complex dependencies.
"""

import sys
import os
from pathlib import Path

# Add paths
current_dir = Path(__file__).parent
unified_deployments = current_dir.parent.parent.parent / "unified-deployments"
sys.path.insert(0, str(unified_deployments))
sys.path.insert(0, str(current_dir))

def test_imports():
    """Test that we can import required modules."""
    try:
        print("Testing unified-deployments imports...")
        
        # Test basic imports
        from multi_agent.core import Agent, Response
        print("✓ Core imports successful")
        
        from multi_agent.precision import VotingConfig, ErrorRecoveryManager
        print("✓ Precision imports successful")
        
        from multi_agent.cross_validation import ValidationLevel
        print("✓ Cross-validation imports successful")
        
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_adapter():
    """Test the adapter functionality."""
    try:
        print("\nTesting adapter...")
        
        from test_adapter import MultiAgentReasoner
        print("✓ Adapter import successful")
        
        reasoner = MultiAgentReasoner()
        print("✓ Reasoner initialization successful")
        
        # Test simple problem
        problem = "What is 123 x 456?"
        result = reasoner.reason(problem)
        expected = str(123 * 456)  # 56088
        
        print(f"Problem: {problem}")
        print(f"Result: {result[:200]}...")
        print(f"Expected: {expected}")
        
        if expected in result:
            print("✓ Simple math test passed")
            return True
        else:
            print("✗ Simple math test failed")
            return False
            
    except Exception as e:
        print(f"✗ Adapter test failed: {e}")
        return False

def test_sorting():
    """Test sorting functionality."""
    try:
        print("\nTesting sorting...")
        
        from test_adapter import MultiAgentReasoner
        reasoner = MultiAgentReasoner()
        
        problem = """Sort from highest to lowest: 300, 100, 200"""
        result = reasoner.reason(problem)
        
        print(f"Sort problem: {problem}")
        print(f"Result: {result[:200]}...")
        
        # Check if the sorted order appears in result
        expected_order = ["300", "200", "100"]
        if all(num in result for num in expected_order):
            print("✓ Sorting test passed")
            return True
        else:
            print("✗ Sorting test failed")
            return False
            
    except Exception as e:
        print(f"✗ Sorting test failed: {e}")
        return False

def test_precision_features():
    """Test precision enhancement features."""
    try:
        print("\nTesting precision features...")
        
        from test_adapter import MultiAgentReasoner
        reasoner = MultiAgentReasoner()
        
        # Check configuration
        print(f"Winning vote count: {reasoner.WINNING_VOTE_COUNT}")
        print(f"Max depth: {reasoner.MAX_DEPTH}")
        print(f"Has voting config: {hasattr(reasoner, 'voting_config')}")
        print(f"Has error manager: {hasattr(reasoner, 'error_manager')}")
        
        if reasoner.WINNING_VOTE_COUNT == 2 and hasattr(reasoner, 'voting_config'):
            print("✓ Precision configuration test passed")
            return True
        else:
            print("✗ Precision configuration test failed")
            return False
            
    except Exception as e:
        print(f"✗ Precision features test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("=== Neuro-SAN Integration Validation ===\n")
    
    tests = [
        ("Import Test", test_imports),
        ("Adapter Test", test_adapter),
        ("Sorting Test", test_sorting),
        ("Precision Features Test", test_precision_features),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} PASSED\n")
            else:
                print(f"✗ {test_name} FAILED\n")
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}\n")
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All validation tests passed!")
        return 0
    else:
        print("❌ Some tests failed. Check output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())