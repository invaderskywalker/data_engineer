import re
import time
# import hashlib
# import datetime
import threading
from threading import Lock
from dataclasses import dataclass
from collections import defaultdict
from typing import Any, List, Dict, Optional, Callable



@dataclass
class Flight:
    lock: Lock
    refs: int = 0


class SingleFlightGroup:
    """ Singleflight is not “a lock per key”.It is a shared in-flight state per key with managed lifetime"""

    def __init__(self):
        self._global = Lock()
        self._flights: dict[str, Flight] = {}

    def do(self, key: str, fn: Callable[[], Any]) -> Any:
        with self._global:
            flight = self._flights.get(key)


            if flight is None:
                flight = Flight(Lock(), 0)
                self._flights[key] = flight
                
            flight.refs += 1
            # print(f"[singleflight] key={key} refs={flight.refs} |||| lock_held={flight.lock.locked()}")
        try:
            with flight.lock:
                return fn()
        finally:
            with self._global:
                flight.refs -= 1
                if flight.refs == 0:
                    self._flights.pop(key, None)



class LocalRedisSimulator:
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}
        self._single_flight = SingleFlightGroup()
        self._pubsub_lock = threading.Lock()
        self._channels: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)

    @staticmethod
    def get_key(key: str) -> str:
        """Normalize and return a readable cache key."""
        key = key.strip()
        key = re.sub(r'\[([^\]]*)\]', lambda m: '_'.join(sorted(x.strip(" '\"") for x in m.group(1).split(','))), key)
        return f"{key}"

    def _is_expired(self, entry: dict[str, Any]) -> bool:
        if entry['expiry'] is None:
            return False
        return time.time() > entry['expiry']

    def getter(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache by key."""
        entry = self.store.get(key)
        if not entry or self._is_expired(entry):
            self.store.pop(key, None)
            # print(f"--\nRedis store after cleanup: {len(self.store)}")
            return None
        # print(f"--\nRedis store on get: {self.store.keys()}")
        return entry['value']

    def setter(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """Set a value in the cache with an optional expiration time in seconds."""
        key = key.strip()
        self.store[key] = {'value': value, 'expiry': time.time() + expire if expire else None}
        # print(f"--\nRedis store after set: {self.store.keys()}")

    # def retriever(self, key: str, callback: Callable[[], Any], expire: int) -> Any:
    #     """Retrieve a value from cache or fetch from callback if not found, then cache it."""
    #     cache = self.getter(key)
    #     if cache is not None:
    #         # print(f"---debug returning Redis_cache value------")
    #         return cache
    #     result = callback()
    #     if result is not None:
    #         # print(f"---debug setting Redis_cache value------ {len(result)}")
    #         self.setter(key, result, expire)
    #     return result

    ### using single flight pattern #####
    def retriever(self, key: str, callback: Callable[[], Any], expire: int) -> Any:
        """Retrieve a value from cache or fetch from callback if not found, then cache it."""
        cache = self.getter(key)
        if cache is not None:
            return cache

        # Singleflight: only one callback per key
        def compute():
            # Double-check inside flight
            cache = self.getter(key)
            if cache is not None:
                return cache

            result = callback()
            if result is not None:
                self.setter(key, result, expire)
            return result
        # print("--debug single_flight------------", self._single_flight)
        return self._single_flight.do(key, compute)


    def delete_key(self, key: str) -> None:
        """Delete a key from the cache."""
        self.store.pop(key, None)
        # print(f"--\nRedis store after delete: {self.store.keys()}")


    # Redis Pub/Sub (simulated)
    def publish(self, channel: str, message: Any):
        with self._pubsub_lock:
            subscribers = list(self._channels.get(channel, []))

        for callback in subscribers:
            try:
                callback(message)
            except Exception as e:
                print(f"[LocalRedisSimulator] pubsub error: {e}")

    def subscribe(self, channel: str, callback: Callable[[Any], None]):
        with self._pubsub_lock:
            self._channels[channel].append(callback)

    def unsubscribe(self, channel: str, callback: Callable[[Any], None]):
        with self._pubsub_lock:
            if channel in self._channels:
                self._channels[channel] = [
                    cb for cb in self._channels[channel] if cb != callback
                ]
                if not self._channels[channel]:
                    del self._channels[channel]


class RedClient:
    local_redis = LocalRedisSimulator()

    @staticmethod
    def start_redis() -> None:
        print("Local Redis Simulator started")

    @staticmethod
    def get_key(key: str) -> str:
        return LocalRedisSimulator.get_key(key)

    @classmethod
    def getter(cls, key_set: str) -> Optional[Any]:
        """Get a value from the cache using a key set."""
        redis_key = cls.get_key(key_set)
        print(f"GET {redis_key}")
        return cls.local_redis.getter(redis_key)

    @classmethod
    def retriever(cls, key_set: str, callback: Callable[[], Any], expire: int) -> Any:
        """Retrieve from cache or fetch from DB if not exist, then cache."""
        redis_key = cls.get_key(key_set)
        return cls.local_redis.retriever(redis_key, callback, expire)

    @classmethod
    def setter(cls, key_set: str, value: Any, expire: int) -> None:
        """Set a value in the cache with an expiration time."""
        redis_key = cls.get_key(key_set)
        print(f"SET {redis_key}")
        cls.local_redis.setter(redis_key, value, expire)

    @classmethod
    def delete_key(cls, key_set: str) -> None:
        """Delete a key from the cache."""
        redis_key = cls.get_key(key_set)
        print(f"deleting key... {redis_key}")
        cls.local_redis.delete_key(redis_key)

    @staticmethod
    def execute(query: Callable[[], Any], key_set: str, expire: int = 300) -> Any:
        """Execute a query and cache the result, or return cached result if available."""

        # print(f"debug ... query type: {type(query)}")
        def fetch_from_db() -> Any:
            # print("Fetching from DB...")
            return query()
        
        # print(f"🔄 Fetching from Redis for  {key_set}")
        
        return RedClient.retriever(
            key_set=key_set,
            callback=fetch_from_db,
            expire=expire
        )


    @staticmethod
    def create_key(components: List[Any]):
        return "::".join(components)

    @classmethod
    def publish(cls, channel: str, message: Any):
        cls.local_redis.publish(channel, message)

    @classmethod
    def subscribe(cls, channel: str, callback):
        cls.local_redis.subscribe(channel, callback)

    @classmethod
    def unsubscribe(cls, channel: str, callback):
        cls.local_redis.unsubscribe(channel, callback)