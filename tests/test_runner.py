"""
Test runner and test suites for IoT platform
Provides different test execution profiles and reporting
Supports conda environment execution
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from datetime import datetime
import shutil

# Import pytest only when needed
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


class TestRunner:
    """Main test runner for IoT platform tests with conda support"""
    
    def __init__(self, conda_env: Optional[str] = None):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.reports_dir = self.test_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Conda environment configuration
        self.conda_env = conda_env or self._detect_conda_env()
        self.conda_prefix = self._get_conda_prefix()
        
        # Check conda availability
        if not self._is_conda_available():
            print("⚠️  Warning: conda not found in PATH. Falling back to system Python.")
            self.use_conda = False
        else:
            self.use_conda = True
            print(f"🐍 Using conda environment: {self.conda_env}")
    
    def _detect_conda_env(self) -> str:
        """Detect current conda environment"""
        # Try to get from CONDA_DEFAULT_ENV environment variable
        env_name = os.environ.get('CONDA_DEFAULT_ENV')
        if env_name and env_name != 'base':
            return env_name
        
        # Try to get from CONDA_PREFIX
        conda_prefix = os.environ.get('CONDA_PREFIX')
        if conda_prefix:
            return Path(conda_prefix).name
        
        # Default to base if nothing found
        return 'base'
    
    def _get_conda_prefix(self) -> Optional[str]:
        """Get conda prefix path"""
        return os.environ.get('CONDA_PREFIX')
    
    def _is_conda_available(self) -> bool:
        """Check if conda is available in the system"""
        return shutil.which('conda') is not None
    
    def _get_python_executable(self) -> str:
        """Get the Python executable for the conda environment"""
        if not self.use_conda:
            return sys.executable
        
        # For conda environments, we'll use conda run instead of direct paths
        # This ensures proper environment activation
        return "python"
    
    def _run_command_in_conda(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run command in conda environment"""
        if not self.use_conda:
            return subprocess.run(args, **kwargs)
        
        # Use conda run to ensure proper environment activation
        conda_args = ['conda', 'run', '-n', self.conda_env] + args
        return subprocess.run(conda_args, **kwargs)
    
    def _prepare_test_environment(self):
        """Prepare the test environment"""
        print(f"🔧 Preparing test environment...")
        
        if self.use_conda:
            print(f"   Using conda environment: {self.conda_env}")
            
            # Verify environment exists
            result = subprocess.run(
                ['conda', 'env', 'list'], 
                capture_output=True, 
                text=True
            )
            
            if self.conda_env not in result.stdout:
                print(f"❌ Conda environment '{self.conda_env}' not found!")
                print("Available environments:")
                print(result.stdout)
                return False
        
        # Create reports directory
        self.reports_dir.mkdir(exist_ok=True)
        print(f"   Reports directory: {self.reports_dir}")
        
        return True
    
    def run_unit_tests(self, verbose: bool = True) -> int:
        """Run unit tests only"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
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
        
        print("🧪 Running unit tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_integration_tests(self, verbose: bool = True) -> int:
        """Run integration tests only"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
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
        
        print("🔗 Running integration tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_e2e_tests(self, verbose: bool = True) -> int:
        """Run end-to-end tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir),
            "-m", "e2e",
            f"--junit-xml={self.reports_dir}/e2e_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("🎯 Running end-to-end tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_infrastructure_tests(self, verbose: bool = True) -> int:
        """Run infrastructure/CDK tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_infrastructure.py"),
            "--cov=iot_poc",
            f"--cov-report=html:{self.reports_dir}/infrastructure_coverage",
            f"--junit-xml={self.reports_dir}/infrastructure_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("🏗️ Running infrastructure tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_lambda_tests(self, verbose: bool = True) -> int:
        """Run Lambda function tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_lambda_functions.py"),
            "--cov=lambda",
            f"--cov-report=html:{self.reports_dir}/lambda_coverage",
            f"--junit-xml={self.reports_dir}/lambda_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("⚡ Running Lambda function tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_api_tests(self, verbose: bool = True) -> int:
        """Run API endpoint tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_api_endpoints.py"),
            f"--junit-xml={self.reports_dir}/api_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("🌐 Running API endpoint tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_etl_tests(self, verbose: bool = True) -> int:
        """Run ETL pipeline tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_glue_etl.py"),
            f"--junit-xml={self.reports_dir}/etl_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("🔄 Running ETL pipeline tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_all_tests(self, verbose: bool = True, parallel: bool = False) -> int:
        """Run all tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
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
        
        print("🚀 Running all tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_performance_tests(self, verbose: bool = True) -> int:
        """Run performance tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir),
            "-m", "slow",
            "--benchmark-only",
            f"--benchmark-json={self.reports_dir}/benchmark.json"
        ]
        
        if verbose:
            args.append("-v")
        
        print("⚡ Running performance tests...")
        return self._run_command_in_conda(args).returncode
    

    
    def generate_test_report(self) -> Dict:
        """Generate comprehensive test report"""
        print("📊 Generating test report...")
        
        try:
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
        except ImportError:
            print("⚠️  Test summary generator not available, generating basic report...")
            return self._generate_basic_report()
    
    def _generate_basic_report(self) -> Dict:
        """Generate basic test report if summary generator is not available"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "conda_env": self.conda_env if self.use_conda else "system",
            "python_executable": self._get_python_executable(),
            "test_results": {},
            "coverage": {},
            "performance": {}
        }
        
        # Check for test result files
        test_files = {
            "unit": self.reports_dir / "unit_tests.xml",
            "integration": self.reports_dir / "integration_tests.xml",
            "infrastructure": self.reports_dir / "infrastructure_tests.xml",
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
    
    def run_monitoring_tests(self, verbose: bool = True) -> int:
        """Run monitoring and observability tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_monitoring.py"),
            f"--junit-xml={self.reports_dir}/monitoring_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("📊 Running monitoring tests...")
        return self._run_command_in_conda(args).returncode
    
    def run_performance_tests_extended(self, verbose: bool = True) -> int:
        """Run extended performance and stress tests"""
        if not self._prepare_test_environment():
            return 1
        
        args = [
            self._get_python_executable(),
            "-m", "pytest",
            str(self.test_dir / "test_performance.py"),
            "-m", "slow or benchmark or stress or load",
            f"--junit-xml={self.reports_dir}/performance_extended_tests.xml"
        ]
        
        if verbose:
            args.append("-v")
        
        print("🚀 Running extended performance tests...")
        return self._run_command_in_conda(args).returncode
    
    def check_conda_environment(self):
        """Check and display conda environment information"""
        print("\n🐍 Conda Environment Information:")
        print("=" * 50)
        
        if not self.use_conda:
            print("❌ Conda not available, using system Python")
            print(f"   Python executable: {sys.executable}")
            return
        
        print(f"✅ Current environment: {self.conda_env}")
        print(f"   Python executable: {self._get_python_executable()}")
        print(f"   Conda prefix: {self.conda_prefix}")
        
        # Show environment packages
        try:
            result = subprocess.run(
                ['conda', 'list', '-n', self.conda_env, '--json'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                relevant_packages = [
                    pkg for pkg in packages 
                    if pkg['name'] in ['pytest', 'pytest-cov', 'boto3', 'aws-cdk-lib']
                ]
                
                if relevant_packages:
                    print("\n📦 Key testing packages:")
                    for pkg in relevant_packages:
                        print(f"   {pkg['name']}: {pkg['version']}")
                else:
                    print("\n⚠️  No key testing packages found")
            
        except Exception as e:
            print(f"\n⚠️  Could not list packages: {e}")


def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(description="IoT Platform Test Runner with Conda Support")
    parser.add_argument(
        "test_type",
        choices=[
            "unit", "integration", "e2e", "infrastructure", 
            "lambda", "api", "etl", "all", "performance",
            "monitoring", "performance-extended", "info"
        ],
        help="Type of tests to run or 'info' to show environment information"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-p", "--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    parser.add_argument("--conda-env", type=str, help="Specify conda environment name")
    
    args = parser.parse_args()
    
    runner = TestRunner(conda_env=args.conda_env)
    
    # Show environment info if requested
    if args.test_type == "info":
        runner.check_conda_environment()
        return 0
    
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

    elif args.test_type == "monitoring":
        result = runner.run_monitoring_tests(args.verbose)
    elif args.test_type == "performance-extended":
        result = runner.run_performance_tests_extended(args.verbose)
    
    # Generate report if requested
    if args.report:
        report = runner.generate_test_report()
        print(f"\n📊 Test report generated: {runner.reports_dir}/test_report.json")
        print(f"📄 Coverage reports available in: {runner.reports_dir}/")
    
    return result


if __name__ == "__main__":
    sys.exit(main()) 