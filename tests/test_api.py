"""Unit tests for the API module."""

import unittest
import logging
from unittest.mock import Mock, patch, MagicMock
from lotus_eaters.api import Throttler, Throttled, consume, throttle
from lotus_eaters.storage import DictStorage, BaseStorage
from lotus_eaters.bucket import Bucket


class TestThrottled(unittest.TestCase):
    """Test cases for Throttled exception."""
    
    def test_throttled_exception(self):
        """Test that Throttled is an Exception."""
        self.assertTrue(issubclass(Throttled, Exception))
        
        # Test raising and catching
        with self.assertRaises(Throttled):
            raise Throttled("Test message")
        
        try:
            raise Throttled("Test message")
        except Throttled as e:
            self.assertEqual(str(e), "Test message")


class TestThrottler(unittest.TestCase):
    """Test cases for Throttler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
        self.rate = 2.0
        self.capacity = 10
        self.throttler = Throttler(self.rate, self.capacity, self.storage)
    
    def test_init(self):
        """Test Throttler initialization."""
        storage = Mock()
        throttler = Throttler(5.0, 20, storage)
        
        self.assertEqual(throttler.rate, 5.0)
        self.assertEqual(throttler.capacity, 20)
        self.assertEqual(throttler.storage, storage)
    
    def test_get_bucket_default_params(self):
        """Test get_bucket with default parameters."""
        bucket = self.throttler.get_bucket('test_key')
        
        self.assertIsInstance(bucket, Bucket)
        self.assertEqual(bucket.key, 'test_key')
        self.assertEqual(bucket.rate, self.rate)
        self.assertEqual(bucket.capacity, self.capacity)
        self.assertEqual(bucket.storage, self.storage)
    
    def test_get_bucket_override_params(self):
        """Test get_bucket with overridden parameters."""
        new_storage = DictStorage()
        bucket = self.throttler.get_bucket(
            'test_key',
            rate=5.0,
            capacity=30,
            storage=new_storage
        )
        
        self.assertEqual(bucket.rate, 5.0)
        self.assertEqual(bucket.capacity, 30)
        self.assertEqual(bucket.storage, new_storage)
        # Throttler's storage should also be updated
        self.assertEqual(self.throttler.storage, new_storage)
    
    def test_get_bucket_partial_override(self):
        """Test get_bucket with partially overridden parameters."""
        bucket = self.throttler.get_bucket('test_key', rate=3.0)
        
        self.assertEqual(bucket.rate, 3.0)
        self.assertEqual(bucket.capacity, self.capacity)  # Should use default
    
    @patch('time.time')
    def test_consume_success(self, mock_time):
        """Test successful consumption."""
        mock_time.return_value = 1000.0
        
        result = self.throttler.consume('test_key', amount=5)
        self.assertTrue(result)
    
    @patch('time.time')
    def test_consume_failure(self, mock_time):
        """Test failed consumption."""
        mock_time.return_value = 1000.0
        
        # Try to consume more than capacity
        result = self.throttler.consume('test_key', amount=15)
        self.assertFalse(result)
    
    @patch('time.time')
    def test_consume_with_overrides(self, mock_time):
        """Test consume with overridden parameters."""
        mock_time.return_value = 1000.0
        
        # Override capacity to be smaller
        result = self.throttler.consume('test_key', amount=8, capacity=5)
        self.assertFalse(result)  # Should fail with capacity 5
    
    @patch('time.time')
    @patch('lotus_eaters.api.logging')
    def test_throttle_success(self, mock_logging, mock_time):
        """Test throttle method when successful."""
        mock_time.return_value = 1000.0
        
        result = self.throttler.throttle('test_key', amount=5)
        self.assertTrue(result)
        
        # Should not log warning on success
        mock_logging.warning.assert_not_called()
    
    @patch('time.time')
    @patch('lotus_eaters.api.logging')
    def test_throttle_failure(self, mock_logging, mock_time):
        """Test throttle method when it fails."""
        mock_time.return_value = 1000.0
        
        result = self.throttler.throttle('test_key', amount=15)
        self.assertFalse(result)
        
        # Should log warning on failure
        mock_logging.warning.assert_called_once_with(
            "Request of %d unit for %s exceeds capacity.",
            15,
            'test_key'
        )
    
    @patch('time.time')
    def test_throttle_with_custom_exception(self, mock_time):
        """Test throttle with custom exception class."""
        mock_time.return_value = 1000.0
        
        class CustomException(Exception):
            pass
        
        # Should return False instead of raising exception
        result = self.throttler.throttle(
            'test_key',
            amount=15,
            exc_class=CustomException
        )
        self.assertFalse(result)
    
    def test_multiple_keys(self):
        """Test throttling with multiple keys."""
        with patch('time.time', return_value=1000.0):
            # Different keys should have separate buckets
            self.assertTrue(self.throttler.consume('key1', 5))
            self.assertTrue(self.throttler.consume('key2', 5))
            self.assertTrue(self.throttler.consume('key1', 5))  # Total 10 for key1
            self.assertFalse(self.throttler.consume('key1', 1))  # Exceeds capacity
            self.assertTrue(self.throttler.consume('key2', 5))  # key2 still has room


class TestAPIFunctions(unittest.TestCase):
    """Test cases for module-level API functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    @patch('time.time')
    def test_consume_function(self, mock_time):
        """Test the consume function."""
        mock_time.return_value = 1000.0
        
        # Test successful consumption
        result = consume('test_key', rate=1.0, capacity=10, storage=self.storage, amount=5)
        self.assertTrue(result)
        
        # Test failed consumption
        result = consume('test_key', rate=1.0, capacity=10, storage=self.storage, amount=10)
        self.assertFalse(result)
    
    @patch('time.time')
    def test_throttle_function(self, mock_time):
        """Test the throttle function."""
        mock_time.return_value = 1000.0
        
        # Test successful throttle
        result = throttle('test_key', rate=1.0, capacity=10, storage=self.storage, amount=5)
        self.assertTrue(result)
        
        # Test failed throttle
        result = throttle('test_key', rate=1.0, capacity=10, storage=self.storage, amount=10)
        self.assertFalse(result)
    
    @patch('time.time')
    def test_throttle_function_with_custom_exception(self, mock_time):
        """Test throttle function with custom exception class."""
        mock_time.return_value = 1000.0
        
        class CustomThrottled(Exception):
            pass
        
        result = throttle(
            'test_key',
            rate=1.0,
            capacity=5,
            storage=self.storage,
            amount=10,
            exc_class=CustomThrottled
        )
        self.assertFalse(result)
    
    def test_api_function_parameters(self):
        """Test that API functions accept all documented parameters."""
        with patch('time.time', return_value=1000.0):
            # Test all parameters are accepted
            result = throttle(
                key='test_key',
                rate=2.0,
                capacity=20,
                storage=self.storage,
                amount=5,
                exc_class=Throttled
            )
            self.assertTrue(result)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for real-world scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    @patch('time.time')
    def test_api_rate_limiting_scenario(self, mock_time):
        """Test a typical API rate limiting scenario."""
        # Allow 10 requests per minute (rate=10/60)
        rate = 10.0 / 60.0  # ~0.167 requests per second
        capacity = 10
        
        mock_time.return_value = 1000.0
        
        # User makes 10 rapid requests
        for i in range(10):
            result = throttle('user123', rate, capacity, self.storage)
            self.assertTrue(result, f"Request {i+1} should succeed")
        
        # 11th request should fail
        result = throttle('user123', rate, capacity, self.storage)
        self.assertFalse(result)
        
        # After 30 seconds, should have regenerated 5 tokens
        mock_time.return_value = 1030.0
        for i in range(5):
            result = throttle('user123', rate, capacity, self.storage)
            self.assertTrue(result, f"Request {i+1} after wait should succeed")
        
        # 6th request should fail
        result = throttle('user123', rate, capacity, self.storage)
        self.assertFalse(result)
    
    @patch('time.time')
    def test_burst_traffic_handling(self, mock_time):
        """Test handling burst traffic with token bucket."""
        # Allow average of 1 request per second, but burst up to 5
        rate = 1.0
        capacity = 5
        
        mock_time.return_value = 1000.0
        
        # Burst of 5 requests should succeed
        for i in range(5):
            self.assertTrue(throttle('api_endpoint', rate, capacity, self.storage))
        
        # 6th request should fail
        self.assertFalse(throttle('api_endpoint', rate, capacity, self.storage))
        
        # After 2 seconds, 2 more requests should succeed
        mock_time.return_value = 1002.0
        self.assertTrue(throttle('api_endpoint', rate, capacity, self.storage))
        self.assertTrue(throttle('api_endpoint', rate, capacity, self.storage))
        self.assertFalse(throttle('api_endpoint', rate, capacity, self.storage))
    
    @patch('time.time')
    def test_different_rate_limits_per_endpoint(self, mock_time):
        """Test different rate limits for different endpoints."""
        mock_time.return_value = 1000.0
        
        # Public endpoint: 100 requests per minute
        public_rate = 100.0 / 60.0
        public_capacity = 20
        
        # Private endpoint: 10 requests per minute
        private_rate = 10.0 / 60.0
        private_capacity = 5
        
        # Test public endpoint can handle more requests
        for i in range(20):
            self.assertTrue(
                throttle('public_api', public_rate, public_capacity, self.storage)
            )
        
        # Test private endpoint is more restrictive
        for i in range(5):
            self.assertTrue(
                throttle('private_api', private_rate, private_capacity, self.storage)
            )
        self.assertFalse(
            throttle('private_api', private_rate, private_capacity, self.storage)
        )


if __name__ == '__main__':
    unittest.main() 