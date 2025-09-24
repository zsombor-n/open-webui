"""
Analytics Performance Monitoring and Metrics Collection

This module provides utilities for monitoring analytics system performance:
- Database query performance tracking
- API endpoint response time metrics
- Error rate monitoring
- Memory and resource usage tracking
- Health check automation
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
import psutil
import os
from contextlib import contextmanager

log = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric record."""
    timestamp: datetime
    operation: str
    duration_seconds: float
    success: bool
    error_type: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """System health snapshot."""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    database_connections: int
    active_requests: int
    error_rate: float
    avg_response_time: float


class AnalyticsMonitor:
    """Performance monitoring system for analytics operations."""

    def __init__(self, max_metrics_history: int = 10000):
        self.metrics_history: deque = deque(maxlen=max_metrics_history)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.active_requests: int = 0
        self._lock = threading.Lock()

        # Performance thresholds
        self.slow_query_threshold = 5.0  # seconds
        self.high_error_rate_threshold = 0.1  # 10%
        self.high_cpu_threshold = 80.0  # 80%
        self.high_memory_threshold = 85.0  # 85%

    def record_metric(self, operation: str, duration: float, success: bool,
                     error_type: Optional[str] = None, **additional_data):
        """Record a performance metric."""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            operation=operation,
            duration_seconds=duration,
            success=success,
            error_type=error_type,
            additional_data=additional_data
        )

        with self._lock:
            self.metrics_history.append(metric)
            self.operation_stats[operation].append(duration)

            # Keep only last 1000 measurements per operation to prevent memory bloat
            if len(self.operation_stats[operation]) > 1000:
                self.operation_stats[operation] = self.operation_stats[operation][-1000:]

            if not success and error_type:
                self.error_counts[error_type] += 1

        # Log performance warnings
        if duration > self.slow_query_threshold:
            log.warning(
                "Slow analytics operation detected",
                extra={
                    "operation": operation,
                    "duration_seconds": duration,
                    "threshold_seconds": self.slow_query_threshold,
                    "timestamp": datetime.now().isoformat(),
                    **additional_data
                }
            )

    @contextmanager
    def track_operation(self, operation: str, **additional_data):
        """Context manager to track operation performance."""
        start_time = time.time()
        self.active_requests += 1

        try:
            yield
            duration = time.time() - start_time
            self.record_metric(operation, duration, True, **additional_data)

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            self.record_metric(operation, duration, False, error_type, **additional_data)
            raise

        finally:
            self.active_requests -= 1

    def get_operation_stats(self, operation: str,
                          time_window_minutes: Optional[int] = None) -> Dict[str, Any]:
        """Get statistics for a specific operation."""
        with self._lock:
            if operation not in self.operation_stats:
                return {
                    "operation": operation,
                    "total_calls": 0,
                    "avg_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0,
                    "error_rate": 0.0
                }

            # Filter by time window if specified
            cutoff_time = None
            if time_window_minutes:
                cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

            relevant_metrics = []
            total_calls = 0
            error_count = 0

            for metric in self.metrics_history:
                if metric.operation == operation:
                    if cutoff_time is None or metric.timestamp >= cutoff_time:
                        relevant_metrics.append(metric.duration_seconds)
                        total_calls += 1
                        if not metric.success:
                            error_count += 1

            if not relevant_metrics:
                return {
                    "operation": operation,
                    "total_calls": 0,
                    "avg_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0,
                    "error_rate": 0.0
                }

            return {
                "operation": operation,
                "total_calls": total_calls,
                "avg_duration": sum(relevant_metrics) / len(relevant_metrics),
                "min_duration": min(relevant_metrics),
                "max_duration": max(relevant_metrics),
                "error_rate": error_count / total_calls if total_calls > 0 else 0.0,
                "time_window_minutes": time_window_minutes
            }

    def get_system_health(self) -> SystemHealth:
        """Get current system health snapshot."""
        try:
            # Get system resource usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Calculate error rate over last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_metrics = [m for m in self.metrics_history
                            if m.timestamp >= one_hour_ago]

            total_recent = len(recent_metrics)
            error_recent = sum(1 for m in recent_metrics if not m.success)
            error_rate = error_recent / total_recent if total_recent > 0 else 0.0

            # Calculate average response time
            recent_durations = [m.duration_seconds for m in recent_metrics]
            avg_response_time = (sum(recent_durations) / len(recent_durations)
                               if recent_durations else 0.0)

            return SystemHealth(
                timestamp=datetime.now(),
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory.percent,
                disk_usage_percent=disk.percent,
                database_connections=self._estimate_db_connections(),
                active_requests=self.active_requests,
                error_rate=error_rate,
                avg_response_time=avg_response_time
            )

        except Exception as e:
            log.error(
                "Failed to collect system health metrics",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                exc_info=True
            )

            # Return basic health info on error
            return SystemHealth(
                timestamp=datetime.now(),
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                disk_usage_percent=0.0,
                database_connections=0,
                active_requests=self.active_requests,
                error_rate=0.0,
                avg_response_time=0.0
            )

    def _estimate_db_connections(self) -> int:
        """Estimate current database connections."""
        try:
            # Count active database connections by checking open file descriptors
            # This is an approximation and may not be perfectly accurate
            process = psutil.Process(os.getpid())
            connections = process.connections()
            # Filter for database-like connections (PostgreSQL typically uses port 5432)
            db_connections = [c for c in connections
                            if hasattr(c, 'raddr') and c.raddr
                            and c.raddr.port in [5432, 5433, 5434]]
            return len(db_connections)
        except Exception:
            return 0

    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

        with self._lock:
            recent_metrics = [m for m in self.metrics_history
                            if m.timestamp >= cutoff_time]

        if not recent_metrics:
            return {
                "time_window_minutes": time_window_minutes,
                "total_operations": 0,
                "unique_operations": 0,
                "overall_error_rate": 0.0,
                "average_duration": 0.0,
                "operations": {},
                "system_health": self.get_system_health()
            }

        # Group by operation
        operations_summary = {}
        for operation in set(m.operation for m in recent_metrics):
            operations_summary[operation] = self.get_operation_stats(
                operation, time_window_minutes
            )

        total_operations = len(recent_metrics)
        total_errors = sum(1 for m in recent_metrics if not m.success)
        overall_error_rate = total_errors / total_operations if total_operations > 0 else 0.0

        durations = [m.duration_seconds for m in recent_metrics]
        average_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "time_window_minutes": time_window_minutes,
            "total_operations": total_operations,
            "unique_operations": len(operations_summary),
            "overall_error_rate": overall_error_rate,
            "average_duration": average_duration,
            "operations": operations_summary,
            "system_health": self.get_system_health(),
            "alerts": self._generate_alerts()
        }

    def _generate_alerts(self) -> List[Dict[str, Any]]:
        """Generate performance alerts based on thresholds."""
        alerts = []
        health = self.get_system_health()

        # CPU usage alert
        if health.cpu_usage_percent > self.high_cpu_threshold:
            alerts.append({
                "type": "high_cpu_usage",
                "level": "warning",
                "message": f"CPU usage is {health.cpu_usage_percent:.1f}% (threshold: {self.high_cpu_threshold}%)",
                "value": health.cpu_usage_percent,
                "threshold": self.high_cpu_threshold
            })

        # Memory usage alert
        if health.memory_usage_percent > self.high_memory_threshold:
            alerts.append({
                "type": "high_memory_usage",
                "level": "warning",
                "message": f"Memory usage is {health.memory_usage_percent:.1f}% (threshold: {self.high_memory_threshold}%)",
                "value": health.memory_usage_percent,
                "threshold": self.high_memory_threshold
            })

        # Error rate alert
        if health.error_rate > self.high_error_rate_threshold:
            alerts.append({
                "type": "high_error_rate",
                "level": "critical",
                "message": f"Error rate is {health.error_rate:.1%} (threshold: {self.high_error_rate_threshold:.1%})",
                "value": health.error_rate,
                "threshold": self.high_error_rate_threshold
            })

        return alerts

    def clear_old_metrics(self, days_to_keep: int = 7):
        """Clear metrics older than specified days."""
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)

        with self._lock:
            # Filter metrics history
            self.metrics_history = deque(
                (m for m in self.metrics_history if m.timestamp >= cutoff_time),
                maxlen=self.metrics_history.maxlen
            )

        log.info(
            "Cleared old performance metrics",
            extra={
                "days_kept": days_to_keep,
                "remaining_metrics": len(self.metrics_history),
                "timestamp": datetime.now().isoformat()
            }
        )


# Global analytics monitor instance
analytics_monitor = AnalyticsMonitor()


def get_analytics_monitor() -> AnalyticsMonitor:
    """Get the global analytics monitor instance."""
    return analytics_monitor