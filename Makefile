# Python Makefile for Walle

.PHONY: install clean lint test build help

# Variables
PYTHON := python3
PIP := pip3
PACKAGE_NAME := walle

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

install-dev: ## Install development dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	$(PIP) install pytest black flake8 mypy

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint: ## Run code linting
	black --check $(PACKAGE_NAME)/
	flake8 $(PACKAGE_NAME)/
	mypy $(PACKAGE_NAME)/

format: ## Format code
	black $(PACKAGE_NAME)/

test: ## Run tests
	pytest tests/

build: ## Build package
	$(PYTHON) setup.py sdist bdist_wheel

run-help: ## Show walle help
	$(PYTHON) -m $(PACKAGE_NAME).cli.main --help

run-version: ## Show walle version
	$(PYTHON) -m $(PACKAGE_NAME).cli.main version