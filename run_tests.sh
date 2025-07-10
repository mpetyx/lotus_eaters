#!/bin/bash
# Run tests for lotus_eaters library

# Use virtual environment if it exists
if [ -d "venv" ]; then
    PYTHON="./venv/bin/python"
elif [ -d ".venv" ]; then
    PYTHON="./.venv/bin/python"
else
    PYTHON="python"
fi

# Run the test runner with all arguments passed through
$PYTHON tests/run_tests.py "$@" 