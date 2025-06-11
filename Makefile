# IoT Platform Development and Testing Makefile
.PHONY: help install install-dev clean test test-unit test-integration test-infrastructure test-api test-etl test-rust test-all coverage lint format pre-commit deploy ci docker-build docker-run docs security-scan

# Default target
.DEFAULT_GOAL := help

# Colors for output
BOLD := \033[1m
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

# Environment variables
PYTHON := python3
PIP := pip3
AWS_REGION := us-east-1
CDK_VERSION := latest

# Project paths
PROJECT_ROOT := $(shell pwd)
TESTS_DIR := $(PROJECT_ROOT)/tests
REPORTS_DIR := $(TESTS_DIR)/reports
RUST_DIR := $(PROJECT_ROOT)/rust-lambda

help: ## Show this help message
	@echo "$(BOLD)IoT Platform Development Commands$(RESET)"
	@echo ""
	@echo "$(BLUE)Setup:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; target="setup"} /^[a-zA-Z_-]+:.*?##/ { if ($$0 ~ target) printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | grep -v "grep"
	@echo ""
	@echo "$(BLUE)Testing:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; target="test"} /^[a-zA-Z_-]+:.*?##/ { if ($$0 ~ target) printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | grep -v "grep"
	@echo ""
	@echo "$(BLUE)Code Quality:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; target="quality"} /^[a-zA-Z_-]+:.*?##/ { if ($$0 ~ target) printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | grep -v "grep"
	@echo ""
	@echo "$(BLUE)Deployment:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; target="deploy"} /^[a-zA-Z_-]+:.*?##/ { if ($$0 ~ target) printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | grep -v "grep"
	@echo ""
	@echo "$(BLUE)Development:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; target="dev"} /^[a-zA-Z_-]+:.*?##/ { if ($$0 ~ target) printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | grep -v "grep"

# Setup targets
install: ## setup: Install production dependencies
	@echo "$(BLUE)📦 Installing production dependencies...$(RESET)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Production dependencies installed$(RESET)"

install-dev: install ## setup: Install development and testing dependencies
	@echo "$(BLUE)📦 Installing development dependencies...$(RESET)"
	$(PIP) install -r tests/requirements-test.txt
	npm install -g aws-cdk@$(CDK_VERSION)
	@if [ -d "$(RUST_DIR)" ]; then \
		echo "$(BLUE)📦 Installing Rust dependencies...$(RESET)"; \
		cd $(RUST_DIR) && cargo build; \
	fi
	@echo "$(GREEN)✅ Development dependencies installed$(RESET)"

clean: ## setup: Clean build artifacts and cache
	@echo "$(BLUE)🧹 Cleaning build artifacts...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf $(REPORTS_DIR)/*
	rm -rf dist/
	rm -rf build/
	@if [ -d "$(RUST_DIR)" ]; then \
		echo "$(BLUE)🧹 Cleaning Rust artifacts...$(RESET)"; \
		cd $(RUST_DIR) && cargo clean; \
	fi
	@echo "$(GREEN)✅ Cleanup completed$(RESET)"

# Testing targets
test-unit: ## test: Run unit tests only (fast)
	@echo "$(BLUE)🧪 Running unit tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py unit -v
	@echo "$(GREEN)✅ Unit tests completed$(RESET)"

test-integration: ## test: Run integration tests
	@echo "$(BLUE)🧪 Running integration tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py integration -v
	@echo "$(GREEN)✅ Integration tests completed$(RESET)"

test-infrastructure: ## test: Run CDK infrastructure tests
	@echo "$(BLUE)🧪 Running infrastructure tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py infrastructure -v
	@echo "$(GREEN)✅ Infrastructure tests completed$(RESET)"

test-api: ## test: Run API endpoint tests
	@echo "$(BLUE)🧪 Running API tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py api -v
	@echo "$(GREEN)✅ API tests completed$(RESET)"

test-etl: ## test: Run ETL pipeline tests
	@echo "$(BLUE)🧪 Running ETL tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py etl -v
	@echo "$(GREEN)✅ ETL tests completed$(RESET)"

test-rust: ## test: Run Rust Lambda tests
	@echo "$(BLUE)🧪 Running Rust tests...$(RESET)"
	@if [ -d "$(RUST_DIR)" ]; then \
		cd $(RUST_DIR) && cargo test --verbose; \
		echo "$(GREEN)✅ Rust tests completed$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️  Rust directory not found, skipping Rust tests$(RESET)"; \
	fi

test-performance: ## test: Run performance and benchmark tests
	@echo "$(BLUE)🧪 Running performance tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py performance -v
	@echo "$(GREEN)✅ Performance tests completed$(RESET)"

test-e2e: ## test: Run end-to-end tests (slow)
	@echo "$(BLUE)🧪 Running end-to-end tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	pytest tests/ -m e2e -v --tb=short
	@echo "$(GREEN)✅ End-to-end tests completed$(RESET)"

test: test-unit test-integration ## test: Run unit and integration tests (default)

test-all: ## test: Run all tests including slow ones
	@echo "$(BLUE)🧪 Running all tests...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py all -v
	@if [ -d "$(RUST_DIR)" ]; then \
		cd $(RUST_DIR) && cargo test; \
	fi
	@echo "$(GREEN)✅ All tests completed$(RESET)"

test-parallel: ## test: Run all tests in parallel (faster)
	@echo "$(BLUE)🧪 Running tests in parallel...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	$(PYTHON) tests/test_runner.py all -p -v
	@echo "$(GREEN)✅ Parallel tests completed$(RESET)"

test-watch: ## test: Run tests in watch mode (re-run on file changes)
	@echo "$(BLUE)👀 Running tests in watch mode...$(RESET)"
	pytest-watch tests/ -- -v

coverage: ## test: Generate test coverage report
	@echo "$(BLUE)📊 Generating coverage report...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	pytest tests/ \
		--cov=iot_poc \
		--cov=lambda \
		--cov-report=html:$(REPORTS_DIR)/coverage_html \
		--cov-report=xml:$(REPORTS_DIR)/coverage.xml \
		--cov-report=term-missing \
		--cov-fail-under=85
	@echo "$(GREEN)📊 Coverage report generated: $(REPORTS_DIR)/coverage_html/index.html$(RESET)"

# Code quality targets
lint: ## quality: Run code linting and static analysis
	@echo "$(BLUE)🔍 Running code analysis...$(RESET)"
	@echo "$(BLUE)  - Running flake8...$(RESET)"
	flake8 iot_poc/ lambda/ tests/ --max-line-length=120 --extend-ignore=E203,W503
	@echo "$(BLUE)  - Running pylint...$(RESET)"
	pylint iot_poc/ lambda/ --rcfile=.pylintrc || true
	@echo "$(BLUE)  - Running mypy...$(RESET)"
	mypy iot_poc/ lambda/ --ignore-missing-imports || true
	@echo "$(BLUE)  - Running bandit security scan...$(RESET)"
	bandit -r iot_poc/ lambda/ -f json -o $(REPORTS_DIR)/security.json || true
	@if [ -d "$(RUST_DIR)" ]; then \
		echo "$(BLUE)  - Running Rust clippy...$(RESET)"; \
		cd $(RUST_DIR) && cargo clippy -- -D warnings || true; \
	fi
	@echo "$(GREEN)✅ Code analysis completed$(RESET)"

format: ## quality: Format code using black and isort
	@echo "$(BLUE)🎨 Formatting code...$(RESET)"
	black iot_poc/ lambda/ tests/ --line-length=120
	isort iot_poc/ lambda/ tests/ --profile black --line-length=120
	@if [ -d "$(RUST_DIR)" ]; then \
		echo "$(BLUE)🎨 Formatting Rust code...$(RESET)"; \
		cd $(RUST_DIR) && cargo fmt; \
	fi
	@echo "$(GREEN)✅ Code formatting completed$(RESET)"

format-check: ## quality: Check if code is properly formatted
	@echo "$(BLUE)🎨 Checking code format...$(RESET)"
	black --check iot_poc/ lambda/ tests/ --line-length=120
	isort --check-only iot_poc/ lambda/ tests/ --profile black --line-length=120
	@if [ -d "$(RUST_DIR)" ]; then \
		cd $(RUST_DIR) && cargo fmt -- --check; \
	fi
	@echo "$(GREEN)✅ Code format check passed$(RESET)"

security-scan: ## quality: Run security vulnerability scan
	@echo "$(BLUE)🔒 Running security scan...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	safety check --json --output $(REPORTS_DIR)/safety.json || true
	bandit -r iot_poc/ lambda/ -f json -o $(REPORTS_DIR)/bandit.json || true
	@echo "$(GREEN)✅ Security scan completed$(RESET)"

pre-commit: format lint test-unit ## quality: Run pre-commit checks (format, lint, unit tests)
	@echo "$(GREEN)✅ Pre-commit checks completed$(RESET)"

# Deployment targets
cdk-synth: ## deploy: Synthesize CDK app
	@echo "$(BLUE)🏗️  Synthesizing CDK app...$(RESET)"
	cdk synth
	@echo "$(GREEN)✅ CDK synthesis completed$(RESET)"

cdk-diff: ## deploy: Show CDK diff
	@echo "$(BLUE)🔍 Showing CDK diff...$(RESET)"
	cdk diff

cdk-deploy: ## deploy: Deploy CDK app
	@echo "$(BLUE)🚀 Deploying CDK app...$(RESET)"
	cdk deploy --require-approval never
	@echo "$(GREEN)✅ CDK deployment completed$(RESET)"

cdk-destroy: ## deploy: Destroy CDK app
	@echo "$(BLUE)💥 Destroying CDK app...$(RESET)"
	cdk destroy --force
	@echo "$(GREEN)✅ CDK destruction completed$(RESET)"

deploy-dev: cdk-synth test-infrastructure cdk-deploy ## deploy: Deploy to development environment
	@echo "$(GREEN)✅ Development deployment completed$(RESET)"

# Development targets
dev-setup: install-dev ## dev: Setup development environment
	@echo "$(BLUE)🔧 Setting up development environment...$(RESET)"
	@if [ ! -f .env ]; then \
		echo "$(BLUE)📝 Creating .env file...$(RESET)"; \
		cp .env.example .env 2>/dev/null || echo "# Development environment variables" > .env; \
	fi
	@echo "$(GREEN)✅ Development environment setup completed$(RESET)"

dev-run: ## dev: Run local development server
	@echo "$(BLUE)🚀 Starting development server...$(RESET)"
	$(PYTHON) -m lambda.api_integration

dev-logs: ## dev: Show development logs
	@echo "$(BLUE)📋 Showing logs...$(RESET)"
	tail -f logs/*.log 2>/dev/null || echo "No log files found"

# Docker targets
docker-build: ## dev: Build Docker images
	@echo "$(BLUE)🐳 Building Docker images...$(RESET)"
	docker build -t iot-platform:latest .
	@echo "$(GREEN)✅ Docker build completed$(RESET)"

docker-run: ## dev: Run application in Docker
	@echo "$(BLUE)🐳 Running Docker container...$(RESET)"
	docker run -p 8080:8080 iot-platform:latest

docker-test: ## dev: Run tests in Docker
	@echo "$(BLUE)🐳 Running tests in Docker...$(RESET)"
	docker build -f Dockerfile.test -t iot-platform-test:latest .
	docker run --rm iot-platform-test:latest

# Documentation
docs-build: ## dev: Build documentation
	@echo "$(BLUE)📚 Building documentation...$(RESET)"
	@if [ -f docs/Makefile ]; then \
		cd docs && make html; \
	else \
		echo "$(YELLOW)⚠️  Documentation directory not found$(RESET)"; \
	fi

docs-serve: ## dev: Serve documentation locally
	@echo "$(BLUE)📚 Serving documentation...$(RESET)"
	@if [ -d docs/_build/html ]; then \
		cd docs/_build/html && $(PYTHON) -m http.server 8000; \
	else \
		echo "$(YELLOW)⚠️  Build documentation first with: make docs-build$(RESET)"; \
	fi

# CI/CD simulation
ci: clean install-dev format-check lint test-all coverage security-scan ## deploy: Run full CI pipeline
	@echo "$(BLUE)🚀 Running full CI pipeline...$(RESET)"
	@if [ -f $(REPORTS_DIR)/coverage.xml ]; then \
		echo "$(GREEN)📊 Coverage report generated$(RESET)"; \
	fi
	@if [ -f $(REPORTS_DIR)/security.json ]; then \
		echo "$(GREEN)🔒 Security report generated$(RESET)"; \
	fi
	@echo "$(GREEN)✅ CI pipeline completed successfully$(RESET)"

ci-fast: clean install-dev format-check lint test coverage ## deploy: Run fast CI pipeline (no slow tests)
	@echo "$(GREEN)✅ Fast CI pipeline completed$(RESET)"

# Utility targets
check-deps: ## dev: Check for dependency updates
	@echo "$(BLUE)📦 Checking for dependency updates...$(RESET)"
	pip list --outdated
	@if [ -d "$(RUST_DIR)" ]; then \
		cd $(RUST_DIR) && cargo outdated; \
	fi

update-deps: ## dev: Update dependencies
	@echo "$(BLUE)📦 Updating dependencies...$(RESET)"
	pip install --upgrade pip
	pip install --upgrade -r requirements.txt
	pip install --upgrade -r tests/requirements-test.txt

benchmark: ## test: Run performance benchmarks
	@echo "$(BLUE)⚡ Running performance benchmarks...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	pytest tests/ -m slow --benchmark-only --benchmark-json=$(REPORTS_DIR)/benchmark.json
	@echo "$(GREEN)✅ Benchmarks completed$(RESET)"

profile: ## dev: Profile application performance
	@echo "$(BLUE)📊 Profiling application...$(RESET)"
	$(PYTHON) -m cProfile -o $(REPORTS_DIR)/profile.stats lambda/processor.py

# Report viewing
view-coverage: ## dev: Open coverage report in browser
	@if [ -f $(REPORTS_DIR)/coverage_html/index.html ]; then \
		open $(REPORTS_DIR)/coverage_html/index.html || xdg-open $(REPORTS_DIR)/coverage_html/index.html; \
	else \
		echo "$(YELLOW)⚠️  Generate coverage report first with: make coverage$(RESET)"; \
	fi

view-reports: ## dev: Open all reports in browser
	@echo "$(BLUE)📊 Opening test reports...$(RESET)"
	@for report in $(REPORTS_DIR)/*.html; do \
		if [ -f "$$report" ]; then \
			open "$$report" || xdg-open "$$report"; \
		fi; \
	done

# Status and information
status: ## dev: Show project status and information
	@echo "$(BOLD)📊 IoT Platform Status$(RESET)"
	@echo ""
	@echo "$(BLUE)Project Structure:$(RESET)"
	@find . -type f -name "*.py" | head -10
	@echo "..."
	@echo ""
	@echo "$(BLUE)Test Coverage:$(RESET)"
	@if [ -f $(REPORTS_DIR)/coverage.xml ]; then \
		grep -o 'line-rate="[^"]*"' $(REPORTS_DIR)/coverage.xml | head -1; \
	else \
		echo "No coverage data available"; \
	fi
	@echo ""
	@echo "$(BLUE)Recent Test Results:$(RESET)"
	@if [ -f $(REPORTS_DIR)/all_tests.xml ]; then \
		grep -o 'tests="[^"]*"' $(REPORTS_DIR)/all_tests.xml | head -1; \
	else \
		echo "No test results available"; \
	fi

# Cleanup and reset
reset: clean ## dev: Reset project to clean state
	@echo "$(BLUE)🔄 Resetting project...$(RESET)"
	git clean -fdx
	@echo "$(GREEN)✅ Project reset completed$(RESET)"

# Version information
version: ## dev: Show version information
	@echo "$(BOLD)📋 Version Information$(RESET)"
	@echo "Python: $(shell python --version)"
	@echo "pip: $(shell pip --version)"
	@echo "CDK: $(shell cdk --version 2>/dev/null || echo 'Not installed')"
	@if [ -d "$(RUST_DIR)" ]; then \
		echo "Rust: $(shell rustc --version 2>/dev/null || echo 'Not installed')"; \
		echo "Cargo: $(shell cargo --version 2>/dev/null || echo 'Not installed')"; \
	fi
	@echo "AWS CLI: $(shell aws --version 2>/dev/null || echo 'Not installed')" 