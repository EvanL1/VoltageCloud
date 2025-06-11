"""
Test runner and test suites for IoT platform
Provides different test execution profiles and reporting
"""

import pytest
import sys
import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from datetime import datetime


class TestRunner:
    """Main test runner for IoT platform tests"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.reports_dir = self.test_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def run_unit_tests(self, verbose: bool = True) -> int:
        """Run unit tests only"""
        args = [
            "-m", "pytest",
            str(self.test_dir),
            "-m", "unit",
            "--cov=iot_poc",
            "--cov-report=term-missing",
            f"--cov-report=html:{self.reports_dir}/unit_coverage",
            f"--junit-xml={self.reports_dir}/unit_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_integration_tests(self, verbose: bool = True) -> int:
        """Run integration tests only"""
        args = [
            "-m", "pytest",
            str(self.test_dir),
            "-m", "integration",
            "--cov=iot_poc",
            "--cov-report=term-missing",
            f"--cov-report=html:{self.reports_dir}/integration_coverage",
            f"--junit-xml={self.reports_dir}/integration_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_e2e_tests(self, verbose: bool = True) -> int:
        """Run end-to-end tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir),
            "-m", "e2e",
            f"--junit-xml={self.reports_dir}/e2e_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_infrastructure_tests(self, verbose: bool = True) -> int:
        """Run infrastructure/CDK tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_infrastructure.py"),
            "--cov=iot_poc",
            f"--cov-report=html:{self.reports_dir}/infrastructure_coverage",
            f"--junit-xml={self.reports_dir}/infrastructure_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_lambda_tests(self, verbose: bool = True) -> int:
        """Run Lambda function tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_lambda_functions.py"),
            "--cov=lambda",
            f"--cov-report=html:{self.reports_dir}/lambda_coverage",
            f"--junit-xml={self.reports_dir}/lambda_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_api_tests(self, verbose: bool = True) -> int:
        """Run API endpoint tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_api_endpoints.py"),
            f"--junit-xml={self.reports_dir}/api_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_etl_tests(self, verbose: bool = True) -> int:
        """Run ETL pipeline tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_glue_etl.py"),
            f"--junit-xml={self.reports_dir}/etl_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_all_tests(self, verbose: bool = True, parallel: bool = False) -> int:
        """Run all tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir),
            "--cov=iot_poc",
            "--cov=lambda",
            "--cov-report=term-missing",
            f"--cov-report=html:{self.reports_dir}/full_coverage",
            f"--junit-xml={self.reports_dir}/all_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        if parallel:
            args.extend(["-n", "auto"])
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_performance_tests(self, verbose: bool = True) -> int:
        """Run performance tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir),
            "-m", "slow",
            "--benchmark-only",
            f"--benchmark-json={self.reports_dir}/benchmark.json"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_rust_tests(self) -> int:
        """Run Rust Lambda tests using cargo"""
        rust_lambda_dir = self.project_root / "rust-lambda"
        
        if not rust_lambda_dir.exists():
            print("Rust Lambda directory not found, skipping Rust tests")
            return 0
        
        # Run cargo test
        result = subprocess.run(
            ["cargo", "test"],
            cwd=rust_lambda_dir,
            capture_output=True,
            text=True
        )
        
        # Save output
        with open(self.reports_dir / "rust_tests.txt", "w") as f:
            f.write(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        
        return result.returncode
    
    def generate_test_report(self) -> Dict:
        """Generate comprehensive test report"""
        from .test_summary_generator import TestSummaryGenerator
        
        # Use the new test summary generator
        generator = TestSummaryGenerator(str(self.reports_dir))
        summary = generator.generate_summary()
        
        # Generate HTML report
        html_file = generator.generate_html_report()
        print(f"📄 Detailed HTML report: {html_file}")
        
        # Print console summary
        generator.print_console_summary()
        
                return summary
    
    def run_monitoring_tests(self, verbose: bool = True) -> int:
        """Run monitoring and observability tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_monitoring.py"),
            f"--junit-xml={self.reports_dir}/monitoring_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
    
    def run_performance_tests_extended(self, verbose: bool = True) -> int:
        """Run extended performance and stress tests"""
        args = [
            "-m", "pytest",
            str(self.test_dir / "test_performance.py"),
            "-m", "slow or benchmark or stress or load",
            f"--junit-xml={self.reports_dir}/performance_extended_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        return subprocess.run([sys.executable] + args).returncode
            "lambda": self.reports_dir / "lambda_tests.xml",
            "api": self.reports_dir / "api_tests.xml",
            "etl": self.reports_dir / "etl_tests.xml",
            "all": self.reports_dir / "all_tests.xml"
        }
        
        for test_type, file_path in test_files.items():
            if file_path.exists():
                report["test_results"][test_type] = {
                    "file": str(file_path),
                    "exists": True
                }
            else:
                report["test_results"][test_type] = {
                    "file": str(file_path),
                    "exists": False
                }
        
        # Check for coverage reports
        coverage_dirs = {
            "unit": self.reports_dir / "unit_coverage",
            "integration": self.reports_dir / "integration_coverage",
            "infrastructure": self.reports_dir / "infrastructure_coverage",
            "lambda": self.reports_dir / "lambda_coverage",
            "full": self.reports_dir / "full_coverage"
        }
        
        for coverage_type, dir_path in coverage_dirs.items():
            if dir_path.exists():
                report["coverage"][coverage_type] = {
                    "directory": str(dir_path),
                    "exists": True
                }
            else:
                report["coverage"][coverage_type] = {
                    "directory": str(dir_path),
                    "exists": False
                }
        
        # Check for performance data
        benchmark_file = self.reports_dir / "benchmark.json"
        if benchmark_file.exists():
            try:
                with open(benchmark_file, 'r') as f:
                    report["performance"] = json.load(f)
            except Exception as e:
                report["performance"] = {"error": str(e)}
        
        # Save report
        report_file = self.reports_dir / "test_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report


def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(description="IoT Platform Test Runner")
    parser.add_argument(
        "test_type",
        choices=[
            "unit", "integration", "e2e", "infrastructure", 
            "lambda", "api", "etl", "all", "performance", "rust"
        ],
        help="Type of tests to run"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-p", "--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Run specified tests
    if args.test_type == "unit":
        result = runner.run_unit_tests(args.verbose)
    elif args.test_type == "integration":
        result = runner.run_integration_tests(args.verbose)
    elif args.test_type == "e2e":
        result = runner.run_e2e_tests(args.verbose)
    elif args.test_type == "infrastructure":
        result = runner.run_infrastructure_tests(args.verbose)
    elif args.test_type == "lambda":
        result = runner.run_lambda_tests(args.verbose)
    elif args.test_type == "api":
        result = runner.run_api_tests(args.verbose)
    elif args.test_type == "etl":
        result = runner.run_etl_tests(args.verbose)
    elif args.test_type == "all":
        result = runner.run_all_tests(args.verbose, args.parallel)
    elif args.test_type == "performance":
        result = runner.run_performance_tests(args.verbose)
    elif args.test_type == "rust":
        result = runner.run_rust_tests()
    
    # Generate report if requested
    if args.report:
        report = runner.generate_test_report()
        print(f"\nTest report generated: {runner.reports_dir}/test_report.json")
        print(f"Coverage reports available in: {runner.reports_dir}/")
    
    return result


if __name__ == "__main__":
    sys.exit(main()) 