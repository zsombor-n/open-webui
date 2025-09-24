"""
Integration tests for Analytics API router endpoints.

This module tests the analytics REST API endpoints including:
- Authentication and authorization
- Request/response validation
- Error handling
- Export functionality
"""
import unittest
from unittest.mock import patch, Mock
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
import io
import csv
from datetime import datetime

from open_webui.main import app
from open_webui.cogniforce_models.analytics_tables import (
    AnalyticsSummary,
    DailyTrendItem,
    UserBreakdownItem,
    ConversationItem,
    HealthStatus
)


class TestAnalyticsRouter(unittest.TestCase):
    """Test cases for analytics API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.test_token = "test_jwt_token"
        self.admin_user = {
            "id": "admin_user_id",
            "email": "admin@example.com",
            "role": "admin",
            "name": "Admin User"
        }
        self.regular_user = {
            "id": "regular_user_id",
            "email": "user@example.com",
            "role": "user",
            "name": "Regular User"
        }

    def _get_auth_headers(self):
        """Get authorization headers for testing."""
        return {"Authorization": f"Bearer {self.test_token}"}

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_summary_data')
    def test_get_analytics_summary_success(self, mock_get_summary, mock_get_admin_user):
        """Test successful analytics summary retrieval."""
        # Mock admin user authentication
        mock_get_admin_user.return_value = self.admin_user

        # Mock analytics data
        mock_summary = AnalyticsSummary(
            total_conversations=100,
            total_time_saved=3000,
            avg_time_saved_per_conversation=30.0,
            confidence_level=85.0
        )
        mock_get_summary.return_value = mock_summary

        response = self.client.get(
            "/api/v1/analytics/summary",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["totalConversations"], 100)
        self.assertEqual(data["totalTimeSaved"], 3000)
        self.assertEqual(data["avgTimeSavedPerConversation"], 30.0)
        self.assertEqual(data["confidenceLevel"], 85.0)

    @patch('open_webui.routers.analytics.get_admin_user')
    def test_get_analytics_summary_unauthorized(self, mock_get_admin_user):
        """Test analytics summary with unauthorized user."""
        # Mock authentication failure
        mock_get_admin_user.side_effect = HTTPException(
            status_code=403,
            detail="Forbidden"
        )

        response = self.client.get(
            "/api/v1/analytics/summary",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 403)

    def test_get_analytics_summary_no_auth(self):
        """Test analytics summary without authentication token."""
        response = self.client.get("/api/v1/analytics/summary")

        self.assertEqual(response.status_code, 422)  # Unprocessable Entity due to missing dependency

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_daily_trend_data')
    def test_get_daily_trend_success(self, mock_get_trend, mock_get_admin_user):
        """Test successful daily trend data retrieval."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock trend data
        mock_trend_data = [
            DailyTrendItem(
                date="2025-01-20",
                conversations=15,
                time_saved=450,
                avg_confidence=80.0
            ),
            DailyTrendItem(
                date="2025-01-19",
                conversations=12,
                time_saved=360,
                avg_confidence=82.0
            )
        ]
        mock_get_trend.return_value = mock_trend_data

        response = self.client.get(
            "/api/v1/analytics/daily-trend?days=7",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(data["data"][0]["conversations"], 15)

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_daily_trend_data')
    def test_get_daily_trend_invalid_params(self, mock_get_trend, mock_get_admin_user):
        """Test daily trend with invalid parameters."""
        mock_get_admin_user.return_value = self.admin_user

        # Test invalid days parameter
        response = self.client.get(
            "/api/v1/analytics/daily-trend?days=0",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 422)

        # Test days parameter too high
        response = self.client.get(
            "/api/v1/analytics/daily-trend?days=100",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 422)

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_user_breakdown_data')
    def test_get_user_breakdown_success(self, mock_get_breakdown, mock_get_admin_user):
        """Test successful user breakdown retrieval."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock user breakdown data
        mock_breakdown_data = [
            UserBreakdownItem(
                user_id_hash="hash1",
                user_name="User One (user1@example.com)",
                conversations=25,
                time_saved=750,
                avg_confidence=85.0
            ),
            UserBreakdownItem(
                user_id_hash="hash2",
                user_name="User Two (user2@example.com)",
                conversations=15,
                time_saved=450,
                avg_confidence=80.0
            )
        ]
        mock_get_breakdown.return_value = mock_breakdown_data

        response = self.client.get(
            "/api/v1/analytics/user-breakdown?limit=10",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("users", data)
        self.assertEqual(len(data["users"]), 2)
        self.assertEqual(data["users"][0]["conversations"], 25)

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_health_status_data')
    def test_get_analytics_health_success(self, mock_get_health, mock_get_admin_user):
        """Test successful health status retrieval."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock health status data
        mock_health_data = HealthStatus(
            status="healthy",
            last_processing_run="2025-01-20T10:00:00",
            next_scheduled_run="2025-01-21T00:00:00",
            system_info={
                "timezone": "UTC",
                "idle_threshold_minutes": 10,
                "processing_version": "1.0",
                "database_status": "connected",
                "llm_integration": "ready"
            }
        )
        mock_get_health.return_value = mock_health_data

        response = self.client.get(
            "/api/v1/analytics/health",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("systemInfo", data)

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_conversations_data')
    def test_get_analytics_conversations_success(self, mock_get_conversations, mock_get_admin_user):
        """Test successful conversations retrieval."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock conversations data
        mock_conversations_data = [
            ConversationItem(
                id="conv1",
                user_name="User One (user1@example.com)",
                created_at="2025-01-20T10:00:00",
                time_saved=45,
                confidence=85,
                summary="Test conversation summary"
            ),
            ConversationItem(
                id="conv2",
                user_name="User Two (user2@example.com)",
                created_at="2025-01-20T09:30:00",
                time_saved=30,
                confidence=80,
                summary="Another conversation"
            )
        ]
        mock_get_conversations.return_value = mock_conversations_data

        response = self.client.get(
            "/api/v1/analytics/conversations?limit=20&offset=0",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conversations", data)
        self.assertEqual(len(data["conversations"]), 2)
        self.assertEqual(data["conversations"][0]["id"], "conv1")

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_summary_data')
    def test_export_analytics_csv_summary(self, mock_get_summary, mock_get_admin_user):
        """Test CSV export for summary data."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock summary data
        mock_summary = AnalyticsSummary(
            total_conversations=50,
            total_time_saved=1500,
            avg_time_saved_per_conversation=30.0,
            confidence_level=85.0
        )
        mock_get_summary.return_value = mock_summary

        response = self.client.get(
            "/api/v1/analytics/export/csv?type=summary",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", response.headers["content-disposition"])

        # Parse CSV content
        csv_content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)

        self.assertGreater(len(rows), 1)  # Header + data rows
        self.assertEqual(rows[0], ["Metric", "Value"])
        # Verify summary data is present
        metrics = {row[0]: row[1] for row in rows[1:]}
        self.assertEqual(metrics["Total Conversations"], "50")

    @patch('open_webui.routers.analytics.get_admin_user')
    def test_export_analytics_invalid_format(self, mock_get_admin_user):
        """Test export with invalid format."""
        mock_get_admin_user.return_value = self.admin_user

        response = self.client.get(
            "/api/v1/analytics/export/json?type=summary",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Only CSV format is currently supported", data["detail"])

    @patch('open_webui.routers.analytics.get_admin_user')
    def test_export_analytics_invalid_type(self, mock_get_admin_user):
        """Test export with invalid type."""
        mock_get_admin_user.return_value = self.admin_user

        response = self.client.get(
            "/api/v1/analytics/export/csv?type=invalid",
            headers=self._get_auth_headers()
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Invalid export type", data["detail"])


class TestAnalyticsRouterError(unittest.TestCase):
    """Test error handling in analytics router."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.test_token = "test_jwt_token"
        self.admin_user = {
            "id": "admin_user_id",
            "email": "admin@example.com",
            "role": "admin"
        }

    def _get_auth_headers(self):
        """Get authorization headers for testing."""
        return {"Authorization": f"Bearer {self.test_token}"}

    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_summary_data')
    def test_analytics_database_error(self, mock_get_summary, mock_get_admin_user):
        """Test handling of database errors."""
        mock_get_admin_user.return_value = self.admin_user

        # Mock database error
        mock_get_summary.side_effect = Exception("Database connection failed")

        response = self.client.get(
            "/api/v1/analytics/summary",
            headers=self._get_auth_headers()
        )

        # Should handle gracefully with 500 error
        self.assertEqual(response.status_code, 500)


class TestAnalyticsRouterPerformance(unittest.TestCase):
    """Performance tests for analytics router endpoints."""

    def setUp(self):
        """Set up performance test fixtures."""
        self.client = TestClient(app)
        self.test_token = "test_jwt_token"
        self.admin_user = {
            "id": "admin_user_id",
            "email": "admin@example.com",
            "role": "admin"
        }

    def _get_auth_headers(self):
        """Get authorization headers for testing."""
        return {"Authorization": f"Bearer {self.test_token}"}

    @pytest.mark.performance
    @patch('open_webui.routers.analytics.get_admin_user')
    @patch('open_webui.routers.analytics.Analytics.get_summary_data')
    def test_summary_endpoint_response_time(self, mock_get_summary, mock_get_admin_user):
        """Test that summary endpoint responds within acceptable time."""
        import time

        mock_get_admin_user.return_value = self.admin_user
        mock_summary = AnalyticsSummary(
            total_conversations=1000,
            total_time_saved=30000,
            avg_time_saved_per_conversation=30.0,
            confidence_level=85.0
        )
        mock_get_summary.return_value = mock_summary

        start_time = time.time()
        response = self.client.get(
            "/api/v1/analytics/summary",
            headers=self._get_auth_headers()
        )
        end_time = time.time()

        response_time = end_time - start_time
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 1.0)  # Should respond within 1 second


if __name__ == '__main__':
    # Run unit tests by default
    unittest.main(argv=[''], verbosity=2, exit=False)

    # Run performance tests separately if specified
    import sys
    if '--performance' in sys.argv:
        pytest.main([__file__, '-m', 'performance', '-v'])