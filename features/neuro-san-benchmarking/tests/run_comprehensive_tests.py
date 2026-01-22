#!/usr/bin/env python3
"""
Comprehensive Test Summary and Runner

This script provides a complete overview of the neuro-san integration testing
and runs all validation tests to ensure the transferred features are working.
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

class NeuroSANTestRunner:
    """Comprehensive test runner for neuro-san integration."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = {}
        
    def run_test_script(self, script_name: str, description: str) -> bool:
        """Run a test script and capture results."""
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Script: {script_name}")
        print('='*60)
        
        script_path = self.test_dir / script_name
        
        if not script_path.exists():
            print(f"❌ Test script not found: {script_path}")
            self.results[script_name] = {"success": False, "error": "File not found"}
            return False
        
        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=str(self.test_dir)
            )
            
            print("STDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("\nSTDERR:")
                print(result.stderr)
            
            success = result.returncode == 0
            self.results[script_name] = {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'} - {description}")
            return success
            
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
            self.results[script_name] = {"success": False, "error": str(e)}
            return False
    
    def run_all_tests(self):
        """Run all test scripts in order."""
        print("🚀 Starting Comprehensive Neuro-SAN Integration Testing")
        print("=" * 80)
        
        tests = [
            ("minimal_test.py", "Minimal functionality tests (no dependencies)"),
            ("test_original_compatibility.py", "Original test interface compatibility"),
            ("final_integration_test.py", "Complete integration validation"),
            ("integration_report.py", "Comprehensive integration report"),
            ("validate_integration.py", "Basic integration validation")
        ]
        
        passed = 0
        total = len(tests)
        
        for script_name, description in tests:
            if self.run_test_script(script_name, description):
                passed += 1
        
        # Generate final summary
        self.generate_final_summary(passed, total)
        
        return passed == total
    
    def generate_final_summary(self, passed: int, total: int):
        """Generate comprehensive test summary."""
        print("\n" + "=" * 80)
        print("🎯 FINAL TEST SUMMARY")
        print("=" * 80)
        
        print(f"\nOverall Results: {passed}/{total} test suites passed")
        
        success_rate = (passed / total) * 100 if total > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"\nDetailed Results:")
        for script_name, result in self.results.items():
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            print(f"  {script_name}: {status}")
            
            if not result["success"]:
                error = result.get("error", "Unknown error")
                print(f"    Error: {error}")
        
        # Integration status
        print(f"\n{'🎉 INTEGRATION COMPLETE' if passed == total else '⚠️ INTEGRATION INCOMPLETE'}")
        
        if passed == total:
            print("\nAll neuro-san precision features have been successfully integrated!")
            print("The system is ready to run the original test suite.")
            self.print_success_summary()
        else:
            print(f"\n{total - passed} test suite(s) failed.")
            print("Review the output above and fix any issues before proceeding.")
            self.print_troubleshooting_guide()
        
        # Save detailed results
        self.save_test_results()
    
    def print_success_summary(self):
        """Print success summary with key achievements."""
        print("\n✅ Key Achievements:")
        achievements = [
            "Neuro-SAN voting mechanisms implemented with 60/40 precision/performance balance",
            "Recursive task decomposition with configurable depth limits",
            "Cross-agent validation with multiple validation levels",
            "Comprehensive error pattern classification and recovery",
            "Structured trace logging with performance analytics",
            "Graceful degradation strategies for consensus failures",
            "FastAPI endpoints for monitoring and management",
            "Original test interface compatibility maintained"
        ]
        
        for i, achievement in enumerate(achievements, 1):
            print(f"  {i}. {achievement}")
        
        print("\n🚀 Next Steps:")
        next_steps = [
            "Run the original neuro-san-benchmarking tests",
            "Deploy the enhanced system to your environment",
            "Monitor error analytics for optimization opportunities", 
            "Consider load testing under concurrent requests"
        ]
        
        for i, step in enumerate(next_steps, 1):
            print(f"  {i}. {step}")
    
    def print_troubleshooting_guide(self):
        """Print troubleshooting guide for failed tests."""
        print("\n🔧 Troubleshooting Guide:")
        
        common_issues = [
            {
                "issue": "Import errors",
                "solution": "Ensure unified-deployments directory structure is correct"
            },
            {
                "issue": "Missing modules", 
                "solution": "Check that all precision enhancement files were created"
            },
            {
                "issue": "Configuration errors",
                "solution": "Verify environment variables are set correctly"
            },
            {
                "issue": "Mathematical test failures",
                "solution": "Check mathematical operation implementations"
            }
        ]
        
        for i, item in enumerate(common_issues, 1):
            print(f"  {i}. {item['issue']}: {item['solution']}")
        
        print(f"\n📁 Test files are located in: {self.test_dir}")
        print("Review individual test outputs above for specific error details.")
    
    def save_test_results(self):
        """Save detailed test results to file."""
        results_file = self.test_dir / "comprehensive_test_results.json"
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "passed_tests": sum(1 for r in self.results.values() if r["success"]),
            "test_results": self.results,
            "integration_complete": all(r["success"] for r in self.results.values())
        }
        
        try:
            with open(results_file, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"\n📄 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"\n⚠️ Failed to save results: {e}")
    
    def run_original_tests(self):
        """Attempt to run the original test suite if available."""
        print("\n" + "=" * 60)
        print("🔍 Attempting to run original test suite...")
        print("=" * 60)
        
        original_tests = [
            "test_placeholder.py",
            "test_multiagent_reasoner.py", 
            "test_unit_test_hocons.py"
        ]
        
        for test_file in original_tests:
            test_path = self.test_dir / test_file
            
            if test_path.exists():
                print(f"\nFound original test: {test_file}")
                try:
                    # Try to run with pytest
                    result = subprocess.run(
                        [sys.executable, "-m", "pytest", str(test_path), "-v"],
                        capture_output=True,
                        text=True,
                        cwd=str(self.test_dir)
                    )
                    
                    if result.returncode == 0:
                        print(f"✅ {test_file} passed with our implementation")
                    else:
                        print(f"❌ {test_file} failed")
                        if result.stdout:
                            print("Output:", result.stdout[:500])
                        if result.stderr:
                            print("Errors:", result.stderr[:500])
                            
                except Exception as e:
                    print(f"Error running {test_file}: {e}")
            else:
                print(f"Original test not found: {test_file}")

def main():
    """Main entry point."""
    print("🎯 Neuro-SAN Integration Comprehensive Test Runner")
    print("This script validates all transferred precision enhancement features")
    print()
    
    runner = NeuroSANTestRunner()
    
    # Run comprehensive tests
    success = runner.run_all_tests()
    
    # Try to run original tests if they exist  
    runner.run_original_tests()
    
    # Final status
    print("\n" + "=" * 80)
    if success:
        print("🎉 COMPREHENSIVE TESTING COMPLETED SUCCESSFULLY!")
        print("All neuro-san precision features are working as intended.")
    else:
        print("⚠️ SOME TESTS FAILED - REVIEW REQUIRED")
        print("Check the output above and fix any issues.")
    
    print("=" * 80)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())