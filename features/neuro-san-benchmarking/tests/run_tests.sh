#!/bin/bash

# Test runner script for neuro-san benchmarking integration
# This script runs the tests against the unified-deployments implementation

echo "=== Neuro-SAN Benchmarking Test Runner ==="
echo "Testing precision-enhanced multi-agent system..."
echo

# Set environment variables for testing
export MAX_DEPTH=5
export WINNING_VOTE_COUNT=2
export PYTHONPATH="/workspaces/multi-agent-vllm/unified-deployments:/workspaces/multi-agent-vllm/features/neuro-san-benchmarking/tests:$PYTHONPATH"

# Change to test directory
cd "/workspaces/multi-agent-vllm/features/neuro-san-benchmarking/tests"

echo "Current directory: $(pwd)"
echo "Python path includes: $PYTHONPATH"
echo

# Test 1: Run the adapter directly
echo "=== Test 1: Running test adapter directly ==="
python3 test_adapter.py
echo "Exit code: $?"
echo

# Test 2: Run the placeholder test
echo "=== Test 2: Running placeholder test ==="
python3 -m pytest test_placeholder.py -v
echo "Exit code: $?"
echo

# Test 3: Run the unified integration test
echo "=== Test 3: Running unified integration test ==="
python3 -m pytest test_unified_integration.py -v
echo "Exit code: $?"
echo

# Test 4: Try to run the original multiagent reasoner test with our adapter
echo "=== Test 4: Running adapted multiagent reasoner test ==="
python3 -m pytest test_unified_integration.py::TestUnifiedDeploymentsIntegration::test_multiplication_problem -v
echo "Exit code: $?"
echo

echo "=== Test Summary ==="
echo "All tests completed. Check output above for any failures."
echo "If tests fail, the adapter needs to be fixed to match the expected interface."