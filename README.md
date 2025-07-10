# lotus_eaters
A simple Python throttling lib relying on the token bucket algorithm - Redis Backend
========

The throttle library provides a robust and versatile throttling mechanism for Python.

It can be used in multiple environments, from a single thread to a distributed
server cluster.


It supports Python versions 2.7 to 3.12, with full async/await support for Python 3.8+.


Usage
-----

In order to perform throttling tasks, simply use the :meth:`~throttle.throttle`
function:

.. code-block:: python

    import throttle

    def some_fun(uid):
        if not throttle.check(key=uid, rate=30, size=10):
            raise ThrottleError()
        # Do the job

    # Or with a custom Redis client,
    throttle(key=key, rate=1, capacity=5, storage=BaseStorage(client=Redis(host='localhost', port=6379, db=220, password=None)), amount=3)


## Synchronous Usage

.. code-block:: python

    from lotus_eaters import throttle, BaseStorage
    from redis import Redis

    # Simple usage with default storage
    def some_fun(uid):
        if not throttle(key=uid, rate=30, capacity=10, storage=BaseStorage()):
            return "Rate limit exceeded"
        # Do the job

    # Or with a custom Redis client
    custom_redis = Redis(host='localhost', port=6379, db=220, password=None)
    throttle(key=key, rate=1, capacity=5, storage=BaseStorage(client=custom_redis), amount=3)


## Async/Await Usage (Python 3.8+)

The library now provides full async/await support for non-blocking rate limiting:

.. code-block:: python

    import asyncio
    from lotus_eaters import async_throttle, AsyncRedisStorage, AsyncDictStorage

    async def handle_request(user_id):
        # Using async Redis storage
        storage = AsyncRedisStorage("redis://localhost:6379")
        
        # Check rate limit (10 requests per second, burst of 20)
        if not await async_throttle(
            key=f"user:{user_id}",
            rate=10.0,
            capacity=20,
            storage=storage
        ):
            return "Rate limit exceeded", 429
        
        # Process the request
        return "Success", 200

    # Using context manager for automatic cleanup
    from lotus_eaters import AsyncThrottleContext

    async def process_api_request(endpoint, user_id):
        async with AsyncThrottleContext(
            key=f"{endpoint}:{user_id}",
            rate=5.0,  # 5 requests per second
            capacity=10
        ) as throttler:
            if await throttler.consume(f"{endpoint}:{user_id}"):
                # Process request
                return {"status": "success"}
            else:
                return {"error": "rate_limit_exceeded"}

    # Thread-safe in-memory storage for testing
    async def test_rate_limiting():
        storage = AsyncDictStorage()  # Thread-safe async dict storage
        
        results = await asyncio.gather(
            async_throttle("test", 1.0, 10, storage),
            async_throttle("test", 1.0, 10, storage),
            async_throttle("test", 1.0, 10, storage),
        )
        print(f"All requests allowed: {all(results)}")


Algorithm
---------

throttle uses the "token bucket" algorithm: for each key, a virtual bucket
exists.

Whenever a new request gets in, the algorithm performs the following actions:

- Test if adding the request's cost to the bucket would exceed its capacity;
  in that case, return False
- Otherwise, add the request's cost to the bucket, and return True

Simultaneously, the bucket's current value is decremented at the chosen rate.


This allows for temporary bursts and average computations.


Installing
----------

From pip (https://pypi.python.org/pypi/lotus_eaters):

.. code-block:: sh

    $ pip install lotus_eaters


From Github:

.. code-block:: sh

    $ git clone git://github.com/mpetyx/lotus_eaters.git
    $ cd lotus_eaters
    $ pip install -r requirements.txt
    $ python setup.py install


Testing
-------

The library includes a comprehensive test suite. To run the tests:

.. code-block:: sh

    # Run all tests
    $ ./run_tests.sh

    # Run specific test module
    $ ./run_tests.sh test_storage

    # Run with different verbosity
    $ ./run_tests.sh -v 0  # quiet
    $ ./run_tests.sh -v 2  # verbose

    # Run async tests
    $ python tests/test_async_api.py

For more details about the test suite, see the [tests/README.md](tests/README.md) file.