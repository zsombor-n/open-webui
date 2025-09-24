"""
Analytics Caching Layer

This module provides caching capabilities for analytics data to improve performance:
- In-memory caching with TTL support
- Cache invalidation strategies
- Cache warming for frequently accessed data
- Metrics tracking for cache hit rates
- Thread-safe cache operations
"""
import time
import threading
import logging
from typing import Any, Dict, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import OrderedDict
import json
import hashlib
from functools import wraps

log = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""
    value: Any
    created_at: float
    ttl_seconds: int
    access_count: int = 0
    last_accessed: float = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)

    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


class AnalyticsCache:
    """Thread-safe caching system for analytics data."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize analytics cache.

        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a consistent cache key from function arguments."""
        # Convert arguments to a stable string representation
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        combined = f"{prefix}:{args_str}:{kwargs_str}"

        # Use hash to keep keys reasonably sized
        return hashlib.md5(combined.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                # Track cache miss in OpenTelemetry
                try:
                    from .analytics_otel import track_cache_operation
                    track_cache_operation("get", hit=False)
                except ImportError:
                    pass
                return None

            entry = self._cache[key]

            if entry.is_expired():
                log.debug(f"Cache entry expired: {key}")
                del self._cache[key]
                self.misses += 1
                # Track cache miss in OpenTelemetry
                try:
                    from .analytics_otel import track_cache_operation
                    track_cache_operation("get", hit=False)
                except ImportError:
                    pass
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self.hits += 1

            # Track cache hit in OpenTelemetry
            try:
                from .analytics_otel import track_cache_operation
                track_cache_operation("get", hit=True)
            except ImportError:
                pass

            log.debug(
                "Cache hit",
                extra={
                    "cache_key": key,
                    "age_seconds": time.time() - entry.created_at,
                    "access_count": entry.access_count,
                    "timestamp": datetime.now().isoformat()
                }
            )

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL override."""
        ttl = ttl or self.default_ttl

        with self._lock:
            # Remove oldest entries if cache is full
            while len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self.evictions += 1
                log.debug(f"Evicted cache entry: {oldest_key}")

            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl
            )

            self._cache[key] = entry

            log.debug(
                "Cache entry created",
                extra={
                    "cache_key": key,
                    "ttl_seconds": ttl,
                    "cache_size": len(self._cache),
                    "timestamp": datetime.now().isoformat()
                }
            )

    def delete(self, key: str) -> bool:
        """Delete specific cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                log.debug(f"Cache entry deleted: {key}")
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            log.info(f"Cache cleared: {cleared_count} entries removed")

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching a pattern."""
        with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_delete:
                del self._cache[key]

            log.info(f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}")
            return len(keys_to_delete)

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries."""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

            log.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests) if total_requests > 0 else 0

            # Calculate cache entry statistics
            current_time = time.time()
            entry_ages = [current_time - entry.created_at for entry in self._cache.values()]
            access_counts = [entry.access_count for entry in self._cache.values()]

            return {
                "cache_size": len(self._cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
                "default_ttl": self.default_ttl,
                "avg_entry_age": sum(entry_ages) / len(entry_ages) if entry_ages else 0,
                "avg_access_count": sum(access_counts) / len(access_counts) if access_counts else 0,
                "timestamp": datetime.now().isoformat()
            }

    def warm_cache(self, warm_func: Callable, key: str, *args, **kwargs) -> None:
        """Pre-populate cache with data from a function call."""
        try:
            value = warm_func(*args, **kwargs)
            self.set(key, value)
            log.info(f"Cache warmed for key: {key}")
        except Exception as e:
            log.error(
                "Cache warming failed",
                extra={
                    "cache_key": key,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                exc_info=True
            )


def cached(ttl: int = 300, key_prefix: str = "analytics"):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = analytics_cache._generate_cache_key(
                f"{key_prefix}:{func.__name__}",
                *args,
                **kwargs
            )

            # Try to get from cache
            cached_result = analytics_cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            try:
                result = func(*args, **kwargs)
                analytics_cache.set(cache_key, result, ttl)
                return result

            except Exception as e:
                log.error(
                    "Function execution failed in cached decorator",
                    extra={
                        "function": func.__name__,
                        "cache_key": cache_key,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    },
                    exc_info=True
                )
                raise

        # Add cache control methods to the wrapped function
        wrapper.cache_key_generator = lambda *a, **kw: analytics_cache._generate_cache_key(
            f"{key_prefix}:{func.__name__}", *a, **kw
        )
        wrapper.invalidate_cache = lambda *a, **kw: analytics_cache.delete(
            wrapper.cache_key_generator(*a, **kw)
        )
        wrapper.cache_stats = analytics_cache.get_stats

        return wrapper
    return decorator


class CacheInvalidationStrategy:
    """Strategies for cache invalidation based on data changes."""

    @staticmethod
    def time_based_invalidation(cache_instance: AnalyticsCache, max_age_hours: int = 1):
        """Invalidate cache entries older than specified hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)

        with cache_instance._lock:
            expired_keys = []
            for key, entry in cache_instance._cache.items():
                if entry.created_at < cutoff_time:
                    expired_keys.append(key)

            for key in expired_keys:
                del cache_instance._cache[key]

            log.info(f"Time-based invalidation removed {len(expired_keys)} entries")
            return len(expired_keys)

    @staticmethod
    def data_change_invalidation(cache_instance: AnalyticsCache, operation_type: str):
        """Invalidate cache based on data modification operations."""
        patterns_to_invalidate = {
            "conversation_analysis_updated": ["analytics:get_summary_data", "analytics:get_daily_trend"],
            "daily_aggregates_updated": ["analytics:get_summary_data", "analytics:get_daily_trend", "analytics:get_user_breakdown"],
            "user_data_updated": ["analytics:get_user_breakdown", "analytics:get_conversations"],
            "processing_run_completed": ["analytics:get_health_status"]
        }

        if operation_type in patterns_to_invalidate:
            total_invalidated = 0
            for pattern in patterns_to_invalidate[operation_type]:
                total_invalidated += cache_instance.invalidate_pattern(pattern)

            log.info(f"Data change invalidation removed {total_invalidated} entries for operation: {operation_type}")
            return total_invalidated

        return 0


# Global cache instance
analytics_cache = AnalyticsCache(max_size=500, default_ttl=300)  # 5 minutes default TTL


def get_analytics_cache() -> AnalyticsCache:
    """Get the global analytics cache instance."""
    return analytics_cache


def setup_cache_cleanup_scheduler():
    """Set up periodic cache cleanup (call this during application startup)."""
    import threading

    def cleanup_job():
        while True:
            try:
                # Clean up expired entries every 5 minutes
                analytics_cache.cleanup_expired()

                # Time-based invalidation every hour
                CacheInvalidationStrategy.time_based_invalidation(analytics_cache, max_age_hours=1)

                time.sleep(300)  # 5 minutes

            except Exception as e:
                log.error(
                    "Cache cleanup job failed",
                    extra={
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    },
                    exc_info=True
                )
                time.sleep(60)  # Wait 1 minute before retrying

    # Start cleanup thread as daemon
    cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
    cleanup_thread.start()
    log.info("Cache cleanup scheduler started")


# Cache warming functions for frequently accessed data
def warm_summary_cache():
    """Warm the cache with summary data."""
    from .analytics_tables import Analytics

    try:
        cache_key = analytics_cache._generate_cache_key("analytics:get_summary_data")
        analytics_cache.warm_cache(Analytics.get_summary_data, cache_key)
    except Exception as e:
        log.error(f"Failed to warm summary cache: {e}")


def warm_daily_trend_cache(days: int = 7):
    """Warm the cache with daily trend data."""
    from .analytics_tables import Analytics

    try:
        cache_key = analytics_cache._generate_cache_key("analytics:get_daily_trend_data", days)
        analytics_cache.warm_cache(Analytics.get_daily_trend_data, cache_key, days)
    except Exception as e:
        log.error(f"Failed to warm daily trend cache: {e}")


def warm_analytics_cache():
    """Warm frequently accessed analytics cache entries."""
    log.info("Starting analytics cache warming")

    # Warm summary data
    warm_summary_cache()

    # Warm daily trends for common periods
    for days in [7, 30]:
        warm_daily_trend_cache(days)

    log.info("Analytics cache warming completed")