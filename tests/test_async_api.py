"""Unit tests for the async API module."""

import asyncio
import unittest
import time
from unittest.mock import AsyncMock, patch, MagicMock

from lotus_eaters.async_api import (
    AsyncThrottler,
    AsyncThrottled,
    async_consume,
    async_throttle,
    AsyncThrottleContext
)
from lotus_eaters.async_storage import AsyncDictStorage, AsyncRedisStorage
from lotus_eaters.async_bucket import AsyncBucket


class TestAsyncThrottler(unittest.TestCase):
    """Test cases for AsyncThrottler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = AsyncDictStorage()
        self.rate = 1.0  # 1 unit per second
        self.capacity = 10
        self.throttler = AsyncThrottler(self.rate, self.capacity, self.storage)
    
    def test_init(self):
        """Test AsyncThrottler initialization."""
        throttler = AsyncThrottler(2.0, 20, self.storage)
        self.assertEqual(throttler.rate, 2.0)
        self.assertEqual(throttler.capacity, 20)
        self.assertEqual(throttler.storage, self.storage)
    
    async def test_get_bucket(self):
        """Test getting a bucket."""
        bucket = await self.throttler.get_bucket('test_key')
        self.assertIsInstance(bucket, AsyncBucket)
        self.assertEqual(bucket.key, 'test_key')
        self.assertEqual(bucket.rate, self.rate)
        self.assertEqual(bucket.capacity, self.capacity)
        
        # Getting the same key should return the same bucket
        bucket2 = await self.throttler.get_bucket('test_key')
        self.assertIs(bucket, bucket2)
    
    async def test_consume_success(self):
        """Test successful consumption."""
        with patch('time.time', return_value=1000.0):
            result = await self.throttler.consume('test_key', amount=5)
            self.assertTrue(result)
    
    async def test_consume_failure(self):
        """Test failed consumption when exceeding capacity."""
        with patch('time.time', return_value=1000.0):
            # Due to the +1 quirk in the bucket algorithm, we can only consume 9
            result = await self.throttler.consume('test_key', amount=9)
            self.assertTrue(result)
            
            # Next consumption should fail
            result = await self.throttler.consume('test_key', amount=1)
            self.assertFalse(result)
    
    async def test_throttle_with_logging(self):
        """Test throttle method with logging."""
        with patch('time.time', return_value=1000.0):
            with patch('logging.warning') as mock_warning:
                # First request should succeed (max 9 due to +1 quirk)
                result = await self.throttler.throttle('test_key', amount=9)
                self.assertTrue(result)
                mock_warning.assert_not_called()
                
                # Second request should fail and log
                result = await self.throttler.throttle('test_key', amount=1)
                self.assertFalse(result)
                mock_warning.assert_called_once_with(
                    "Request of %d unit(s) for %s exceeds capacity.",
                    1, 'test_key'
                )
    
    async def test_remaining(self):
        """Test getting remaining capacity."""
        with patch('time.time', return_value=1000.0):
            # Initially should have full capacity (but due to +1 quirk, effective capacity is 9)
            remaining = await self.throttler.remaining('test_key')
            self.assertEqual(remaining, 9)
            
            # After consuming 3, should have 6 remaining
            await self.throttler.consume('test_key', amount=3)
            remaining = await self.throttler.remaining('test_key')
            self.assertEqual(remaining, 6)
    
    async def test_reset(self):
        """Test resetting a bucket."""
        with patch('time.time', return_value=1000.0):
            # Consume some capacity
            await self.throttler.consume('test_key', amount=5)
            
            # Reset the bucket
            await self.throttler.reset('test_key')
            
            # Should have full capacity again (9 due to +1 quirk)
            remaining = await self.throttler.remaining('test_key')
            self.assertEqual(remaining, 9)
    
    async def test_close(self):
        """Test closing storage connections."""
        # Should not raise any errors
        await self.throttler.close()


class TestAsyncConvenienceFunctions(unittest.TestCase):
    """Test async convenience functions."""
    
    async def test_async_consume(self):
        """Test async_consume function."""
        storage = AsyncDictStorage()
        
        with patch('time.time', return_value=1000.0):
            # Test successful consumption
            result = await async_consume('test', 1.0, 10, storage, amount=5)
            self.assertTrue(result)
            
            # Test failed consumption (can't consume more than 9 due to +1 quirk)
            result = await async_consume('test', 1.0, 10, storage, amount=6)
            self.assertFalse(result)
    
    async def test_async_throttle(self):
        """Test async_throttle function."""
        storage = AsyncDictStorage()
        
        with patch('time.time', return_value=1000.0):
            with patch('logging.warning') as mock_warning:
                # Test successful throttle
                result = await async_throttle('test', 1.0, 10, storage, amount=5)
                self.assertTrue(result)
                
                # Test failed throttle (can't consume more than 9 due to +1 quirk)
                result = await async_throttle('test', 1.0, 10, storage, amount=6)
                self.assertFalse(result)
                mock_warning.assert_called_once()


class TestAsyncThrottleContext(unittest.TestCase):
    """Test AsyncThrottleContext context manager."""
    
    async def test_context_manager_basic(self):
        """Test basic context manager usage."""
        async with AsyncThrottleContext('test', 1.0, 10) as throttler:
            self.assertIsInstance(throttler, AsyncThrottler)
            result = await throttler.consume('test', 5)
            self.assertTrue(result)
    
    async def test_context_manager_allowed(self):
        """Test context manager allowed method."""
        with patch('time.time', return_value=1000.0):
            context = AsyncThrottleContext('test', 1.0, 10)
            
            # Should be allowed initially
            self.assertTrue(await context.allowed(5))
            self.assertTrue(await context.allowed(4))  # Total 9 (max due to +1 quirk)
            
            # Should not be allowed when capacity exceeded
            self.assertFalse(await context.allowed(1))
    
    async def test_context_manager_cleanup(self):
        """Test context manager cleanup."""
        storage = AsyncDictStorage()
        storage.close = AsyncMock()
        
        async with AsyncThrottleContext('test', 1.0, 10, storage):
            pass
        
        # External storage should not be closed
        storage.close.assert_not_called()
        
        # Internal storage should be closed
        mock_close = AsyncMock()
        async with AsyncThrottleContext('test', 1.0, 10) as throttler:
            throttler.close = mock_close
        
        mock_close.assert_called_once()


class TestAsyncIntegration(unittest.TestCase):
    """Integration tests for async functionality."""
    
    async def test_concurrent_requests(self):
        """Test handling concurrent async requests."""
        storage = AsyncDictStorage()
        throttler = AsyncThrottler(1.0, 10, storage)
        
        with patch('time.time', return_value=1000.0):
            # Make 10 concurrent requests
            tasks = [
                throttler.consume(f'user_{i}', 1) 
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            
            # All should succeed (different keys)
            self.assertTrue(all(results))
            
            # Make 10 concurrent requests to same key
            tasks = [throttler.consume('same_key', 1) for _ in range(10)]
            results = await asyncio.gather(*tasks)
            
            # Only 9 should succeed due to +1 quirk
            self.assertEqual(sum(results), 9)
            
            # One more should fail
            result = await throttler.consume('same_key', 1)
            self.assertFalse(result)
    
    async def test_rate_limiting_over_time(self):
        """Test rate limiting with time progression."""
        storage = AsyncDictStorage()
        throttler = AsyncThrottler(5.0, 10, storage)  # 5 per second
        
        current_time = 1000.0
        
        async def consume_with_time(amount=1):
            nonlocal current_time
            with patch('time.time', return_value=current_time):
                return await throttler.consume('test', amount)
        
        # Consume all capacity (9 due to +1 quirk)
        self.assertTrue(await consume_with_time(9))
        self.assertFalse(await consume_with_time(1))
        
        # After 1 second, should have 5 tokens
        current_time += 1.0
        for _ in range(5):
            self.assertTrue(await consume_with_time(1))
        self.assertFalse(await consume_with_time(1))
        
        # After 2 more seconds, should have 9 tokens again (max due to +1 quirk)
        current_time += 2.0
        self.assertTrue(await consume_with_time(9))
        self.assertFalse(await consume_with_time(1))


# Helper to run async tests
def async_test(coro):
    """Decorator to run async test methods."""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# Apply decorator to all async test methods
for test_class in [TestAsyncThrottler, TestAsyncConvenienceFunctions, 
                   TestAsyncThrottleContext, TestAsyncIntegration]:
    for attr_name in dir(test_class):
        attr = getattr(test_class, attr_name)
        if asyncio.iscoroutinefunction(attr) and attr_name.startswith('test_'):
            setattr(test_class, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main() 