#!/usr/bin/env python3
"""
IoT Platform Test Summary Generator
Generates comprehensive test reports and coverage analysis
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
import argparse


class TestSummaryGenerator:
    """Generate comprehensive test summaries and reports"""
    
    def __init__(self, reports_dir: str = "tests/reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        self.summary_data = {
            "timestamp": datetime.now().isoformat(),
            "test_suites": {},
            "coverage": {},
            "performance": {},
            "quality": {},
            "infrastructure": {},
            "overall_status": "unknown"
        }
    
    def collect_pytest_results(self) -> Dict[str, Any]:
        """Collect pytest results from XML files"""
        pytest_results = {}
        
        # Look for JUnit XML files
        xml_files = list(self.reports_dir.glob("*_tests.xml"))
        
        for xml_file in xml_files:
            suite_name = xml_file.stem.replace("_tests", "")
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                pytest_results[suite_name] = {
                    "total_tests": int(root.get("tests", 0)),
                    "failures": int(root.get("failures", 0)),
                    "errors": int(root.get("errors", 0)),
                    "skipped": int(root.get("skipped", 0)),
                    "time": float(root.get("time", 0)),
                    "status": "passed" if int(root.get("failures", 0)) == 0 and int(root.get("errors", 0)) == 0 else "failed"
                }
                
                # Calculate success rate
                total = pytest_results[suite_name]["total_tests"]
                failed = pytest_results[suite_name]["failures"] + pytest_results[suite_name]["errors"]
                success_rate = ((total - failed) / total * 100) if total > 0 else 0
                pytest_results[suite_name]["success_rate"] = round(success_rate, 2)
                
            except Exception as e:
                print(f"Warning: Could not parse {xml_file}: {e}")
                pytest_results[suite_name] = {
                    "total_tests": 0,
                    "failures": 0,
                    "errors": 1,
                    "skipped": 0,
                    "time": 0,
                    "status": "error",
                    "success_rate": 0
                }
        
        return pytest_results
    
    def collect_coverage_data(self) -> Dict[str, Any]:
        """Collect coverage data from coverage reports"""
        coverage_data = {}
        
        # Try to find coverage.xml
        coverage_xml = self.reports_dir / "coverage.xml"
        if coverage_xml.exists():
            try:
                tree = ET.parse(coverage_xml)
                root = tree.getroot()
                
                # Extract overall coverage
                coverage_data["line_rate"] = float(root.get("line-rate", 0)) * 100
                coverage_data["branch_rate"] = float(root.get("branch-rate", 0)) * 100
                
                # Extract package-level coverage
                packages = {}
                for package in root.findall(".//package"):
                    package_name = package.get("name", "unknown")
                    line_rate = float(package.get("line-rate", 0)) * 100
                    branch_rate = float(package.get("branch-rate", 0)) * 100
                    
                    packages[package_name] = {
                        "line_coverage": round(line_rate, 2),
                        "branch_coverage": round(branch_rate, 2)
                    }
                
                coverage_data["packages"] = packages
                coverage_data["overall_line_coverage"] = round(coverage_data["line_rate"], 2)
                coverage_data["overall_branch_coverage"] = round(coverage_data["branch_rate"], 2)
                
            except Exception as e:
                print(f"Warning: Could not parse coverage.xml: {e}")
                coverage_data = {"error": str(e)}
        
        return coverage_data
    
    def collect_rust_test_results(self) -> Dict[str, Any]:
        """Collect Rust test results"""
        rust_results = {}
        
        rust_test_file = self.reports_dir / "rust_tests.txt"
        if rust_test_file.exists():
            try:
                with open(rust_test_file, 'r') as f:
                    content = f.read()
                
                # Parse Rust test output
                lines = content.split('\n')
                test_results = {"passed": 0, "failed": 0, "ignored": 0}
                
                for line in lines:
                    if "test result:" in line:
                        # Example: "test result: ok. 15 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "passed;":
                                test_results["passed"] = int(parts[i-1])
                            elif part == "failed;":
                                test_results["failed"] = int(parts[i-1])
                            elif part == "ignored;":
                                test_results["ignored"] = int(parts[i-1])
                
                total_tests = test_results["passed"] + test_results["failed"]
                success_rate = (test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
                
                rust_results = {
                    "total_tests": total_tests,
                    "passed": test_results["passed"],
                    "failed": test_results["failed"],
                    "ignored": test_results["ignored"],
                    "success_rate": round(success_rate, 2),
                    "status": "passed" if test_results["failed"] == 0 else "failed"
                }
                
            except Exception as e:
                print(f"Warning: Could not parse Rust test results: {e}")
                rust_results = {"error": str(e)}
        
        return rust_results
    
    def collect_performance_data(self) -> Dict[str, Any]:
        """Collect performance and benchmark data"""
        performance_data = {}
        
        # Look for benchmark results
        benchmark_file = self.reports_dir / "benchmark.json"
        if benchmark_file.exists():
            try:
                with open(benchmark_file, 'r') as f:
                    benchmark_data = json.load(f)
                
                performance_data["benchmarks"] = benchmark_data
                
                # Extract key metrics
                if "benchmarks" in benchmark_data:
                    total_benchmarks = len(benchmark_data["benchmarks"])
                    avg_time = sum(b.get("stats", {}).get("mean", 0) for b in benchmark_data["benchmarks"]) / total_benchmarks if total_benchmarks > 0 else 0
                    
                    performance_data["summary"] = {
                        "total_benchmarks": total_benchmarks,
                        "average_execution_time": round(avg_time, 4),
                        "timestamp": benchmark_data.get("datetime", "unknown")
                    }
                
            except Exception as e:
                print(f"Warning: Could not parse benchmark results: {e}")
                performance_data = {"error": str(e)}
        
        return performance_data
    
    def collect_security_data(self) -> Dict[str, Any]:
        """Collect security scan results"""
        security_data = {}
        
        # Bandit security scan results
        bandit_file = self.reports_dir / "bandit.json"
        if bandit_file.exists():
            try:
                with open(bandit_file, 'r') as f:
                    bandit_data = json.load(f)
                
                security_data["bandit"] = {
                    "total_issues": len(bandit_data.get("results", [])),
                    "high_severity": len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "HIGH"]),
                    "medium_severity": len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "MEDIUM"]),
                    "low_severity": len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "LOW"])
                }
                
            except Exception as e:
                print(f"Warning: Could not parse bandit results: {e}")
                security_data["bandit"] = {"error": str(e)}
        
        # Safety vulnerability scan results
        safety_file = self.reports_dir / "safety.json"
        if safety_file.exists():
            try:
                with open(safety_file, 'r') as f:
                    safety_data = json.load(f)
                
                security_data["safety"] = {
                    "vulnerabilities_found": len(safety_data) if isinstance(safety_data, list) else 0,
                    "report": safety_data
                }
                
            except Exception as e:
                print(f"Warning: Could not parse safety results: {e}")
                security_data["safety"] = {"error": str(e)}
        
        return security_data
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        print("🔍 Collecting test results...")
        
        # Collect all test data
        self.summary_data["test_suites"]["python"] = self.collect_pytest_results()
        self.summary_data["test_suites"]["rust"] = self.collect_rust_test_results()
        self.summary_data["coverage"] = self.collect_coverage_data()
        self.summary_data["performance"] = self.collect_performance_data()
        self.summary_data["quality"]["security"] = self.collect_security_data()
        
        # Calculate overall status
        self.summary_data["overall_status"] = self._calculate_overall_status()
        
        # Add summary statistics
        self.summary_data["summary"] = self._generate_summary_stats()
        
        return self.summary_data
    
    def _calculate_overall_status(self) -> str:
        """Calculate overall test status"""
        issues = []
        
        # Check Python tests
        python_tests = self.summary_data["test_suites"].get("python", {})
        for suite, results in python_tests.items():
            if results.get("status") == "failed":
                issues.append(f"Python {suite} tests failed")
        
        # Check Rust tests
        rust_tests = self.summary_data["test_suites"].get("rust", {})
        if rust_tests.get("status") == "failed":
            issues.append("Rust tests failed")
        
        # Check coverage
        coverage = self.summary_data["coverage"]
        if coverage.get("overall_line_coverage", 0) < 80:
            issues.append("Low test coverage")
        
        # Check security
        security = self.summary_data["quality"].get("security", {})
        bandit = security.get("bandit", {})
        if bandit.get("high_severity", 0) > 0:
            issues.append("High severity security issues found")
        
        if not issues:
            return "✅ PASSED"
        elif len(issues) <= 2:
            return "⚠️ WARNINGS"
        else:
            return "❌ FAILED"
    
    def _generate_summary_stats(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        stats = {}
        
        # Total tests
        total_tests = 0
        total_failures = 0
        
        python_tests = self.summary_data["test_suites"].get("python", {})
        for suite_results in python_tests.values():
            total_tests += suite_results.get("total_tests", 0)
            total_failures += suite_results.get("failures", 0) + suite_results.get("errors", 0)
        
        rust_tests = self.summary_data["test_suites"].get("rust", {})
        total_tests += rust_tests.get("total_tests", 0)
        total_failures += rust_tests.get("failed", 0)
        
        stats["total_tests"] = total_tests
        stats["total_failures"] = total_failures
        stats["overall_success_rate"] = round(((total_tests - total_failures) / total_tests * 100) if total_tests > 0 else 0, 2)
        
        # Coverage summary
        coverage = self.summary_data["coverage"]
        stats["coverage_percentage"] = coverage.get("overall_line_coverage", 0)
        
        # Security summary
        security = self.summary_data["quality"].get("security", {})
        bandit = security.get("bandit", {})
        stats["security_issues"] = bandit.get("total_issues", 0)
        stats["high_severity_issues"] = bandit.get("high_severity", 0)
        
        return stats
    
    def save_summary(self, filename: str = "test_summary.json") -> str:
        """Save summary to JSON file"""
        summary_file = self.reports_dir / filename
        
        with open(summary_file, 'w') as f:
            json.dump(self.summary_data, f, indent=2)
        
        print(f"📊 Test summary saved to: {summary_file}")
        return str(summary_file)
    
    def generate_html_report(self) -> str:
        """Generate HTML test report"""
        html_content = self._generate_html_content()
        html_file = self.reports_dir / "test_report.html"
        
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        print(f"📄 HTML report generated: {html_file}")
        return str(html_file)
    
    def _generate_html_content(self) -> str:
        """Generate HTML content for the report"""
        summary = self.summary_data["summary"]
        overall_status = self.summary_data["overall_status"]
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT Platform Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .status {{ font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        .status.passed {{ background-color: #d4edda; color: #155724; }}
        .status.warning {{ background-color: #fff3cd; color: #856404; }}
        .status.failed {{ background-color: #f8d7da; color: #721c24; }}
        .metric-card {{ display: inline-block; margin: 10px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; min-width: 200px; }}
        .metric-title {{ font-weight: bold; color: #495057; }}
        .metric-value {{ font-size: 24px; color: #007bff; }}
        .section {{ margin: 20px 0; }}
        .section h2 {{ color: #495057; border-bottom: 2px solid #007bff; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .success {{ color: #28a745; }}
        .warning {{ color: #ffc107; }}
        .danger {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 IoT Platform Test Report</h1>
            <p>Generated on: {self.summary_data['timestamp']}</p>
            <div class="status {overall_status.split()[1].lower() if len(overall_status.split()) > 1 else 'unknown'}">{overall_status}</div>
        </div>
        
        <div class="section">
            <h2>📊 Overview</h2>
            <div class="metric-card">
                <div class="metric-title">Total Tests</div>
                <div class="metric-value">{summary.get('total_tests', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Success Rate</div>
                <div class="metric-value">{summary.get('overall_success_rate', 0)}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Coverage</div>
                <div class="metric-value">{summary.get('coverage_percentage', 0)}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Security Issues</div>
                <div class="metric-value {'danger' if summary.get('high_severity_issues', 0) > 0 else 'success'}">{summary.get('security_issues', 0)}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🐍 Python Test Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test Suite</th>
                        <th>Total Tests</th>
                        <th>Passed</th>
                        <th>Failed</th>
                        <th>Success Rate</th>
                        <th>Duration</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        python_tests = self.summary_data["test_suites"].get("python", {})
        for suite_name, results in python_tests.items():
            status_class = "success" if results.get("status") == "passed" else "danger"
            passed = results.get("total_tests", 0) - results.get("failures", 0) - results.get("errors", 0)
            
            html += f"""
                    <tr>
                        <td>{suite_name.title()}</td>
                        <td>{results.get('total_tests', 0)}</td>
                        <td class="success">{passed}</td>
                        <td class="danger">{results.get('failures', 0) + results.get('errors', 0)}</td>
                        <td class="{status_class}">{results.get('success_rate', 0)}%</td>
                        <td>{results.get('time', 0):.2f}s</td>
                        <td class="{status_class}">{results.get('status', 'unknown').upper()}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🦀 Rust Test Results</h2>
        """
        
        rust_tests = self.summary_data["test_suites"].get("rust", {})
        if rust_tests:
            status_class = "success" if rust_tests.get("status") == "passed" else "danger"
            html += f"""
            <div class="metric-card">
                <div class="metric-title">Total Tests</div>
                <div class="metric-value">{rust_tests.get('total_tests', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Passed</div>
                <div class="metric-value success">{rust_tests.get('passed', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Failed</div>
                <div class="metric-value danger">{rust_tests.get('failed', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Success Rate</div>
                <div class="metric-value {status_class}">{rust_tests.get('success_rate', 0)}%</div>
            </div>
            """
        else:
            html += "<p>No Rust test results found.</p>"
        
        html += """
        </div>
        
        <div class="section">
            <h2>📈 Coverage Report</h2>
        """
        
        coverage = self.summary_data["coverage"]
        if coverage:
            html += f"""
            <div class="metric-card">
                <div class="metric-title">Line Coverage</div>
                <div class="metric-value">{coverage.get('overall_line_coverage', 0)}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Branch Coverage</div>
                <div class="metric-value">{coverage.get('overall_branch_coverage', 0)}%</div>
            </div>
            """
            
            packages = coverage.get("packages", {})
            if packages:
                html += """
                <table>
                    <thead>
                        <tr>
                            <th>Package</th>
                            <th>Line Coverage</th>
                            <th>Branch Coverage</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                for package, data in packages.items():
                    html += f"""
                        <tr>
                            <td>{package}</td>
                            <td>{data.get('line_coverage', 0)}%</td>
                            <td>{data.get('branch_coverage', 0)}%</td>
                        </tr>
                    """
                html += """
                    </tbody>
                </table>
                """
        else:
            html += "<p>No coverage data available.</p>"
        
        html += """
        </div>
        
        <div class="section">
            <h2>🔒 Security Analysis</h2>
        """
        
        security = self.summary_data["quality"].get("security", {})
        bandit = security.get("bandit", {})
        if bandit:
            html += f"""
            <div class="metric-card">
                <div class="metric-title">Total Issues</div>
                <div class="metric-value">{bandit.get('total_issues', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">High Severity</div>
                <div class="metric-value danger">{bandit.get('high_severity', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Medium Severity</div>
                <div class="metric-value warning">{bandit.get('medium_severity', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Low Severity</div>
                <div class="metric-value">{bandit.get('low_severity', 0)}</div>
            </div>
            """
        else:
            html += "<p>No security scan results available.</p>"
        
        html += """
        </div>
        
        <div class="section">
            <h2>⚡ Performance Metrics</h2>
        """
        
        performance = self.summary_data["performance"]
        if performance.get("summary"):
            perf_summary = performance["summary"]
            html += f"""
            <div class="metric-card">
                <div class="metric-title">Total Benchmarks</div>
                <div class="metric-value">{perf_summary.get('total_benchmarks', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Average Execution Time</div>
                <div class="metric-value">{perf_summary.get('average_execution_time', 0)}s</div>
            </div>
            """
        else:
            html += "<p>No performance data available.</p>"
        
        html += """
        </div>
        
        <footer style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #6c757d;">
            <p>Generated by IoT Platform Test Suite</p>
        </footer>
    </div>
</body>
</html>
        """
        
        return html
    
    def print_console_summary(self):
        """Print summary to console"""
        print("\n" + "="*60)
        print("🧪 IoT PLATFORM TEST SUMMARY")
        print("="*60)
        
        summary = self.summary_data["summary"]
        overall_status = self.summary_data["overall_status"]
        
        print(f"📊 Overall Status: {overall_status}")
        print(f"📈 Total Tests: {summary.get('total_tests', 0)}")
        print(f"✅ Success Rate: {summary.get('overall_success_rate', 0)}%")
        print(f"📋 Coverage: {summary.get('coverage_percentage', 0)}%")
        print(f"🔒 Security Issues: {summary.get('security_issues', 0)} (High: {summary.get('high_severity_issues', 0)})")
        
        # Python test details
        print("\n🐍 Python Tests:")
        python_tests = self.summary_data["test_suites"].get("python", {})
        for suite_name, results in python_tests.items():
            status_icon = "✅" if results.get("status") == "passed" else "❌"
            print(f"  {status_icon} {suite_name.title()}: {results.get('success_rate', 0)}% ({results.get('total_tests', 0)} tests)")
        
        # Rust test details
        rust_tests = self.summary_data["test_suites"].get("rust", {})
        if rust_tests:
            status_icon = "✅" if rust_tests.get("status") == "passed" else "❌"
            print(f"\n🦀 Rust Tests:")
            print(f"  {status_icon} Lambda: {rust_tests.get('success_rate', 0)}% ({rust_tests.get('total_tests', 0)} tests)")
        
        print("\n" + "="*60)


def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(description="Generate IoT Platform test summary")
    parser.add_argument("--reports-dir", default="tests/reports", help="Directory containing test reports")
    parser.add_argument("--output", default="test_summary.json", help="Output filename for JSON summary")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--console", action="store_true", help="Print summary to console")
    parser.add_argument("--open", action="store_true", help="Open HTML report in browser")
    
    args = parser.parse_args()
    
    # Generate summary
    generator = TestSummaryGenerator(args.reports_dir)
    summary = generator.generate_summary()
    
    # Save JSON summary
    json_file = generator.save_summary(args.output)
    
    # Generate HTML report if requested
    html_file = None
    if args.html:
        html_file = generator.generate_html_report()
    
    # Print console summary if requested
    if args.console:
        generator.print_console_summary()
    
    # Open HTML report in browser if requested
    if args.open and html_file:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(html_file)}")
    
    # Exit with appropriate code
    overall_status = summary["overall_status"]
    if "FAILED" in overall_status:
        sys.exit(1)
    elif "WARNINGS" in overall_status:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main() 