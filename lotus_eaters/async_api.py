"""Async API for the lotus_eaters throttle library.

This module provides async/await support for non-blocking rate limiting.
"""

import asyncio
import logging
from typing import Optional, Type, Dict, Any

from .async_bucket import AsyncBucket
from .async_storage import AsyncBaseStorage, AsyncDictStorage

__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"


class AsyncThrottled(Exception):
    """Exception raised when a request is throttled."""
    pass


class AsyncThrottler:
    """Async throttler using the token bucket algorithm.
    
    This class provides async/await support for rate limiting.
    """
    
    def __init__(self, rate: float, capacity: int, storage: AsyncBaseStorage):
        """Initialize the async throttler.
        
        Args:
            rate: Units regenerated per second
            capacity: Maximum units in the bucket
            storage: Async storage backend
        """
        self.rate = rate
        self.capacity = capacity
        self.storage = storage
        self._buckets: Dict[str, AsyncBucket] = {}
        self._lock = asyncio.Lock()
    
    async def get_bucket(
        self, 
        key: str, 
        rate: Optional[float] = None, 
        capacity: Optional[int] = None,
        storage: Optional[AsyncBaseStorage] = None
    ) -> AsyncBucket:
        """Fetch or create an AsyncBucket for the given key.
        
        Args:
            key: The bucket key
            rate: Override rate for this bucket
            capacity: Override capacity for this bucket
            storage: Override storage for this bucket
            
        Returns:
            AsyncBucket instance
        """
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = AsyncBucket(
                    key=key,
                    rate=rate or self.rate,
                    capacity=capacity or self.capacity,
                    storage=storage or self.storage
                )
            return self._buckets[key]
    
    async def consume(
        self, 
        key: str, 
        amount: int = 1,
        rate: Optional[float] = None,
        capacity: Optional[int] = None
    ) -> bool:
        """Consume an amount for a given key.
        
        Args:
            key: The bucket key
            amount: Number of units to consume
            rate: Override rate for this bucket
            capacity: Override capacity for this bucket
            
        Returns:
            True if units were consumed, False otherwise
        """
        bucket = await self.get_bucket(key, rate, capacity)
        return await bucket.consume(amount)
    
    async def throttle(
        self,
        key: str,
        amount: int = 1,
        rate: Optional[float] = None,
        capacity: Optional[int] = None,
        exc_class: Type[Exception] = AsyncThrottled
    ) -> bool:
        """Consume an amount for a given key, or log a warning.
        
        Args:
            key: The bucket key
            amount: Number of units to consume
            rate: Override rate for this bucket
            capacity: Override capacity for this bucket
            exc_class: Exception class (kept for compatibility)
            
        Returns:
            True if units were consumed, False otherwise
        """
        if not await self.consume(key, amount, rate, capacity):
            logging.warning(
                "Request of %d unit(s) for %s exceeds capacity.",
                amount, key
            )
            return False
        return True
    
    async def remaining(self, key: str) -> int:
        """Get remaining capacity for a key.
        
        Args:
            key: The bucket key
            
        Returns:
            Number of remaining units
        """
        bucket = await self.get_bucket(key)
        return await bucket.remaining()
    
    async def reset(self, key: str) -> None:
        """Reset a bucket to empty state.
        
        Args:
            key: The bucket key
        """
        bucket = await self.get_bucket(key)
        await bucket.reset()
    
    async def close(self) -> None:
        """Close storage connections."""
        await self.storage.close()


# Convenience functions

async def async_consume(
    key: str,
    rate: float,
    capacity: int,
    storage: AsyncBaseStorage,
    amount: int = 1
) -> bool:
    """Async consume function.
    
    Args:
        key: The bucket key
        rate: Units regenerated per second
        capacity: Maximum units in the bucket
        storage: Async storage backend
        amount: Number of units to consume
        
    Returns:
        True if units were consumed, False otherwise
    """
    throttler = AsyncThrottler(rate, capacity, storage)
    return await throttler.consume(key, amount=amount)


async def async_throttle(
    key: str,
    rate: float,
    capacity: int,
    storage: AsyncBaseStorage,
    amount: int = 1,
    exc_class: Type[Exception] = AsyncThrottled
) -> bool:
    """Async throttle function using the token bucket algorithm.
    
    The token bucket algorithm works as follows:
    - Test if adding the request's cost to the bucket would exceed its capacity
    - If so, return False
    - Otherwise, add the request's cost to the bucket and return True
    - Simultaneously, the bucket's value is decremented at the chosen rate
    
    Args:
        key: The bucket key
        rate: Units regenerated per second
        capacity: Maximum units in the bucket
        storage: Async storage backend
        amount: Number of units to consume
        exc_class: Exception class (kept for compatibility)
        
    Returns:
        True if units were consumed, False otherwise
    """
    throttler = AsyncThrottler(rate, capacity, storage)
    return await throttler.throttle(key, amount=amount, exc_class=exc_class)


# Context manager for auto-cleanup

class AsyncThrottleContext:
    """Async context manager for throttling with automatic cleanup."""
    
    def __init__(
        self,
        key: str,
        rate: float,
        capacity: int,
        storage: Optional[AsyncBaseStorage] = None
    ):
        """Initialize the context manager.
        
        Args:
            key: The bucket key
            rate: Units regenerated per second
            capacity: Maximum units in the bucket
            storage: Async storage backend (defaults to AsyncDictStorage)
        """
        self.key = key
        self.storage = storage or AsyncDictStorage()
        self.throttler = AsyncThrottler(rate, capacity, self.storage)
        self._owned_storage = storage is None
    
    async def __aenter__(self) -> AsyncThrottler:
        """Enter the context."""
        return self.throttler
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and cleanup."""
        if self._owned_storage:
            await self.throttler.close()
    
    async def allowed(self, amount: int = 1) -> bool:
        """Check if request is allowed.
        
        Args:
            amount: Number of units to consume
            
        Returns:
            True if allowed, False otherwise
        """
        return await self.throttler.consume(self.key, amount) 