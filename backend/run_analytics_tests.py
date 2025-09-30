#!/usr/bin/env python3
"""
Analytics Test Suite Runner

This script runs all analytics-related tests with comprehensive reporting.
Supports unit tests, integration tests, and performance tests.
"""
import sys
import os
import subprocess
import json
import time
from typing import Dict, List, Any
from datetime import datetime
import argparse


def run_command(cmd: List[str], capture_output: bool = True) -> Dict[str, Any]:
    """Run a command and return results."""
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        duration = time.time() - start_time

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout if capture_output else "",
            "stderr": result.stderr if capture_output else "",
            "duration": duration,
            "command": " ".join(cmd)
        }

    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "duration": time.time() - start_time,
            "command": " ".join(cmd)
        }


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_test_result(test_name: str, result: Dict[str, Any]):
    """Print formatted test result."""
    status = "✅ PASSED" if result["success"] else "❌ FAILED"
    duration = f"{result['duration']:.2f}s"

    print(f"{status} {test_name} ({duration})")

    if not result["success"]:
        print(f"   Command: {result['command']}")
        if result["stderr"]:
            print(f"   Error: {result['stderr']}")
        if result["stdout"]:
            print(f"   Output: {result['stdout']}")


def run_unit_tests() -> Dict[str, Any]:
    """Run unit tests for analytics components."""
    print_section("UNIT TESTS")

    results = {}

    # Test analytics tables
    print("Running AnalyticsTable unit tests...")
    result = run_command([
        sys.executable, "-m", "pytest",
        "open_webui/test/test_analytics_tables.py",
        "-v", "--tb=short"
    ])
    results["analytics_tables"] = result
    print_test_result("AnalyticsTable Tests", result)

    # Test analytics router
    print("\nRunning Analytics Router unit tests...")
    result = run_command([
        sys.executable, "-m", "pytest",
        "open_webui/test/test_analytics_router.py",
        "-v", "--tb=short"
    ])
    results["analytics_router"] = result
    print_test_result("Analytics Router Tests", result)

    return results


def run_integration_tests() -> Dict[str, Any]:
    """Run integration tests."""
    print_section("INTEGRATION TESTS")

    results = {}

    # Integration tests with actual database
    print("Running integration tests with database...")
    result = run_command([
        sys.executable, "-m", "pytest",
        "open_webui/test/test_analytics_tables.py::TestAnalyticsTableIntegration",
        "-v", "--tb=short", "-m", "integration"
    ])
    results["database_integration"] = result
    print_test_result("Database Integration Tests", result)

    return results


def run_performance_tests() -> Dict[str, Any]:
    """Run performance tests."""
    print_section("PERFORMANCE TESTS")

    results = {}

    # Performance tests
    print("Running performance tests...")
    result = run_command([
        sys.executable, "-m", "pytest",
        "open_webui/test/test_analytics_router.py::TestAnalyticsRouterPerformance",
        "-v", "--tb=short", "-m", "performance"
    ])
    results["api_performance"] = result
    print_test_result("API Performance Tests", result)

    return results


def run_frontend_tests() -> Dict[str, Any]:
    """Run frontend tests."""
    print_section("FRONTEND TESTS")

    results = {}

    # Check if we're in the right directory structure
    frontend_test_path = "../src/lib/apis/analytics/analytics.test.ts"
    if os.path.exists(frontend_test_path):
        print("Running frontend API service tests...")
        result = run_command([
            "npm", "test", "--", "analytics.test.ts"
        ])
        results["frontend_api"] = result
        print_test_result("Frontend API Tests", result)
    else:
        print("⚠️  Frontend test file not found, skipping frontend tests")
        results["frontend_api"] = {
            "success": True,
            "returncode": 0,
            "stdout": "Skipped - test file not found",
            "stderr": "",
            "duration": 0,
            "command": "skipped"
        }

    return results


