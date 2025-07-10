__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"

import unittest
from lotus_eaters.api import throttle
from lotus_eaters.storage import BaseStorage
from lotus_eaters.api import Throttled
import random
from redis import Redis
from redis.exceptions import ResponseError

class ThrottlerTest(unittest.TestCase):

    def setUp(self):
        self.client = Redis(host='localhost', port=6379, db=13, password=None)
        self.client.flushall()

    """

    throttle uses the "token bucket" algorithm: for each key, a virtual bucket exists.

    Whenever a new request gets in, the algorithm performs the following actions:

    Test if adding the request's cost to the bucket would exceed its capacity; in that case, return False
    Otherwise, add the request's cost to the bucket, and return True
    Simultaneously, the bucket's current value is decremented at the chosen rate.

    This allows for temporary bursts and average computations.
    """

    def test_with_zero_rate(self):
        # TODO update this
        key = ''.join(random.choice('0123456789ABCDEF') for i in range(20))
        self.assertTrue(throttle(key=key, rate=0, capacity=5, storage=BaseStorage(), amount=3))

    def test_empty_bucket_initial_request(self):
        key = ''.join(random.choice('0123456789ABCDEF') for i in range(20))
        self.assertTrue(throttle(key=key, rate=1, capacity=5, storage=BaseStorage(), amount=3))

    def test_entering_3_values(self):
        key = ''.join(random.choice('0123456789ABCDEF') for i in range(20))
        self.assertTrue(throttle(key=key, rate=1, capacity=5, storage=BaseStorage(), amount=3))

    def test_entering_3_values_every_2_second(self):
        key = ''.join(random.choice('0123456789ABCDEF') for i in range(20))
        self.assertTrue(throttle(key=key, rate=1, capacity=5, storage=BaseStorage(), amount=3))
        self.assertFalse(throttle(key=key, rate=1, capacity=5, storage=BaseStorage(), amount=3))

    def test_with_wrong_client(self):
        key = ''.join(random.choice('0123456789ABCDEF') for i in range(20))
        with self.assertRaises(ResponseError):
            throttle(key=key, rate=1, capacity=5, storage=BaseStorage(client=Redis(host='localhost', port=6379, db=220, password=None)), amount=3)

    def tearDown(self):
        self.client.flushall()

