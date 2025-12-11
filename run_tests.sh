#!/bin/bash
# Test runner script for Architecture Decisions backend tests

set -e

echo "=== Architecture Decisions Test Runner ==="
echo ""

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "✗ Virtual environment not found at .venv/"
    echo "  Please create it with: python -m venv .venv"
    exit 1
fi

# Check if dependencies are installed
echo ""
echo "Checking dependencies..."
python -c "import flask; import flask_sqlalchemy; import pytest" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ All dependencies installed"
else
    echo "✗ Missing dependencies. Installing from requirements.txt..."
    pip install -r requirements.txt
    pip install pytest pytest-cov
    echo "✓ Dependencies installed"
fi

echo ""
echo "=== Running Tests ==="
echo ""

# Run tests with options
if [ -z "$1" ]; then
    # No arguments - run all tests
    python -m pytest tests/ -v
elif [ "$1" == "--coverage" ]; then
    # Coverage report
    python -m pytest tests/ --cov=. --cov-report=html --cov-report=term
    echo ""
    echo "Coverage report generated in htmlcov/index.html"
elif [ "$1" == "--quick" ]; then
    # Quick run - no verbose
    python -m pytest tests/
elif [ "$1" == "--help" ]; then
    echo "Usage: ./run_tests.sh [option]"
    echo ""
    echo "Options:"
    echo "  (none)       Run all tests with verbose output"
    echo "  --coverage   Run tests with coverage report"
    echo "  --quick      Run tests without verbose output"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_tests.sh                    # Run all tests"
    echo "  ./run_tests.sh --coverage         # Generate coverage report"
    echo "  pytest tests/test_auth.py -v      # Run specific test file"
    echo "  pytest tests/ -k 'test_maturity'  # Run tests matching pattern"
else
    # Pass through other arguments to pytest
    python -m pytest "$@"
fi

echo ""
echo "=== Tests Complete ==="
