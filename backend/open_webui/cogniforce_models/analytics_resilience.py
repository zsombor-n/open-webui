"""
Analytics Resilience and Error Handling

This module provides robust error handling and resilience patterns:
- Exponential backoff retry logic
- Circuit breaker pattern
- Graceful degradation strategies
- Database connection resilience
- Custom exception classes
"""
import time
import random
import logging
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
from contextlib import contextmanager

log = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for analytics operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        OSError,
    )


class AnalyticsError(Exception):
    """Base exception for analytics operations."""

    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 operation: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.severity = severity
        self.operation = operation
        self.original_error = original_error
        self.timestamp = datetime.now()


class DatabaseConnectionError(AnalyticsError):
    """Database connection related errors."""

    def __init__(self, message: str, database: str = "unknown",
                 original_error: Optional[Exception] = None):
        super().__init__(message, ErrorSeverity.HIGH, "database_connection", original_error)
        self.database = database


class DataValidationError(AnalyticsError):
    """Data validation errors."""

    def __init__(self, message: str, field: Optional[str] = None,
                 value: Optional[Any] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorSeverity.MEDIUM, "data_validation", original_error)
        self.field = field
        self.value = value


class PerformanceError(AnalyticsError):
    """Performance threshold exceeded errors."""

    def __init__(self, message: str, operation: str, duration: float,
                 threshold: float, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorSeverity.LOW, operation, original_error)
        self.duration = duration
        self.threshold = threshold


class CircuitBreakerError(AnalyticsError):
    """Circuit breaker is open - operation blocked."""

    def __init__(self, operation: str):
        super().__init__(
            f"Circuit breaker is open for operation: {operation}",
            ErrorSeverity.HIGH,
            operation
        )


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreaker:
    """Circuit breaker implementation for analytics operations."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if (self.last_failure_time and
                time.time() - self.last_failure_time >= self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                log.info(f"Circuit breaker moving to HALF_OPEN state")
                return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            log.info("Circuit breaker closed - service recovered")

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            log.warning(
                f"Circuit breaker opened due to {self.failure_count} failures"
            )

    @contextmanager
    def protect(self, operation: str):
        """Context manager to protect operations with circuit breaker."""
        if not self.can_execute():
            raise CircuitBreakerError(operation)

        try:
            yield
            self.record_success()

        except self.expected_exception as e:
            self.record_failure()
            raise


def retry_with_exponential_backoff(config: RetryConfig = None):
    """Decorator to add retry logic with exponential backoff."""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts - 1:
                        log.error(
                            "All retry attempts exhausted",
                            extra={
                                "function": func.__name__,
                                "attempts": config.max_attempts,
                                "last_error": str(e),
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        break

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay *= (0.5 + random.random() * 0.5)

                    log.warning(
                        "Retrying operation after failure",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": config.max_attempts,
                            "delay_seconds": delay,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable exception - fail immediately
                    log.error(
                        "Non-retryable error occurred",
                        extra={
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    raise

            # Re-raise the last exception if all retries failed
            raise last_exception

        return wrapper
    return decorator


def async_retry_with_exponential_backoff(config: RetryConfig = None):
    """Async version of retry decorator."""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts - 1:
                        log.error(
                            "All async retry attempts exhausted",
                            extra={
                                "function": func.__name__,
                                "attempts": config.max_attempts,
                                "last_error": str(e),
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        break

                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    if config.jitter:
                        delay *= (0.5 + random.random() * 0.5)

                    log.warning(
                        "Retrying async operation after failure",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": config.max_attempts,
                            "delay_seconds": delay,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    log.error(
                        "Non-retryable async error occurred",
                        extra={
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    raise

            raise last_exception

        return wrapper
    return decorator


class GracefulDegradation:
    """Provides fallback strategies when primary operations fail."""

    @staticmethod
    def with_fallback(primary_func: Callable, fallback_func: Callable,
                     fallback_exceptions: tuple = (Exception,)):
        """Execute primary function with fallback on specific exceptions."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return primary_func(*args, **kwargs)

                except fallback_exceptions as e:
                    log.warning(
                        "Primary function failed, using fallback",
                        extra={
                            "primary_function": primary_func.__name__,
                            "fallback_function": fallback_func.__name__,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        log.error(
                            "Fallback function also failed",
                            extra={
                                "primary_error": str(e),
                                "fallback_error": str(fallback_error),
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        raise

            return wrapper
        return decorator

    @staticmethod
    def empty_response_fallback():
        """Return empty response when operation fails."""
        def fallback(*args, **kwargs):
            return []

        return fallback

    @staticmethod
    def cached_response_fallback(cache_key: str, default_ttl: int = 300):
        """Return cached response when operation fails."""
        # Simple in-memory cache - in production, use Redis or similar
        _cache = {}

        def fallback(*args, **kwargs):
            if cache_key in _cache:
                cached_data, timestamp = _cache[cache_key]
                if time.time() - timestamp < default_ttl:
                    log.info(
                        f"Using cached fallback response for {cache_key}",
                        extra={"cache_age_seconds": time.time() - timestamp}
                    )
                    return cached_data

            # If no valid cache, return empty response
            return []

        return fallback


# Global circuit breakers for different operations
_circuit_breakers = {
    "database_query": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "user_lookup": CircuitBreaker(failure_threshold=5, recovery_timeout=60),
    "export_operation": CircuitBreaker(failure_threshold=2, recovery_timeout=120),
}


def get_circuit_breaker(operation: str) -> CircuitBreaker:
    """Get or create a circuit breaker for the specified operation."""
    if operation not in _circuit_breakers:
        _circuit_breakers[operation] = CircuitBreaker()

    return _circuit_breakers[operation]


def resilient_database_operation(operation_name: str = "database_operation"):
    """Decorator combining retry logic and circuit breaker for database operations."""
    def decorator(func: Callable) -> Callable:
        circuit_breaker = get_circuit_breaker(operation_name)

        @retry_with_exponential_backoff(RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            retryable_exceptions=(ConnectionError, TimeoutError, OSError)
        ))
        @wraps(func)
        def wrapper(*args, **kwargs):
            with circuit_breaker.protect(operation_name):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Convert database-specific exceptions to our custom exceptions
                    if "connection" in str(e).lower():
                        raise DatabaseConnectionError(
                            f"Database connection failed: {str(e)}",
                            original_error=e
                        )
                    raise

        return wrapper
    return decorator