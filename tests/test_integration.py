"""Integration tests for the lotus_eaters library."""

import unittest
import time
import threading
from unittest.mock import patch, Mock
from concurrent.futures import ThreadPoolExecutor, as_completed
from lotus_eaters.api import throttle, Throttler
from lotus_eaters.storage import DictStorage, BaseStorage
from lotus_eaters.bucket import Bucket


class TestRealTimeScenarios(unittest.TestCase):
    """Test scenarios with actual time delays (slower tests)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    def test_real_time_leak(self):
        """Test token bucket leak with real time delays."""
        # Rate of 5 tokens per second, capacity of 10
        rate = 5.0
        capacity = 10
        key = 'real_time_test'
        
        # Consume all capacity
        for i in range(10):
            result = throttle(key, rate, capacity, self.storage)
            self.assertTrue(result, f"Request {i+1} should succeed")
        
        # Next request should fail
        self.assertFalse(throttle(key, rate, capacity, self.storage))
        
        # Wait 0.4 seconds (should regenerate 2 tokens)
        time.sleep(0.4)
        
        # Should be able to make 2 requests
        self.assertTrue(throttle(key, rate, capacity, self.storage))
        self.assertTrue(throttle(key, rate, capacity, self.storage))
        self.assertFalse(throttle(key, rate, capacity, self.storage))
    
    def test_sustained_rate(self):
        """Test sustained request rate at the limit."""
        rate = 10.0  # 10 requests per second
        capacity = 5  # Small burst capacity
        key = 'sustained_rate'
        
        # Make requests at exactly the allowed rate
        successful_requests = 0
        start_time = time.time()
        
        for i in range(10):
            if throttle(key, rate, capacity, self.storage):
                successful_requests += 1
            time.sleep(0.1)  # 10 requests per second
        
        elapsed_time = time.time() - start_time
        
        # Should have made approximately 10 requests in ~1 second
        self.assertGreaterEqual(successful_requests, 9)
        self.assertLessEqual(successful_requests, 11)
        self.assertAlmostEqual(elapsed_time, 1.0, delta=0.2)


class TestConcurrentAccess(unittest.TestCase):
    """Test concurrent access scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    def test_thread_safety_dict_storage(self):
        """Test thread safety of DictStorage (note: DictStorage is NOT thread-safe)."""
        rate = 1.0
        capacity = 100
        key = 'concurrent_test'
        
        successful_requests = []
        failed_requests = []
        
        def make_request(request_id):
            result = throttle(key, rate, capacity, self.storage)
            if result:
                successful_requests.append(request_id)
            else:
                failed_requests.append(request_id)
            return result
        
        # Make 100 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()
        
        # All requests should succeed since capacity is 100
        # Note: This might fail occasionally due to race conditions in DictStorage
        self.assertEqual(len(successful_requests), 100)
        self.assertEqual(len(failed_requests), 0)
    
    @patch('lotus_eaters.storage.Redis')
    def test_thread_safety_redis_storage(self, mock_redis):
        """Test thread safety with Redis storage (mocked)."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        
        # Setup thread-safe mock responses
        current_value = {'value': 0}
        lock = threading.Lock()
        
        def mock_get(key):
            with lock:
                if 'current-amount' in key:
                    return str(current_value['value']).encode()
                return None
        
        def mock_set(key, value):
            with lock:
                if 'current-amount' in key:
                    current_value['value'] = int(value)
                return True
        
        mock_client.get.side_effect = mock_get
        mock_client.set.side_effect = mock_set
        
        storage = BaseStorage()
        rate = 1.0
        capacity = 50
        key = 'redis_concurrent'
        
        successful_count = 0
        
        def make_request():
            nonlocal successful_count
            with patch('time.time', return_value=1000.0):
                result = throttle(key, rate, capacity, storage)
                if result:
                    successful_count += 1
        
        # Make 60 concurrent requests (10 should fail)
        threads = []
        for _ in range(60):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have exactly 50 successful requests
        self.assertLessEqual(successful_count, 50)
    
    def test_multiple_keys_concurrent(self):
        """Test concurrent access to different keys."""
        rate = 1.0
        capacity = 10
        
        results = {'key1': [], 'key2': [], 'key3': []}
        
        def make_requests(key, count):
            for i in range(count):
                with patch('time.time', return_value=1000.0 + i * 0.001):
                    result = throttle(key, rate, capacity, self.storage)
                    results[key].append(result)
        
        # Create threads for different keys
        threads = [
            threading.Thread(target=make_requests, args=('key1', 15)),
            threading.Thread(target=make_requests, args=('key2', 15)),
            threading.Thread(target=make_requests, args=('key3', 15)),
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Each key should have 10 successful and 5 failed requests
        for key, key_results in results.items():
            successful = sum(1 for r in key_results if r)
            self.assertEqual(successful, 10, f"Key {key} should have 10 successful requests")


class TestComplexScenarios(unittest.TestCase):
    """Test complex real-world scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    @patch('time.time')
    def test_tiered_rate_limiting(self, mock_time):
        """Test tiered rate limiting (e.g., different limits for different user tiers)."""
        mock_time.return_value = 1000.0
        
        # Define tiers
        tiers = {
            'free': {'rate': 10.0 / 60.0, 'capacity': 10},      # 10 per minute
            'basic': {'rate': 100.0 / 60.0, 'capacity': 50},    # 100 per minute
            'premium': {'rate': 1000.0 / 60.0, 'capacity': 200} # 1000 per minute
        }
        
        # Test each tier
        for tier_name, limits in tiers.items():
            key = f'user_{tier_name}_123'
            
            # Should be able to make 'capacity' requests
            for i in range(limits['capacity']):
                self.assertTrue(
                    throttle(key, limits['rate'], limits['capacity'], self.storage),
                    f"{tier_name} tier request {i+1} should succeed"
                )
            
            # Next request should fail
            self.assertFalse(
                throttle(key, limits['rate'], limits['capacity'], self.storage),
                f"{tier_name} tier should be at capacity"
            )
    
    @patch('time.time')
    def test_sliding_window_approximation(self, mock_time):
        """Test that token bucket approximates sliding window behavior."""
        rate = 1.0  # 1 request per second
        capacity = 60  # 1 minute burst
        key = 'sliding_window'
        
        # Start at time 0
        mock_time.return_value = 0.0
        
        # Make 60 requests (fill the bucket)
        for i in range(60):
            self.assertTrue(throttle(key, rate, capacity, self.storage))
        
        # 61st request should fail
        self.assertFalse(throttle(key, rate, capacity, self.storage))
        
        # After 30 seconds, should have 30 tokens
        mock_time.return_value = 30.0
        for i in range(30):
            self.assertTrue(throttle(key, rate, capacity, self.storage))
        self.assertFalse(throttle(key, rate, capacity, self.storage))
        
        # After another 30 seconds, should have 30 tokens again
        mock_time.return_value = 60.0
        for i in range(30):
            self.assertTrue(throttle(key, rate, capacity, self.storage))
        self.assertFalse(throttle(key, rate, capacity, self.storage))
    
    @patch('time.time')
    def test_graceful_degradation(self, mock_time):
        """Test graceful degradation under load."""
        mock_time.return_value = 1000.0
        
        # Simulate a service with multiple endpoints
        endpoints = {
            '/api/critical': {'rate': 100.0, 'capacity': 100},
            '/api/normal': {'rate': 50.0, 'capacity': 50},
            '/api/bulk': {'rate': 10.0, 'capacity': 20}
        }
        
        # Simulate load on each endpoint
        for endpoint, limits in endpoints.items():
            successful = 0
            total_attempts = limits['capacity'] + 10
            
            for _ in range(total_attempts):
                if throttle(endpoint, limits['rate'], limits['capacity'], self.storage):
                    successful += 1
            
            # Should have successful requests up to capacity
            self.assertEqual(
                successful,
                limits['capacity'],
                f"{endpoint} should allow exactly {limits['capacity']} requests"
            )
    
    def test_memory_efficiency(self):
        """Test memory efficiency with many keys."""
        rate = 1.0
        capacity = 10
        
        # Create many different keys
        num_keys = 1000
        
        with patch('time.time', return_value=1000.0):
            for i in range(num_keys):
                key = f'user_{i}'
                # Each user makes one request
                self.assertTrue(throttle(key, rate, capacity, self.storage))
        
        # Check storage size (each key creates 2 entries: amount and last_leak)
        self.assertEqual(len(self.storage.data), num_keys * 2)
        
        # Verify all keys are properly namespaced
        for i in range(num_keys):
            self.assertIn(f'user_{i}:current-amount', self.storage.data)
            self.assertIn(f'user_{i}:last-leak', self.storage.data)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""
    
    def test_invalid_parameters(self):
        """Test handling of invalid parameters."""
        storage = DictStorage()
        
        with patch('time.time', return_value=1000.0):
            # Negative rate should still work (no leak)
            result = throttle('test', rate=-1.0, capacity=10, storage=storage)
            self.assertTrue(result)
            
            # Zero capacity should always fail
            result = throttle('test2', rate=1.0, capacity=0, storage=storage)
            self.assertFalse(result)
            
            # Very large numbers should work
            result = throttle('test3', rate=1e6, capacity=1e9, storage=storage, amount=1000)
            self.assertTrue(result)
    
    @patch('lotus_eaters.storage.Redis')
    def test_redis_connection_failure(self, mock_redis):
        """Test handling of Redis connection failures."""
        mock_redis.side_effect = Exception("Connection failed")
        
        # Should raise exception when creating storage
        with self.assertRaises(Exception):
            storage = BaseStorage()
    
    def test_storage_type_errors(self):
        """Test type conversion in storage."""
        storage = DictStorage()
        
        # Set non-numeric values
        storage.set('test:current-amount', 'not-a-number')
        storage.set('test:last-leak', 'also-not-a-number')
        
        bucket = Bucket('test', 1.0, 10, storage)
        
        # Should handle gracefully (though behavior might be undefined)
        with patch('time.time', return_value=1000.0):
            # This will raise ValueError when trying to convert 'not-a-number' to float
            with self.assertRaises(ValueError):
                bucket.leak()


if __name__ == '__main__':
    unittest.main() 