#!/usr/bin/env python3
"""
Ultimate IoT Platform Test Execution Script
Comprehensive testing with reporting, monitoring, and CI/CD integration
"""

import os
import sys
import time
import argparse
import subprocess
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class UltimateTestRunner:
    """Ultimate test runner for IoT platform with comprehensive features"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.tests_dir = self.project_root / "tests"
        self.reports_dir = self.tests_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Color codes for output
        self.colors = {
            'RED': '\033[0;31m',
            'GREEN': '\033[0;32m',
            'YELLOW': '\033[1;33m',
            'BLUE': '\033[0;34m',
            'PURPLE': '\033[0;35m',
            'CYAN': '\033[0;36m',
            'WHITE': '\033[1;37m',
            'NC': '\033[0m'  # No Color
        }
        
        # Test suites configuration
        self.test_suites = {
            'unit': {
                'name': '🧪 Unit Tests',
                'command': ['python', 'tests/test_runner.py', 'unit', '-v'],
                'fast': True,
                'critical': True
            },
            'integration': {
                'name': '🔗 Integration Tests', 
                'command': ['python', 'tests/test_runner.py', 'integration', '-v'],
                'fast': False,
                'critical': True
            },
            'infrastructure': {
                'name': '🏗️ Infrastructure Tests',
                'command': ['python', 'tests/test_runner.py', 'infrastructure', '-v'],
                'fast': True,
                'critical': True
            },
            'api': {
                'name': '🌐 API Tests',
                'command': ['python', 'tests/test_runner.py', 'api', '-v'],
                'fast': False,
                'critical': False
            },
            'etl': {
                'name': '📊 ETL Tests',
                'command': ['python', 'tests/test_runner.py', 'etl', '-v'],
                'fast': False,
                'critical': False
            },
            'monitoring': {
                'name': '📈 Monitoring Tests',
                'command': ['python', 'tests/test_runner.py', 'monitoring', '-v'],
                'fast': True,
                'critical': False
            },
            'performance': {
                'name': '⚡ Performance Tests',
                'command': ['python', 'tests/test_runner.py', 'performance', '-v'],
                'fast': False,
                'critical': False
            },
            'rust': {
                'name': '🦀 Rust Tests',
                'command': ['python', 'tests/test_runner.py', 'rust', '-v'],
                'fast': True,
                'critical': True
            }
        }
    
    def print_colored(self, message: str, color: str = 'WHITE'):
        """Print colored message"""
        print(f"{self.colors[color]}{message}{self.colors['NC']}")
    
    def print_banner(self):
        """Print test execution banner"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                  🧪 IoT PLATFORM TEST SUITE                  ║
