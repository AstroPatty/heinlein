#!/bin/bash
# Get the TEST_SET environment variable
if [ -z "$TEST_SET" ]; then
  TEST_SET=""
else
  TEST_SET="test_$TEST_SET.py"
fi
cd tests && poetry run pytest $TEST_SET
