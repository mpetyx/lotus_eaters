#!/usr/bin/env python
"""Test runner for lotus_eaters library."""

import sys
import os
import unittest
import argparse

# Add parent directory to path so we can import lotus_eaters
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests(verbosity=2):
    """Run all tests in the test suite."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_specific_test(test_module, verbosity=2):
    """Run a specific test module."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_module)
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description='Run tests for lotus_eaters library')
    parser.add_argument(
        'test',
        nargs='?',
        help='Specific test module to run (e.g., test_storage, test_bucket, test_api, test_integration)'
    )
    parser.add_argument(
        '-v', '--verbosity',
        type=int,
        choices=[0, 1, 2],
        default=2,
        help='Test output verbosity (0=quiet, 1=normal, 2=verbose)'
    )
    parser.add_argument(
        '--no-redis',
        action='store_true',
        help='Skip tests that require Redis'
    )
    
    args = parser.parse_args()
    
    if args.no_redis:
        # Set environment variable to skip Redis tests
        os.environ['SKIP_REDIS_TESTS'] = '1'
    
    if args.test:
        # Run specific test module
        success = run_specific_test(args.test, args.verbosity)
    else:
        # Run all tests
        print("Running all tests...")
        success = run_all_tests(args.verbosity)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 