║                     Ultimate Test Runner                     ║
╚══════════════════════════════════════════════════════════════╝
        """
        self.print_colored(banner, 'CYAN')
        self.print_colored(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'BLUE')
        print()
    
    def setup_environment(self):
        """Setup test environment"""
        self.print_colored("🔧 Setting up test environment...", 'BLUE')
        
        # Set AWS test environment variables
        test_env = {
            'AWS_ACCESS_KEY_ID': 'testing',
            'AWS_SECRET_ACCESS_KEY': 'testing',
            'AWS_SECURITY_TOKEN': 'testing',
            'AWS_SESSION_TOKEN': 'testing',
            'AWS_DEFAULT_REGION': 'us-east-1'
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
        
        # Check dependencies
        self.check_dependencies()
        
        self.print_colored("✅ Environment setup complete", 'GREEN')
        print()
    
    def check_dependencies(self):
        """Check required dependencies"""
        dependencies = [
            ('python', 'Python'),
            ('pip', 'Pip'),
        ]
        
        optional_deps = [
            ('node', 'Node.js (for CDK)'),
            ('cargo', 'Rust Cargo'),
            ('docker', 'Docker')
        ]
        
        # Check required dependencies
        for cmd, name in dependencies:
            try:
                subprocess.run([cmd, '--version'], capture_output=True, check=True)
                self.print_colored(f"  ✅ {name} available", 'GREEN')
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.print_colored(f"  ❌ {name} not available", 'RED')
                sys.exit(1)
        
        # Check optional dependencies
        for cmd, name in optional_deps:
            try:
                subprocess.run([cmd, '--version'], capture_output=True, check=True)
                self.print_colored(f"  ✅ {name} available", 'GREEN')
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.print_colored(f"  ⚠️  {name} not available (optional)", 'YELLOW')
    
    def install_dependencies(self):
        """Install Python test dependencies"""
        self.print_colored("📦 Installing test dependencies...", 'BLUE')
        
        try:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', 'tests/requirements-test.txt'
            ], check=True, capture_output=True)
            self.print_colored("✅ Dependencies installed successfully", 'GREEN')
        except subprocess.CalledProcessError as e:
            self.print_colored("❌ Failed to install dependencies", 'RED')
            print(e.stderr.decode())
            sys.exit(1)
        
        print()
    
    def run_test_suite(self, suite_name: str, suite_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test suite"""
        start_time = time.time()
        
        self.print_colored(f"🏃 Running {suite_config['name']}", 'BLUE')
        
        try:
            result = subprocess.run(
                suite_config['command'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                self.print_colored(f"✅ {suite_config['name']} PASSED ({duration:.1f}s)", 'GREEN')
                status = 'PASSED'
            else:
                self.print_colored(f"❌ {suite_config['name']} FAILED ({duration:.1f}s)", 'RED')
                if result.stderr:
                    self.print_colored(f"Error: {result.stderr}", 'RED')
                status = 'FAILED'
            
            return {
                'suite': suite_name,
                'name': suite_config['name'],
                'status': status,
                'duration': duration,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'critical': suite_config.get('critical', False)
            }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.print_colored(f"⏰ {suite_config['name']} TIMEOUT ({duration:.1f}s)", 'YELLOW')
            return {
                'suite': suite_name,
                'name': suite_config['name'],
                'status': 'TIMEOUT',
                'duration': duration,
                'returncode': -1,
                'critical': suite_config.get('critical', False)
            }
        except Exception as e:
            duration = time.time() - start_time
            self.print_colored(f"💥 {suite_config['name']} ERROR: {str(e)}", 'RED')
            return {
                'suite': suite_name,
                'name': suite_config['name'],
                'status': 'ERROR',
                'duration': duration,
                'returncode': -2,
                'error': str(e),
                'critical': suite_config.get('critical', False)
            }
    
    def run_tests_sequential(self, suites: List[str]) -> List[Dict[str, Any]]:
        """Run tests sequentially"""
        results = []
        
        for suite_name in suites:
            if suite_name not in self.test_suites:
                self.print_colored(f"⚠️  Unknown test suite: {suite_name}", 'YELLOW')
                continue
            
            result = self.run_test_suite(suite_name, self.test_suites[suite_name])
            results.append(result)
            
            # Stop on critical test failure
            if result['status'] in ['FAILED', 'ERROR'] and result['critical']:
                self.print_colored(f"🛑 Critical test failed: {result['name']}", 'RED')
                if input("Continue with remaining tests? (y/N): ").lower() != 'y':
                    break
        
        return results
    
    def run_tests_parallel(self, suites: List[str], max_workers: int = 4) -> List[Dict[str, Any]]:
        """Run tests in parallel"""
        self.print_colored(f"🚀 Running tests in parallel (max {max_workers} workers)", 'BLUE')
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_suite = {}
            
            for suite_name in suites:
                if suite_name not in self.test_suites:
                    self.print_colored(f"⚠️  Unknown test suite: {suite_name}", 'YELLOW')
                    continue
                
                future = executor.submit(
                    self.run_test_suite,
                    suite_name,
                    self.test_suites[suite_name]
                )
                future_to_suite[future] = suite_name
            
            for future in concurrent.futures.as_completed(future_to_suite):
                result = future.result()
                results.append(result)
        
        return results
    
    def run_code_quality_checks(self) -> Dict[str, Any]:
        """Run code quality checks"""
        self.print_colored("🔍 Running code quality checks...", 'BLUE')
        
        quality_results = {}
        
        # Code formatting check
        try:
            result = subprocess.run([
                'black', '--check', '--line-length=120',
                'iot_poc/', 'lambda/', 'tests/'
            ], capture_output=True, text=True)
            quality_results['formatting'] = 'PASSED' if result.returncode == 0 else 'FAILED'
        except FileNotFoundError:
            quality_results['formatting'] = 'SKIPPED'
        
        # Linting
        try:
            result = subprocess.run([
                'flake8', 'iot_poc/', 'lambda/', 'tests/',
                '--max-line-length=120', '--extend-ignore=E203,W503'
            ], capture_output=True, text=True)
            quality_results['linting'] = 'PASSED' if result.returncode == 0 else 'FAILED'
        except FileNotFoundError:
            quality_results['linting'] = 'SKIPPED'
        
        # Security scan
        try:
            result = subprocess.run([
                'bandit', '-r', 'iot_poc/', 'lambda/',
                '-f', 'json', '-o', str(self.reports_dir / 'security.json')
            ], capture_output=True, text=True)
            quality_results['security'] = 'PASSED' if result.returncode == 0 else 'ISSUES_FOUND'
        except FileNotFoundError:
            quality_results['security'] = 'SKIPPED'
        
        return quality_results
    
    def generate_coverage_report(self) -> Dict[str, Any]:
        """Generate comprehensive coverage report"""
        self.print_colored("📊 Generating coverage report...", 'BLUE')
        
        try:
            result = subprocess.run([
                'pytest', 'tests/',
                '--cov=iot_poc', '--cov=lambda',
                '--cov-report=html:' + str(self.reports_dir / 'coverage_html'),
                '--cov-report=xml:' + str(self.reports_dir / 'coverage.xml'),
                '--cov-report=term-missing',
                '--cov-fail-under=80'
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                self.print_colored("✅ Coverage report generated", 'GREEN')
                coverage_status = 'PASSED'
            else:
                self.print_colored("⚠️  Coverage below threshold", 'YELLOW')
                coverage_status = 'LOW_COVERAGE'
            
            return {
                'status': coverage_status,
                'html_report': str(self.reports_dir / 'coverage_html' / 'index.html'),
                'xml_report': str(self.reports_dir / 'coverage.xml')
            }
            
        except Exception as e:
            self.print_colored(f"❌ Coverage generation failed: {str(e)}", 'RED')
            return {'status': 'FAILED', 'error': str(e)}
    
    def generate_comprehensive_report(self, test_results: List[Dict[str, Any]], 
                                    quality_results: Dict[str, Any], 
                                    coverage_results: Dict[str, Any]) -> str:
        """Generate comprehensive test report"""
        self.print_colored("📋 Generating comprehensive report...", 'BLUE')
        
        try:
            from tests.test_summary_generator import TestSummaryGenerator
            
            generator = TestSummaryGenerator(str(self.reports_dir))
            summary = generator.generate_summary()
            
            # Generate HTML report
            html_file = generator.generate_html_report()
            
            # Save detailed results
            detailed_results = {
                'timestamp': datetime.now().isoformat(),
                'test_results': test_results,
                'quality_results': quality_results,
                'coverage_results': coverage_results,
                'summary': summary
            }
            
            detailed_file = self.reports_dir / 'detailed_results.json'
            import json
            with open(detailed_file, 'w') as f:
                json.dump(detailed_results, f, indent=2)
            
            self.print_colored(f"✅ Comprehensive report generated: {html_file}", 'GREEN')
            return html_file
            
        except Exception as e:
            self.print_colored(f"❌ Report generation failed: {str(e)}", 'RED')
            return ""
    
    def print_final_summary(self, test_results: List[Dict[str, Any]], 
                          quality_results: Dict[str, Any], 
                          coverage_results: Dict[str, Any]):
        """Print final test summary"""
        print("\n" + "="*80)
        self.print_colored("🏁 FINAL TEST SUMMARY", 'WHITE')
        print("="*80)
        
        # Test results summary
        total_tests = len(test_results)
        passed_tests = len([r for r in test_results if r['status'] == 'PASSED'])
        failed_tests = len([r for r in test_results if r['status'] in ['FAILED', 'ERROR']])
        
        self.print_colored(f"📊 Test Suites: {passed_tests}/{total_tests} passed", 
                          'GREEN' if failed_tests == 0 else 'RED')
        
        # Quality results
        self.print_colored("🔍 Code Quality:", 'BLUE')
        for check, status in quality_results.items():
            color = 'GREEN' if status == 'PASSED' else 'YELLOW' if status == 'SKIPPED' else 'RED'
            self.print_colored(f"  {check.title()}: {status}", color)
        
        # Coverage results
        coverage_status = coverage_results.get('status', 'UNKNOWN')
        color = 'GREEN' if coverage_status == 'PASSED' else 'YELLOW' if 'LOW' in coverage_status else 'RED'
        self.print_colored(f"📈 Coverage: {coverage_status}", color)
        
        # Overall status
        if failed_tests == 0 and coverage_status == 'PASSED':
            self.print_colored("🎉 ALL TESTS PASSED!", 'GREEN')
            overall_status = 0
        elif failed_tests == 0:
            self.print_colored("⚠️  TESTS PASSED WITH WARNINGS", 'YELLOW')
            overall_status = 1
        else:
            self.print_colored("❌ TESTS FAILED", 'RED')
            overall_status = 2
        
        # Execution time
        total_time = sum(r.get('duration', 0) for r in test_results)
        self.print_colored(f"⏱️  Total execution time: {total_time:.1f}s", 'BLUE')
        
        print("="*80)
        return overall_status


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Ultimate IoT Platform Test Runner")
    parser.add_argument('suites', nargs='*', default=['all'], 
                       help='Test suites to run (default: all)')
    parser.add_argument('--fast', action='store_true', 
                       help='Run only fast tests')
    parser.add_argument('--critical', action='store_true',
                       help='Run only critical tests')
    parser.add_argument('--parallel', '-p', action='store_true',
                       help='Run tests in parallel')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Maximum parallel workers (default: 4)')
    parser.add_argument('--no-deps', action='store_true',
                       help='Skip dependency installation')
    parser.add_argument('--no-quality', action='store_true',
                       help='Skip code quality checks')
    parser.add_argument('--no-coverage', action='store_true',
                       help='Skip coverage report generation')
    parser.add_argument('--open-report', action='store_true',
                       help='Open HTML report in browser')
    
    args = parser.parse_args()
    
    runner = UltimateTestRunner()
    runner.print_banner()
    
    # Setup environment
    runner.setup_environment()
    
    # Install dependencies
    if not args.no_deps:
        runner.install_dependencies()
    
    # Determine which test suites to run
    if 'all' in args.suites:
        suites = list(runner.test_suites.keys())
    else:
        suites = args.suites
    
    # Filter suites based on options
    if args.fast:
        suites = [s for s in suites if runner.test_suites.get(s, {}).get('fast', False)]
    
    if args.critical:
        suites = [s for s in suites if runner.test_suites.get(s, {}).get('critical', False)]
    
    # Run tests
    start_time = time.time()
    
    if args.parallel:
        test_results = runner.run_tests_parallel(suites, args.max_workers)
    else:
        test_results = runner.run_tests_sequential(suites)
    
    # Run code quality checks
    if not args.no_quality:
        quality_results = runner.run_code_quality_checks()
    else:
        quality_results = {}
    
    # Generate coverage report
    if not args.no_coverage:
        coverage_results = runner.generate_coverage_report()
    else:
        coverage_results = {}
    
    # Generate comprehensive report
    html_report = runner.generate_comprehensive_report(test_results, quality_results, coverage_results)
    
    # Print final summary
    exit_code = runner.print_final_summary(test_results, quality_results, coverage_results)
    
    # Open report in browser if requested
    if args.open_report and html_report:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(html_report)}")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 