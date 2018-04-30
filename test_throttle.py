__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"

import unittest
from lotus_eaters.api import throttle
from lotus_eaters.storage import BaseStorage
from lotus_eaters.api import Throttled

class ThrottlerTest(unittest.TestCase):

    """

    throttle uses the "token bucket" algorithm: for each key, a virtual bucket exists.

    Whenever a new request gets in, the algorithm performs the following actions:

    Test if adding the request's cost to the bucket would exceed its capacity; in that case, return False
    Otherwise, add the request's cost to the bucket, and return True
    Simultaneously, the bucket's current value is decremented at the chosen rate.

    This allows for temporary bursts and average computations.
    """

    # def some_fun(self, uid, counter):
    #     if not throttle(key=uid, rate=1, capacity=20, storage=BaseStorage(), amount=1):
    #         print("something is working")
    #     return counter + 1
    #
    # def test_fun(self):
    #     counter = 0
    #     for number in range(1, 1000):
    #         counter = self.some_fun("kouklaki2", counter)
    #         print("this is iteration: ",str(counter))
    #     print
    #     print
    #     print
    #     print
    #     self.assertEqual(True, False)
    #
    # def test_empty_bucket_initial_request(self):
    #     pass
    #
    # def test_second_request(self):
    #     pass
    #
    # def test_bucket_full_bucket(self):
    #     pass
    #
    def test_enter_3_values_every_2_second(self):
        self.assertTrue(throttle(key='test_enter_3_values_every_2_second', rate=1, capacity=5, storage=BaseStorage(), amount=3))
        self.assertIs(throttle(key='test_enter_3_values_every_2_second', rate=1, capacity=5, storage=BaseStorage(), amount=3),Throttled("Request of %d unit for %s exceeds capacity."
                    % (3, 'test_enter_3_values_every_2_second')))