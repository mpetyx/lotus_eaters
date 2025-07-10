"""Async bucket implementation for the token bucket algorithm.

This module provides the async version of the token bucket algorithm.
"""

import asyncio
import time
from typing import Optional

from .async_storage import AsyncBaseStorage

__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"


class AsyncBucket:
    """An async token bucket implementation.
    
    A bucket "leaks" queries at a rate of ``rate`` per second,
    and has a maximum capacity of ``capacity``.
    When a new request arrives (call to ``consume()``), the bucket checks that
    it can add it without exceeding capacity; otherwise, it is rejected.
    
    Attributes:
        key: The base namespace used by this bucket
        rate: The rate at which consumed units are regenerated, in units per second
        capacity: The maximum amount of units in the bucket
        storage: An async storage engine for this bucket
    """
    
    def __init__(self, key: str, rate: float, capacity: int, storage: AsyncBaseStorage):
        """Initialize the async bucket.
        
        Args:
            key: The base namespace for this bucket
            rate: Units regenerated per second
            capacity: Maximum units in the bucket
            storage: Async storage backend
        """
        self.key = key
        self.rate = rate
        self.capacity = capacity
        self.storage = storage
        self._lock = asyncio.Lock()
    
    @property
    def key_amount(self) -> str:
        """Name of the key used to store the current amount."""
        return f'{self.key}:current-amount'
    
    @property
    def key_last_leak(self) -> str:
        """Name of the key used to store the time of the last leak."""
        return f'{self.key}:last-leak'
    
    async def leak(self) -> int:
        """Leak the adequate amount of data from the bucket.
        
        This should be called before any consumption takes place.
        
        Returns:
            The new capacity of the bucket
        """
        # Get current values atomically
        values = await self.storage.mget(
            self.key_amount, 
            self.key_last_leak,
            coherent=True
        )
        current_amount = values[0] if values[0] is not None else 0
        last_leak = values[1]
        
        now = time.time()
        
        if last_leak is not None:
            elapsed = now - float(last_leak)
            decrement = elapsed * self.rate
            # Convert to float first to handle the decrement properly, then to int
            # Note: +1 is added to match the original implementation's behavior
            new_amount = max(int(float(current_amount) - decrement) + 1, 0)
        else:
            new_amount = 0
        
        # Update storage
        await self.storage.mset({
            self.key_amount: new_amount,
            self.key_last_leak: now,
        })
        
        return new_amount
    
    async def consume(self, amount: int = 1) -> bool:
        """Consume one or more units from the bucket.
        
        Args:
            amount: Number of units to consume
            
        Returns:
            True if the units could be consumed, False otherwise
        """
        async with self._lock:
            # First, cleanup old stock
            current = await self.leak()
            
            if current + amount > self.capacity:
                return False
            
            # Increment the amount
            await self.storage.incr(self.key_amount, amount)
            return True
    
    async def remaining(self) -> int:
        """Get the number of remaining tokens in the bucket.
        
        Returns:
            Number of tokens available for consumption
        """
        # Get current values without modifying them
        values = await self.storage.mget(
            self.key_amount, 
            self.key_last_leak,
            coherent=True
        )
        current_amount = values[0] if values[0] is not None else 0
        last_leak = values[1]
        
        # Calculate how much would have leaked
        if last_leak is not None:
            now = time.time()
            elapsed = now - float(last_leak)
            decrement = elapsed * self.rate
            # Match the +1 behavior of the leak method
            effective_amount = max(float(current_amount) - decrement + 1, 0)
        else:
            # Initial state: no tokens consumed yet
            # But to match the +1 quirk behavior, we need to account for it
            effective_amount = 1 if current_amount == 0 else 0
            
        return max(int(self.capacity - effective_amount), 0)
    
    async def reset(self) -> None:
        """Reset the bucket to empty state."""
        await self.storage.mset({
            self.key_amount: 0,
            self.key_last_leak: time.time(),
        }) 