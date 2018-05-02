__author__ = 'mpetyx (Michael Petychakis)'
__version__ = "1.0.0"
__maintainer__ = "Michael Petychakis"
__email__ = "hello@apilama.com"
__status__ = "Production"

"""Base storage engines.
This module holds a few storage backends to be used for storing current bucket state.
"""

from redis.client import Redis

class BaseStorage(object):
    """Base class for a storage engine.
    Such objects provide a general abstraction over various storage backends
    (in-memory dict, remote cache, ...)
    """

    def __init__(self, client=None):
        if not client:
            self.client = Redis(host='localhost', port=6379, db=13, password=None)
        else:
            self.client = client

    def get(self, key, default=0.0):
        """Retrieve the current value for a key.
        Args:
            key (str): the key whose value should be retrieved
            default (object): the value to use when no value exist for the key
        """
        result =  self.client.get(key)
        if not result:
            return default
        else:
            return float(result)
        # raise NotImplementedError()

    def set(self, key, value):
        """Set a new value for a given key."""
        return self.client.set(key,value)
        # raise NotImplementedError()

    def mget(self, *keys, **kwargs):
        """Retrieve values for a set of keys.
        Args:
            keys (str list): the list of keys whose value should be retrieved
        Keyword arguements:
            default (object): the value to use for non-existent keys
            coherent (bool): whether all fetched values should be "coherent",
                i.e no other update was performed on any of those values while
                fetching from the database.
        Yields:
            object: values for the keys, in the order they were passed
        """
        default = kwargs.get('default')
        coherent = kwargs.get('coherent', False)
        for key in keys:
            yield self.get(key, default=default)

    def mset(self, values):
        """Set the value of several keys at once.
        Args:
            values (dict): maps a key to its value.
        """
        for key, value in values.items():
            self.set(key, value)

    def incr(self, key, amount=1, default=0):
        """Increment the value of a key by a given amount.
        Also works for decrementing it.
        Args:
            key (str): the key whose value should be incremented
            amount (int): the amount by which the value should be incremented
            default (int): the default value to use if the key was never set
        Returns:
            int, the updated value
        """
        # import pdb;pdb.set_trace()
        value = int(self.get(key, default)) + int(amount)
        self.set(key, value )
        return value


class DictStorage(BaseStorage):
    """A simple storage, backed by a dict."""
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
