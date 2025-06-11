#!/bin/bash
# IoT Platform Test Execution Script
# Usage: ./run_tests.sh [test_type] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
VERBOSE=""
PARALLEL=""
REPORT=""
COVERAGE=""

# Help function
show_help() {
    echo "IoT Platform Test Runner"
    echo ""
    echo "Usage: $0 [test_type] [options]"
    echo ""
    echo "Test Types:"
    echo "  unit           Run unit tests only"
    echo "  integration    Run integration tests"
    echo "  infrastructure Run CDK infrastructure tests"
    echo "  lambda         Run Lambda function tests"
    echo "  api           Run API endpoint tests"
    echo "  etl           Run ETL pipeline tests"
    echo "  e2e           Run end-to-end tests"
    echo "  performance   Run performance tests"
    echo "  rust          Run Rust Lambda tests"
    echo "  all           Run all tests (default)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose     Verbose output"
    echo "  -p, --parallel    Run tests in parallel"
    echo "  -r, --report      Generate test report"
    echo "  -c, --coverage    Generate coverage report"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 unit -v                 # Run unit tests with verbose output"
    echo "  $0 all -p -r               # Run all tests in parallel with report"
    echo "  $0 integration --coverage  # Run integration tests with coverage"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        unit|integration|infrastructure|lambda|api|etl|e2e|performance|rust|all)
            TEST_TYPE="$1"
            shift
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -p|--parallel)
            PARALLEL="-p"
            shift
            ;;
        -r|--report)
            REPORT="--report"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov=iot_poc --cov=lambda --cov-report=html:tests/reports/coverage_html --cov-report=term-missing"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🧪 IoT Platform Test Runner${NC}"
echo -e "${BLUE}==============================${NC}"
echo ""

# Check if virtual environment exists
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo -e "${GREEN}✓ Virtual environment detected: $VIRTUAL_ENV${NC}"
else
    echo -e "${YELLOW}⚠ Warning: No virtual environment detected${NC}"
    echo -e "${YELLOW}  Consider activating a virtual environment first${NC}"
fi

# Check if test dependencies are installed
echo -e "${BLUE}📦 Checking test dependencies...${NC}"
if ! python -c "import pytest, moto, boto3" 2>/dev/null; then
    echo -e "${RED}❌ Test dependencies missing. Installing...${NC}"
    pip install -r tests/requirements-test.txt
else
    echo -e "${GREEN}✓ Test dependencies installed${NC}"
fi

# Create reports directory
mkdir -p tests/reports

# Set AWS environment variables for testing
export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export AWS_SECURITY_TOKEN=testing
export AWS_SESSION_TOKEN=testing
export AWS_DEFAULT_REGION=us-east-1

echo -e "${BLUE}🚀 Running ${TEST_TYPE} tests...${NC}"

# Build command
if [[ -n "$COVERAGE" ]]; then
    # Use pytest directly for coverage
    CMD="python -m pytest tests/ $COVERAGE"
    
    if [[ "$TEST_TYPE" != "all" ]]; then
        case $TEST_TYPE in
            unit)
                CMD="$CMD -m unit"
                ;;
            integration)
                CMD="$CMD -m integration"
                ;;
            infrastructure)
                CMD="$CMD tests/test_infrastructure.py"
                ;;
            lambda)
                CMD="$CMD tests/test_lambda_functions.py"
                ;;
            api)
                CMD="$CMD tests/test_api_endpoints.py"
                ;;
            etl)
                CMD="$CMD tests/test_glue_etl.py"
                ;;
            e2e)
                CMD="$CMD -m e2e"
                ;;
            performance)
                CMD="$CMD -m slow"
                ;;
        esac
    fi
    
    if [[ -n "$VERBOSE" ]]; then
        CMD="$CMD -v"
    fi
    
    if [[ -n "$PARALLEL" ]]; then
        CMD="$CMD -n auto"
    fi
else
    # Use test runner
    CMD="python tests/test_runner.py $TEST_TYPE $VERBOSE $PARALLEL $REPORT"
fi

# Run the tests
echo -e "${YELLOW}Executing: $CMD${NC}"
echo ""

START_TIME=$(date +%s)

if eval $CMD; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo ""
    echo -e "${GREEN}✅ Tests completed successfully in ${DURATION}s${NC}"
    
    # Show coverage report location if generated
    if [[ -n "$COVERAGE" ]]; then
        echo -e "${GREEN}📊 Coverage report: tests/reports/coverage_html/index.html${NC}"
    fi
    
    # Show test report location if generated
    if [[ -n "$REPORT" ]]; then
        echo -e "${GREEN}📋 Test report: tests/reports/test_report.json${NC}"
    fi
    
    EXIT_CODE=0
else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo ""
    echo -e "${RED}❌ Tests failed after ${DURATION}s${NC}"
    EXIT_CODE=1
fi

# Optional: Open coverage report in browser (macOS/Linux)
if [[ -n "$COVERAGE" && $EXIT_CODE -eq 0 ]]; then
    read -p "Open coverage report in browser? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v open >/dev/null 2>&1; then
            open tests/reports/coverage_html/index.html
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open tests/reports/coverage_html/index.html
        else
            echo "Cannot open browser automatically. Open tests/reports/coverage_html/index.html manually."
        fi
    fi
fi

echo ""
echo -e "${BLUE}📁 Test artifacts location: tests/reports/${NC}"
echo -e "${BLUE}🔍 For detailed logs, check individual test output files${NC}"

exit $EXIT_CODE 