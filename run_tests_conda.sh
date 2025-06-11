#!/bin/bash

# IoT Platform Test Runner with Conda Support
# This script provides a convenient way to run tests in conda environment

set -e

# Default values
TEST_TYPE="all"
VERBOSE=""
PARALLEL=""
REPORT=""
CONDA_ENV=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
show_usage() {
    echo -e "${BLUE}IoT Platform Test Runner with Conda Support${NC}"
    echo
    echo "Usage: $0 [OPTIONS] [TEST_TYPE]"
    echo
    echo "Test Types:"
    echo "  unit               Run unit tests only"
    echo "  integration        Run integration tests only" 
    echo "  e2e                Run end-to-end tests"
    echo "  infrastructure     Run infrastructure/CDK tests"
    echo "  lambda             Run Lambda function tests"
    echo "  api                Run API endpoint tests"
    echo "  etl                Run ETL pipeline tests"
    echo "  all                Run all tests (default)"
    echo "  performance        Run performance tests"
    echo ""
    echo "  monitoring         Run monitoring tests"
    echo "  performance-extended Run extended performance tests"
    echo "  info               Show conda environment information"
    echo
    echo "Options:"
    echo "  -h, --help         Show this help message"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -p, --parallel     Run tests in parallel"
    echo "  -r, --report       Generate test report"
    echo "  -e, --env ENV      Specify conda environment name"
    echo "  --setup            Setup conda environment with required packages"
    echo
    echo "Examples:"
    echo "  $0                           # Run all tests"
    echo "  $0 unit -v                   # Run unit tests with verbose output"
    echo "  $0 all -p -r                 # Run all tests in parallel with report"
    echo "  $0 --env myenv unit          # Run unit tests in specific conda env"
    echo "  $0 --setup                   # Setup conda environment"
    echo "  $0 info                      # Show environment information"
}

# Function to setup conda environment
setup_conda_env() {
    echo -e "${BLUE}🔧 Setting up conda environment for IoT platform testing${NC}"
    
    # Check if conda is available
    if ! command -v conda &> /dev/null; then
        echo -e "${RED}❌ Conda not found. Please install conda first.${NC}"
        exit 1
    fi
    
    ENV_NAME=${CONDA_ENV:-"iot-testing"}
    
    echo -e "${YELLOW}📦 Creating conda environment: ${ENV_NAME}${NC}"
    
    # Create environment with Python 3.9
    conda create -n "$ENV_NAME" python=3.9 -y
    
    echo -e "${YELLOW}📥 Installing testing dependencies...${NC}"
    
    # Activate environment and install packages
    eval "$(conda shell.bash hook)"
    conda activate "$ENV_NAME"
    
    # Install Python testing packages
    pip install -r requirements.txt
    pip install pytest pytest-cov pytest-xdist pytest-mock pytest-benchmark
    pip install moto[all] # For AWS mocking
    
    echo -e "${GREEN}✅ Conda environment '${ENV_NAME}' setup complete!${NC}"
    echo -e "${BLUE}💡 To activate: conda activate ${ENV_NAME}${NC}"
    echo -e "${BLUE}💡 To run tests: $0 --env ${ENV_NAME} all${NC}"
}

# Function to check conda environment
check_conda() {
    if ! command -v conda &> /dev/null; then
        echo -e "${YELLOW}⚠️  Conda not found. Running with system Python.${NC}"
        return 1
    fi
    
    # Check if we're in a conda environment
    if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
        echo -e "${GREEN}🐍 Active conda environment: $CONDA_DEFAULT_ENV${NC}"
    else
        echo -e "${YELLOW}⚠️  No active conda environment. Consider activating one.${NC}"
    fi
    
    return 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -p|--parallel)
            PARALLEL="--parallel"
            shift
            ;;
        -r|--report)
            REPORT="--report"
            shift
            ;;
        -e|--env)
            CONDA_ENV="$2"
            shift 2
            ;;
        --setup)
            setup_conda_env
            exit 0
            ;;
        unit|integration|e2e|infrastructure|lambda|api|etl|all|performance|monitoring|performance-extended|info)
            TEST_TYPE="$1"
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Check conda environment
check_conda

# Build command arguments
ARGS="$TEST_TYPE"

if [[ -n "$VERBOSE" ]]; then
    ARGS="$ARGS $VERBOSE"
fi

if [[ -n "$PARALLEL" ]]; then
    ARGS="$ARGS $PARALLEL"
fi

if [[ -n "$REPORT" ]]; then
    ARGS="$ARGS $REPORT"
fi

if [[ -n "$CONDA_ENV" ]]; then
    ARGS="$ARGS --conda-env $CONDA_ENV"
fi

# Show what we're about to run
echo -e "${BLUE}🚀 Running IoT Platform Tests${NC}"
echo -e "${BLUE}Command: python tests/test_runner.py $ARGS${NC}"
echo

# Check if test runner exists
if [[ ! -f "tests/test_runner.py" ]]; then
    echo -e "${RED}❌ Test runner not found: tests/test_runner.py${NC}"
    echo -e "${YELLOW}💡 Make sure you're in the project root directory${NC}"
    exit 1
fi

# Run the test runner
python tests/test_runner.py $ARGS

# Capture exit code
EXIT_CODE=$?

# Show results
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "\n${GREEN}✅ Tests completed successfully!${NC}"
else
    echo -e "\n${RED}❌ Tests failed with exit code: $EXIT_CODE${NC}"
fi

# Show reports location if report was generated
if [[ -n "$REPORT" ]]; then
    echo -e "${BLUE}📊 Test reports available in: tests/reports/${NC}"
fi

exit $EXIT_CODE 