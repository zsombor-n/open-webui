"""
Analytics OpenTelemetry Integration

Simple integration with OpenWebUI's existing OpenTelemetry infrastructure.
Adds analytics-specific metrics and tracing to the existing observability stack.
"""
import logging
from functools import wraps
from typing import Any, Callable
from datetime import datetime

from opentelemetry import trace, metrics

log = logging.getLogger(__name__)

# Get the existing OpenTelemetry instances (already configured by OpenWebUI)
tracer = trace.get_tracer("analytics")
meter = metrics.get_meter("analytics")

# Analytics-specific metrics
ANALYTICS_REQUESTS = meter.create_counter(
    name="analytics_requests_total",
    description="Total analytics API requests",
    unit="1"
)

ANALYTICS_CACHE_OPERATIONS = meter.create_counter(
    name="analytics_cache_operations_total",
    description="Analytics cache operations",
    unit="1"
)

ANALYTICS_DATABASE_QUERIES = meter.create_histogram(
    name="analytics_database_query_duration_seconds",
    description="Analytics database query duration",
    unit="s"
)

ANALYTICS_ERRORS = meter.create_counter(
    name="analytics_errors_total",
    description="Analytics operation errors",
    unit="1"
)

# User activity metrics
ANALYTICS_USER_OPERATIONS = meter.create_counter(
    name="analytics_user_operations_total",
    description="Analytics operations by user type",
    unit="1"
)


def track_analytics_operation(operation_name: str):
    """
    Decorator to add OpenTelemetry tracing and metrics to analytics operations.

    Uses OpenWebUI's existing OpenTelemetry setup - no additional configuration needed.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a span for this operation
            with tracer.start_as_current_span(f"analytics_{operation_name}") as span:
                try:
                    # Add operation metadata to span
                    span.set_attribute("analytics.operation", operation_name)
                    span.set_attribute("analytics.timestamp", datetime.now().isoformat())

                    # Execute the function
                    result = func(*args, **kwargs)

                    # Record success metrics
                    ANALYTICS_REQUESTS.add(1, {
                        "operation": operation_name,
                        "status": "success"
                    })

                    # Add result metadata to span
                    span.set_attribute("analytics.success", True)
                    if isinstance(result, list):
                        span.set_attribute("analytics.result_count", len(result))
                    elif hasattr(result, '__dict__'):
                        span.set_attribute("analytics.result_type", type(result).__name__)

                    log.info(f"Analytics operation completed: {operation_name}")
                    return result

                except Exception as e:
                    # Record error metrics
                    ANALYTICS_REQUESTS.add(1, {
                        "operation": operation_name,
                        "status": "error"
                    })

                    ANALYTICS_ERRORS.add(1, {
                        "operation": operation_name,
                        "error_type": type(e).__name__
                    })

                    # Add error info to span
                    span.set_attribute("analytics.success", False)
                    span.set_attribute("analytics.error_type", type(e).__name__)
                    span.set_attribute("analytics.error_message", str(e))

                    log.error(f"Analytics operation failed: {operation_name} - {str(e)}")
                    raise

        return wrapper
    return decorator


def track_cache_operation(operation: str, hit: bool = True):
    """Track cache operations in OpenTelemetry metrics."""
    ANALYTICS_CACHE_OPERATIONS.add(1, {
        "operation": operation,
        "result": "hit" if hit else "miss"
    })


def track_user_activity(user_hash: str, operation: str):
    """Track user-specific analytics activity."""
    ANALYTICS_USER_OPERATIONS.add(1, {
        "operation": operation,
        "user_type": "admin"  # All analytics users are admins
    })


def track_database_query(query_type: str, duration_seconds: float):
    """Track database query performance."""
    ANALYTICS_DATABASE_QUERIES.record(duration_seconds, {
        "query_type": query_type
    })


# Context manager for database operations
class DatabaseOperationTracker:
    """Context manager to track database operations with OpenTelemetry."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.span = None
        self.start_time = None

    def __enter__(self):
        self.span = tracer.start_span(f"analytics_db_{self.operation_name}")
        self.span.set_attribute("db.operation", self.operation_name)
        self.span.set_attribute("db.system", "postgresql")
        self.span.set_attribute("db.name", "cogniforce")
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type is None:
                self.span.set_attribute("analytics.success", True)
                duration = (datetime.now() - self.start_time).total_seconds()
                track_database_query(self.operation_name, duration)
            else:
                self.span.set_attribute("analytics.success", False)
                self.span.set_attribute("analytics.error_type", exc_type.__name__)

            self.span.end()


# Simplified logging that integrates with OpenTelemetry
def log_analytics_event(level: str, message: str, **context):
    """
    Log analytics events with OpenTelemetry correlation.

    OpenWebUI's existing logging instrumentor will automatically
    add trace and span IDs to these log entries.
    """
    logger = logging.getLogger("analytics")

    # Add analytics context
    extra_context = {
        "analytics.event": True,
        "analytics.timestamp": datetime.now().isoformat(),
        **context
    }

    if level.upper() == "ERROR":
        logger.error(message, extra=extra_context)
    elif level.upper() == "WARNING":
        logger.warning(message, extra=extra_context)
    else:
        logger.info(message, extra=extra_context)