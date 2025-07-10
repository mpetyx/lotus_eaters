# Lotus Eaters Test Suite

This directory contains comprehensive unit tests for the lotus_eaters throttling library.

## Test Files

- **test_storage.py** - Tests for storage backends (DictStorage and BaseStorage)
- **test_bucket.py** - Tests for the Bucket class and token bucket algorithm
- **test_api.py** - Tests for the API module (Throttler class and public functions)
- **test_integration.py** - Integration tests including real-time, concurrent, and complex scenarios
- **test_throttle.py** - Original test file with basic throttling tests

## Running Tests

### From the project root directory:

#### Run all tests:
```bash
python tests/run_tests.py
# or
python -m unittest discover tests
```

#### Run a specific test module:
```bash
python tests/run_tests.py test_storage
python tests/run_tests.py test_bucket
python tests/run_tests.py test_api
python tests/run_tests.py test_integration
```

### From within the tests directory:

#### Run all tests:
```bash
cd tests
python run_tests.py
```

#### Run with different verbosity:
```bash
python run_tests.py -v 0  # Quiet mode
python run_tests.py -v 1  # Normal mode
python run_tests.py -v 2  # Verbose mode (default)
```

#### Skip Redis tests (if Redis is not available):
```bash
python run_tests.py --no-redis
```

### Run individual test classes or methods:
```bash
# From project root
python -m unittest tests.test_storage.TestDictStorage
python -m unittest tests.test_bucket.TestBucket.test_consume_success

# From tests directory
python -m unittest test_storage.TestDictStorage
python -m unittest test_bucket.TestBucket.test_consume_success
```

## Test Coverage

The test suite covers:

1. **Storage Layer**
   - DictStorage in-memory implementation
   - BaseStorage Redis implementation (with mocks)
   - All CRUD operations
   - Thread safety considerations

2. **Bucket Algorithm**
   - Token bucket initialization
   - Leak calculations
   - Consumption logic
   - Edge cases (zero rate, zero capacity, etc.)

3. **API Layer**
   - Throttler class methods
   - Public API functions
   - Exception handling
   - Parameter overrides

4. **Integration Scenarios**
   - Real-time token regeneration
   - Concurrent access patterns
   - Multiple keys/users
   - Tiered rate limiting
   - Memory efficiency
   - Error handling

## Requirements

- Python 2.7+ or Python 3.x
- redis-py (for Redis-based tests)
- unittest (built-in)
- mock (for Python 2.7, built-in for Python 3.3+)

## Notes

- The DictStorage is NOT thread-safe and should only be used for testing or single-threaded applications
- Redis-based storage (BaseStorage) provides better concurrency support
- Some integration tests use real time delays and may take longer to complete
- Mock objects are used extensively to avoid Redis dependencies in most tests

## Virtual Environment Setup

If you haven't set up a virtual environment yet:

```bash
# From project root
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install redis
``` 