"""Unit tests for the storage module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from lotus_eaters.storage import BaseStorage, DictStorage
from redis.exceptions import ConnectionError


class TestDictStorage(unittest.TestCase):
    """Test cases for DictStorage class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = DictStorage()
    
    def test_init(self):
        """Test DictStorage initialization."""
        storage = DictStorage()
        self.assertIsInstance(storage.data, dict)
        self.assertEqual(len(storage.data), 0)
    
    def test_get_nonexistent_key(self):
        """Test getting a non-existent key returns default."""
        self.assertIsNone(self.storage.get('nonexistent'))
        self.assertEqual(self.storage.get('nonexistent', 'default'), 'default')
    
    def test_set_and_get(self):
        """Test setting and getting values."""
        self.storage.set('key1', 'value1')
        self.assertEqual(self.storage.get('key1'), 'value1')
        
        self.storage.set('key2', 42)
        self.assertEqual(self.storage.get('key2'), 42)
    
    def test_overwrite_value(self):
        """Test overwriting an existing value."""
        self.storage.set('key', 'value1')
        self.storage.set('key', 'value2')
        self.assertEqual(self.storage.get('key'), 'value2')
    
    def test_mget(self):
        """Test getting multiple values at once."""
        self.storage.set('key1', 'value1')
        self.storage.set('key2', 'value2')
        
        values = list(self.storage.mget('key1', 'key2', 'key3'))
        self.assertEqual(values, ['value1', 'value2', None])
        
        values_with_default = list(self.storage.mget('key1', 'key2', 'key3', default='missing'))
        self.assertEqual(values_with_default, ['value1', 'value2', 'missing'])
    
    def test_mset(self):
        """Test setting multiple values at once."""
        values = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'
        }
        self.storage.mset(values)
        
        self.assertEqual(self.storage.get('key1'), 'value1')
        self.assertEqual(self.storage.get('key2'), 'value2')
        self.assertEqual(self.storage.get('key3'), 'value3')
    
    def test_incr(self):
        """Test incrementing values."""
        # Test increment on non-existent key
        result = self.storage.incr('counter')
        self.assertEqual(result, 1)
        self.assertEqual(self.storage.get('counter'), 1)
        
        # Test increment existing key
        result = self.storage.incr('counter')
        self.assertEqual(result, 2)
        self.assertEqual(self.storage.get('counter'), 2)
        
        # Test increment by specific amount
        result = self.storage.incr('counter', 5)
        self.assertEqual(result, 7)
        self.assertEqual(self.storage.get('counter'), 7)
        
        # Test decrement (negative increment)
        result = self.storage.incr('counter', -3)
        self.assertEqual(result, 4)
        self.assertEqual(self.storage.get('counter'), 4)
        
        # Test with custom default
        result = self.storage.incr('new_counter', 1, default=10)
        self.assertEqual(result, 11)


class TestBaseStorage(unittest.TestCase):
    """Test cases for BaseStorage class with Redis."""
    
    @patch('lotus_eaters.storage.Redis')
    def test_init_without_client(self, mock_redis):
        """Test BaseStorage initialization without providing a client."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        
        storage = BaseStorage()
        
        mock_redis.assert_called_once_with(host='localhost', port=6379, db=13, password=None)
        self.assertEqual(storage.client, mock_client)
    
    def test_init_with_client(self):
        """Test BaseStorage initialization with a provided client."""
        mock_client = Mock()
        storage = BaseStorage(client=mock_client)
        self.assertEqual(storage.client, mock_client)
    
    @patch('lotus_eaters.storage.Redis')
    def test_get(self, mock_redis):
        """Test getting values from Redis."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        # Test when key exists
        mock_client.get.return_value = b'3.14'
        result = storage.get('key1')
        self.assertEqual(result, 3.14)
        mock_client.get.assert_called_with('key1')
        
        # Test when key doesn't exist
        mock_client.get.return_value = None
        result = storage.get('nonexistent')
        self.assertEqual(result, 0.0)
        
        # Test with custom default
        result = storage.get('nonexistent', default=42.0)
        self.assertEqual(result, 42.0)
    
    @patch('lotus_eaters.storage.Redis')
    def test_set(self, mock_redis):
        """Test setting values in Redis."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        storage.set('key1', 'value1')
        mock_client.set.assert_called_once_with('key1', 'value1')
    
    @patch('lotus_eaters.storage.Redis')
    def test_mget(self, mock_redis):
        """Test getting multiple values."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        # Setup mock responses
        def get_side_effect(key):
            responses = {
                'key1': b'1.0',
                'key2': b'2.0',
                'key3': None
            }
            return responses.get(key)
        
        mock_client.get.side_effect = get_side_effect
        
        values = list(storage.mget('key1', 'key2', 'key3'))
        self.assertEqual(values, [1.0, 2.0, 0.0])
        
        values_with_default = list(storage.mget('key1', 'key2', 'key3', default=99.0))
        self.assertEqual(values_with_default, [1.0, 2.0, 99.0])
    
    @patch('lotus_eaters.storage.Redis')
    def test_mset(self, mock_redis):
        """Test setting multiple values."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        values = {'key1': 'value1', 'key2': 'value2'}
        storage.mset(values)
        
        expected_calls = [
            unittest.mock.call('key1', 'value1'),
            unittest.mock.call('key2', 'value2')
        ]
        mock_client.set.assert_has_calls(expected_calls, any_order=True)
    
    @patch('lotus_eaters.storage.Redis')
    def test_incr(self, mock_redis):
        """Test incrementing values."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        # Test increment on existing key
        mock_client.get.return_value = b'5'
        result = storage.incr('counter', 3)
        self.assertEqual(result, 8)
        mock_client.set.assert_called_with('counter', 8)
        
        # Test increment on non-existent key
        mock_client.get.return_value = None
        result = storage.incr('new_counter', 1, default=10)
        self.assertEqual(result, 11)
        mock_client.set.assert_called_with('new_counter', 11)
    
    @patch('lotus_eaters.storage.Redis')
    def test_coherent_mget(self, mock_redis):
        """Test mget with coherent flag (though it's not implemented differently)."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        storage = BaseStorage()
        
        mock_client.get.return_value = b'1.0'
        values = list(storage.mget('key1', 'key2', coherent=True))
        self.assertEqual(len(values), 2)


if __name__ == '__main__':
    unittest.main() 