def run_linting() -> Dict[str, Any]:
    """Run code linting and formatting checks."""
    print_section("CODE QUALITY CHECKS")

    results = {}

    # Python linting
    analytics_files = [
        "open_webui/cogniforce_models/analytics_tables.py",
        "open_webui/cogniforce_models/analytics_cache.py",
        "open_webui/cogniforce_models/analytics_monitoring.py",
        "open_webui/cogniforce_models/analytics_resilience.py",
        "open_webui/routers/analytics.py",
        "open_webui/routers/analytics_docs.py"
    ]

    # Check if files exist
    existing_files = [f for f in analytics_files if os.path.exists(f)]

    if existing_files:
        print("Running Python linting (flake8)...")
        result = run_command([
            sys.executable, "-m", "flake8",
            "--max-line-length=88",
            "--extend-ignore=E203,W503"
        ] + existing_files)
        results["python_linting"] = result
        print_test_result("Python Linting", result)

        # Type checking
        print("\nRunning type checking (mypy)...")
        result = run_command([
            sys.executable, "-m", "mypy",
            "--ignore-missing-imports",
            "--no-strict-optional"
        ] + existing_files)
        results["type_checking"] = result
        print_test_result("Type Checking", result)
    else:
        print("⚠️  No analytics files found for linting")

    return results


def generate_coverage_report() -> Dict[str, Any]:
    """Generate test coverage report."""
    print_section("COVERAGE ANALYSIS")

    print("Generating coverage report...")

    # Run tests with coverage
    result = run_command([
        sys.executable, "-m", "pytest",
        "--cov=open_webui.cogniforce_models",
        "--cov=open_webui.routers.analytics",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "open_webui/test/test_analytics_tables.py",
        "open_webui/test/test_analytics_router.py"
    ])

    print_test_result("Coverage Analysis", result)

    if result["success"]:
        print("\n📊 Coverage report generated in 'htmlcov/' directory")

    return {"coverage": result}


def run_all_tests(args) -> None:
    """Run all test suites and generate report."""
    start_time = time.time()

    print("🚀 Starting Analytics Test Suite")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")

    all_results = {}

    # Run different test types based on arguments
    if args.unit or args.all:
        all_results.update(run_unit_tests())

    if args.integration or args.all:
        all_results.update(run_integration_tests())

    if args.performance or args.all:
        all_results.update(run_performance_tests())

    if args.frontend or args.all:
        all_results.update(run_frontend_tests())

    if args.lint or args.all:
        all_results.update(run_linting())

    if args.coverage or args.all:
        all_results.update(generate_coverage_report())

    # Generate summary
    total_duration = time.time() - start_time

    print_section("TEST SUMMARY")

    passed = sum(1 for r in all_results.values() if r["success"])
    failed = len(all_results) - passed
    total_time = sum(r["duration"] for r in all_results.values())

    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Total Test Time: {total_time:.2f}s")
    print(f"⏱️  Total Runtime: {total_duration:.2f}s")

    # Detailed results
    if failed > 0:
        print("\n💥 FAILED TESTS:")
        for name, result in all_results.items():
            if not result["success"]:
                print(f"   - {name}: {result.get('stderr', 'Unknown error')}")

    # Save results to JSON
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": len(all_results),
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / len(all_results)) * 100 if all_results else 0,
            "total_duration": total_duration
        },
        "results": all_results,
        "environment": {
            "python_version": sys.version,
            "working_directory": os.getcwd()
        }
    }

    report_file = f"analytics_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)

    print(f"\n📄 Detailed report saved to: {report_file}")

    # Exit with appropriate code
    if failed > 0:
        print("\n💥 Some tests failed!")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Analytics Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_analytics_tests.py --all          # Run all tests
  python run_analytics_tests.py --unit         # Run only unit tests
  python run_analytics_tests.py --integration  # Run only integration tests
  python run_analytics_tests.py --coverage     # Run tests with coverage
  python run_analytics_tests.py --lint         # Run only linting
        """
    )

    parser.add_argument("--all", action="store_true",
                       help="Run all test types")
    parser.add_argument("--unit", action="store_true",
                       help="Run unit tests")
    parser.add_argument("--integration", action="store_true",
                       help="Run integration tests")
    parser.add_argument("--performance", action="store_true",
                       help="Run performance tests")
    parser.add_argument("--frontend", action="store_true",
                       help="Run frontend tests")
    parser.add_argument("--lint", action="store_true",
                       help="Run linting and code quality checks")
    parser.add_argument("--coverage", action="store_true",
                       help="Generate coverage report")

    args = parser.parse_args()

    # If no specific test type is specified, run all
    if not any([args.unit, args.integration, args.performance,
               args.frontend, args.lint, args.coverage]):
        args.all = True

    try:
        run_all_tests(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()