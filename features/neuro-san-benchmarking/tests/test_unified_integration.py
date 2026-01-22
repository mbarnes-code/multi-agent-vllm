"""
Modified test for MultiAgentReasoner using the precision-enhanced system.

This test uses the adapter to run the original test expectations
against our unified-deployments implementation.
"""

# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

from unittest import TestCase
import sys
import os
from pathlib import Path

# Add current directory to path to import the adapter
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from test_adapter import MultiAgentReasoner
except ImportError as e:
    print(f"Could not import test adapter: {e}")
    # Try importing from the original location if available
    try:
        from decomposer.multiagent_reasoner import MultiAgentReasoner
    except ImportError:
        print("Could not import either adapter or original MultiAgentReasoner")
        raise


class TestUnifiedDeploymentsIntegration(TestCase):
    """
    Tests precision-enhanced multi-agent reasoner against unified-deployments.
    """

    def test_multiplication_problem(self):
        """
        Test the reasoner with the standard multiplication problem.
        """
        problem: str = "What is 46048 x 42098?"
        reasoner = MultiAgentReasoner()
        answer: str = reasoner.reason(problem)
        expected: str = "1938528704"
        
        print(f"Problem: {problem}")
        print(f"Answer: {answer}")
        print(f"Expected: {expected}")
        
        self.assertIn(expected, answer, f"Expected '{expected}' to be found in answer: {answer}")

    def test_sorting_problem(self):
        """
        Test the reasoner with a sorting problem similar to the HOCON tests.
        """
        problem = """Sort the following list of numbers from highest to lowest:
601449
153694
216901
849467
137676
704296"""
        
        reasoner = MultiAgentReasoner()
        answer: str = reasoner.reason(problem)
        
        # Expected numbers in sorted order (highest to lowest)
        expected_numbers = ["849467", "704296", "601449", "216901", "153694", "137676"]
        
        print(f"Sorting Problem: {problem.replace(chr(10), ' ')}")
        print(f"Answer: {answer}")
        
        # Check that all expected numbers appear in the response
        for num in expected_numbers:
            self.assertIn(num, answer, f"Expected number '{num}' not found in answer: {answer}")

    def test_precision_configuration(self):
        """
        Test that the reasoner is properly configured with precision enhancement.
        """
        reasoner = MultiAgentReasoner()
        
        # Check that the reasoner has the expected configuration
        self.assertEqual(reasoner.WINNING_VOTE_COUNT, 2, "Default winning vote count should be 2")
        self.assertTrue(hasattr(reasoner, 'voting_config'), "Reasoner should have voting configuration")
        self.assertTrue(hasattr(reasoner, 'error_manager'), "Reasoner should have error manager")

    def test_error_handling(self):
        """
        Test that the reasoner handles invalid problems gracefully.
        """
        problem: str = "This is not a valid mathematical problem"
        reasoner = MultiAgentReasoner()
        answer: str = reasoner.reason(problem)
        
        print(f"Invalid Problem: {problem}")
        print(f"Answer: {answer}")
        
        # Should not crash and should provide some response
        self.assertIsInstance(answer, str, "Answer should be a string")
        self.assertTrue(len(answer) > 0, "Answer should not be empty")

    def test_agent_initialization(self):
        """
        Test that the agents are properly initialized.
        """
        reasoner = MultiAgentReasoner()
        
        # Check that agents dictionary exists and has expected entries
        self.assertTrue(hasattr(reasoner, 'agents'), "Reasoner should have agents")
        self.assertIn('supervisor', reasoner.agents, "Should have supervisor agent")
        self.assertIn('coding', reasoner.agents, "Should have coding agent")
        
    def test_complex_multiplication(self):
        """
        Test with a different multiplication problem to ensure robustness.
        """
        problem: str = "Calculate 12345 × 6789"
        reasoner = MultiAgentReasoner()
        answer: str = reasoner.reason(problem)
        expected: str = str(12345 * 6789)  # 83810205
        
        print(f"Complex Problem: {problem}")
        print(f"Answer: {answer}")
        print(f"Expected: {expected}")
        
        self.assertIn(expected, answer, f"Expected '{expected}' to be found in answer: {answer}")


if __name__ == "__main__":
    import unittest
    
    # Run the tests
    unittest.main(verbosity=2)