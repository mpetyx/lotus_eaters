"""Unit tests for the bucket module."""

import unittest
import time
from unittest.mock import Mock, patch
from lotus_eaters.bucket import Bucket
from lotus_eaters.storage import DictStorage


class TestBucket(unittest.TestCase):
    """Test cases for Bucket class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
        self.key = 'test_bucket'
        self.rate = 1.0  # 1 unit per second
        self.capacity = 10
        self.bucket = Bucket(
            key=self.key,
            rate=self.rate,
            capacity=self.capacity,
            storage=self.storage
        )
    
    def test_init(self):
        """Test Bucket initialization."""
        bucket = Bucket('test', 2.0, 20, self.storage)
        self.assertEqual(bucket.key, 'test')
        self.assertEqual(bucket.rate, 2.0)
        self.assertEqual(bucket.capacity, 20)
        self.assertEqual(bucket.storage, self.storage)
    
    def test_key_properties(self):
        """Test key property methods."""
        self.assertEqual(self.bucket.key_amount, 'test_bucket:current-amount')
        self.assertEqual(self.bucket.key_last_leak, 'test_bucket:last-leak')
    
    @patch('time.time')
    def test_leak_first_time(self, mock_time):
        """Test leak method when called for the first time."""
        mock_time.return_value = 1000.0
        
        new_capacity = self.bucket.leak()
        
        self.assertEqual(new_capacity, 0)
        self.assertEqual(self.storage.get(self.bucket.key_amount), 0)
        self.assertEqual(self.storage.get(self.bucket.key_last_leak), 1000.0)
    
    @patch('time.time')
    def test_leak_with_elapsed_time(self, mock_time):
        """Test leak method with elapsed time."""
        # First, set initial state
        mock_time.return_value = 1000.0
        self.storage.set(self.bucket.key_amount, 5)
        self.storage.set(self.bucket.key_last_leak, 1000.0)
        
        # Then leak after 2 seconds
        mock_time.return_value = 1002.0
        new_capacity = self.bucket.leak()
        
        # With rate=1.0 and 2 seconds elapsed, should leak 2 units
        # 5 - 2 = 3, but the +1 in the code makes it 4
        self.assertEqual(new_capacity, 4)
    
    @patch('time.time')
    def test_leak_to_zero(self, mock_time):
        """Test leak method when capacity goes to zero."""
        # Set initial state
        mock_time.return_value = 1000.0
        self.storage.set(self.bucket.key_amount, 3)
        self.storage.set(self.bucket.key_last_leak, 1000.0)
        
        # Leak after 10 seconds (more than enough to empty)
        mock_time.return_value = 1010.0
        new_capacity = self.bucket.leak()
        
        # Should be 0 (can't go negative)
        self.assertEqual(new_capacity, 0)
    
    def test_incr(self):
        """Test _incr method."""
        self.storage.set(self.bucket.key_amount, 5)
        self.bucket._incr(3)
        self.assertEqual(self.storage.get(self.bucket.key_amount), 8)
    
    @patch('time.time')
    def test_consume_success(self, mock_time):
        """Test successful consumption."""
        mock_time.return_value = 1000.0
        
        # First consume should succeed (empty bucket)
        result = self.bucket.consume(3)
        self.assertTrue(result)
        self.assertEqual(self.storage.get(self.bucket.key_amount), 3)
    
    @patch('time.time')
    def test_consume_failure_exceeds_capacity(self, mock_time):
        """Test consumption failure when exceeding capacity."""
        mock_time.return_value = 1000.0
        
        # Try to consume more than capacity
        result = self.bucket.consume(11)
        self.assertFalse(result)
        # Amount should not change
        self.assertEqual(self.storage.get(self.bucket.key_amount), 0)
    
    @patch('time.time')
    def test_consume_multiple_requests(self, mock_time):
        """Test multiple consumption requests."""
        mock_time.return_value = 1000.0
        
        # Consume 3 units
        self.assertTrue(self.bucket.consume(3))
        # Consume 5 more units (total 8)
        self.assertTrue(self.bucket.consume(5))
        # Try to consume 3 more (would be 11, exceeds capacity of 10)
        self.assertFalse(self.bucket.consume(3))
        # But consuming 2 should work
        self.assertTrue(self.bucket.consume(2))
    
    @patch('time.time')
    def test_consume_with_leak(self, mock_time):
        """Test consumption with leak over time."""
        # Initial consumption
        mock_time.return_value = 1000.0
        self.assertTrue(self.bucket.consume(8))
        
        # After 3 seconds, should have leaked 3 units
        mock_time.return_value = 1003.0
        # Current amount should be around 5-6 after leak
        # So consuming 5 more should work
        self.assertTrue(self.bucket.consume(5))
    
    @patch('time.time')
    def test_consume_default_amount(self, mock_time):
        """Test consume with default amount of 1."""
        mock_time.return_value = 1000.0
        
        result = self.bucket.consume()
        self.assertTrue(result)
        self.assertEqual(self.storage.get(self.bucket.key_amount), 1)
    
    @patch('time.time')
    def test_rapid_consumption(self, mock_time):
        """Test rapid consumption without time passing."""
        mock_time.return_value = 1000.0
        
        # Rapidly consume until full
        for i in range(10):
            result = self.bucket.consume(1)
            self.assertTrue(result)
        
        # Next consumption should fail
        result = self.bucket.consume(1)
        self.assertFalse(result)
    
    @patch('time.time')
    def test_different_rates(self, mock_time):
        """Test bucket with different leak rates."""
        # Create a bucket with rate 2.0 (2 units per second)
        fast_bucket = Bucket('fast', 2.0, 10, self.storage)
        
        mock_time.return_value = 1000.0
        fast_bucket.consume(6)
        
        # After 2 seconds, should have leaked 4 units
        mock_time.return_value = 1002.0
        # Should be able to consume 4 more
        self.assertTrue(fast_bucket.consume(4))
    
    def test_multiple_buckets_same_storage(self):
        """Test multiple buckets using the same storage."""
        bucket1 = Bucket('bucket1', 1.0, 10, self.storage)
        bucket2 = Bucket('bucket2', 1.0, 10, self.storage)
        
        with patch('time.time', return_value=1000.0):
            bucket1.consume(5)
            bucket2.consume(3)
        
        # Check they maintain separate states
        self.assertEqual(self.storage.get(bucket1.key_amount), 5)
        self.assertEqual(self.storage.get(bucket2.key_amount), 3)
    
    @patch('time.time')
    def test_fractional_leak(self, mock_time):
        """Test leak with fractional seconds."""
        mock_time.return_value = 1000.0
        self.bucket.consume(5)
        
        # After 0.5 seconds with rate 1.0, should leak 0.5 units
        mock_time.return_value = 1000.5
        new_capacity = self.bucket.leak()
        
        # 5 - 0.5 = 4.5, int() makes it 4, +1 makes it 5
        self.assertEqual(new_capacity, 5)


class TestBucketEdgeCases(unittest.TestCase):
    """Test edge cases for Bucket class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    @patch('time.time')
    def test_zero_rate(self, mock_time):
        """Test bucket with zero leak rate."""
        bucket = Bucket('zero_rate', 0.0, 10, self.storage)
        
        mock_time.return_value = 1000.0
        bucket.consume(5)
        
        # After any amount of time, nothing should leak
        mock_time.return_value = 2000.0
        new_capacity = bucket.leak()
        
        # With rate 0, no leaking occurs, but +1 is still applied
        self.assertEqual(new_capacity, 6)
    
    @patch('time.time')
    def test_very_high_rate(self, mock_time):
        """Test bucket with very high leak rate."""
        bucket = Bucket('high_rate', 1000.0, 10, self.storage)
        
        mock_time.return_value = 1000.0
        bucket.consume(10)
        
        # After just 0.01 seconds, should leak everything
        mock_time.return_value = 1000.01
        new_capacity = bucket.leak()
        
        self.assertEqual(new_capacity, 0)
    
    def test_zero_capacity(self):
        """Test bucket with zero capacity."""
        bucket = Bucket('zero_cap', 1.0, 0, self.storage)
        
        with patch('time.time', return_value=1000.0):
            # Should not be able to consume anything
            self.assertFalse(bucket.consume(1))
            self.assertFalse(bucket.consume(0))
    
    @patch('time.time')
    def test_negative_amount(self, mock_time):
        """Test consuming negative amount (should work as it just calls incr)."""
        bucket = Bucket('test', 1.0, 10, self.storage)
        mock_time.return_value = 1000.0
        
        # First consume some
        bucket.consume(5)
        
        # Consuming negative amount actually reduces the bucket
        result = bucket.consume(-2)
        self.assertTrue(result)  # Will return True as current + (-2) < capacity
        self.assertEqual(self.storage.get(bucket.key_amount), 3)


if __name__ == '__main__':
    unittest.main() 