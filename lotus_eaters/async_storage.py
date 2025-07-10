"""Async storage engines for the lotus_eaters library.

This module provides async storage backends for non-blocking rate limiting.
"""

import asyncio
from typing import Optional, Dict, Any, List, Tuple
from redis import asyncio as redis_asyncio
from abc import ABC, abstractmethod

__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"


class AsyncBaseStorage(ABC):
    """Abstract base class for async storage engines."""
    
    @abstractmethod
    async def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieve the current value for a key.
        
        Args:
            key: The key whose value should be retrieved
            default: The value to use when no value exists for the key
            
        Returns:
            The value associated with the key, or default if not found
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any) -> bool:
        """Set a new value for a given key.
        
        Args:
            key: The key to set
            value: The value to associate with the key
            
        Returns:
            True if the operation succeeded
        """
        pass
    
    @abstractmethod
    async def mget(self, *keys: str, default: Optional[Any] = None, coherent: bool = False) -> List[Any]:
        """Retrieve values for a set of keys.
        
        Args:
            keys: The list of keys whose values should be retrieved
            default: The value to use for non-existent keys
            coherent: Whether all fetched values should be coherent
            
        Returns:
            Values for the keys, in the order they were passed
        """
        pass
    
    @abstractmethod
    async def mset(self, values: Dict[str, Any]) -> bool:
        """Set the value of several keys at once.
        
        Args:
            values: Maps keys to their values
            
        Returns:
            True if the operation succeeded
        """
        pass
    
    @abstractmethod
    async def incr(self, key: str, amount: int = 1, default: int = 0) -> int:
        """Increment the value of a key by a given amount.
        
        Args:
            key: The key whose value should be incremented
            amount: The amount by which the value should be incremented
            default: The default value to use if the key was never set
            
        Returns:
            The updated value
        """
        pass
    
    async def close(self) -> None:
        """Close any open connections."""
        pass


class AsyncRedisStorage(AsyncBaseStorage):
    """Async Redis-based storage engine."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 13):
        """Initialize the async Redis storage.
        
        Args:
            redis_url: Redis connection URL
            db: Redis database number
        """
        self.redis_url = redis_url
        self.db = db
        self._client: Optional[redis_asyncio.Redis] = None
        self._lock = asyncio.Lock()
    
    async def _get_client(self) -> redis_asyncio.Redis:
        """Get or create the Redis client."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = redis_asyncio.from_url(
                        self.redis_url,
                        db=self.db,
                        decode_responses=True
                    )
        return self._client
    
    async def get(self, key: str, default: Optional[Any] = 0.0) -> Any:
        """Retrieve the current value for a key."""
        client = await self._get_client()
        result = await client.get(key)
        if result is None:
            return default
        return float(result)
    
    async def set(self, key: str, value: Any) -> bool:
        """Set a new value for a given key."""
        client = await self._get_client()
        return await client.set(key, value)
    
    async def mget(self, *keys: str, default: Optional[Any] = None, coherent: bool = False) -> List[Any]:
        """Retrieve values for a set of keys."""
        client = await self._get_client()
        
        if coherent:
            # Use a pipeline for coherent reads
            async with client.pipeline(transaction=True) as pipe:
                for key in keys:
                    pipe.get(key)
                results = await pipe.execute()
        else:
            results = await client.mget(keys)
        
        return [float(r) if r is not None else default for r in results]
    
    async def mset(self, values: Dict[str, Any]) -> bool:
        """Set the value of several keys at once."""
        client = await self._get_client()
        return await client.mset(values)
    
    async def incr(self, key: str, amount: int = 1, default: int = 0) -> int:
        """Increment the value of a key by a given amount."""
        client = await self._get_client()
        
        # Use Lua script for atomic increment with default
        lua_script = """
        local current = redis.call('GET', KEYS[1])
        if current == false then
            current = ARGV[2]
        end
        local new_value = tonumber(current) + tonumber(ARGV[1])
        redis.call('SET', KEYS[1], new_value)
        return new_value
        """
        
        result = await client.eval(lua_script, 1, key, amount, default)
        return int(result)
    
    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None


class AsyncDictStorage(AsyncBaseStorage):
    """Thread-safe async in-memory storage using a dictionary."""
    
    def __init__(self):
        """Initialize the async dictionary storage."""
        self.data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieve the current value for a key."""
        async with self._lock:
            return self.data.get(key, default)
    
    async def set(self, key: str, value: Any) -> bool:
        """Set a new value for a given key."""
        async with self._lock:
            self.data[key] = value
            return True
    
    async def mget(self, *keys: str, default: Optional[Any] = None, coherent: bool = False) -> List[Any]:
        """Retrieve values for a set of keys."""
        async with self._lock:
            return [self.data.get(key, default) for key in keys]
    
    async def mset(self, values: Dict[str, Any]) -> bool:
        """Set the value of several keys at once."""
        async with self._lock:
            self.data.update(values)
            return True
    
    async def incr(self, key: str, amount: int = 1, default: int = 0) -> int:
        """Increment the value of a key by a given amount."""
        async with self._lock:
            current = int(self.data.get(key, default))
            new_value = current + amount
            self.data[key] = new_value
            return new_value 