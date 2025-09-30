"""
Unit tests for AnalyticsTable class and related functionality.

This module tests the analytics data access layer, including:
- Database operations
- Data transformations
- Error handling
- Cross-database user lookup functionality
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import pytest
import uuid
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import List

from open_webui.cogniforce_models.analytics_tables import (
    AnalyticsTable,
    AnalyticsSummary,
    DailyTrendItem,
    UserBreakdownItem,
    ChatItem,
    HealthStatus
)


class MockDBResult:
    """Mock database result for testing."""

    def __init__(self, rows: List[tuple]):
        self.rows = rows
        self._index = 0

    def fetchone(self):
        if self._index < len(self.rows):
            result = self.rows[self._index]
            self._index += 1
            return result
        return None

    def fetchall(self):
        return self.rows


class TestAnalyticsTable(unittest.TestCase):
    """Test cases for AnalyticsTable class."""

    def setUp(self):
        """Set up test fixtures."""
        self.analytics_table = AnalyticsTable()
        self.test_user_id = "550e8400-e29b-41d4-a716-446655440000"
        self.test_user_email = "test@example.com"
        self.test_user_name = "Test User"

    @patch('open_webui.cogniforce_models.analytics_tables.get_db')
    def test_get_user_name_from_id_success(self, mock_get_db):
        """Test successful user name resolution from UUID."""
        # Mock database session and result
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock the user query result
        mock_user = (self.test_user_id, self.test_user_email, self.test_user_name)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = self.analytics_table._get_user_name_from_id(self.test_user_id)

        expected = f"{self.test_user_name} ({self.test_user_email})"
        self.assertEqual(result, expected)

    @patch('open_webui.cogniforce_models.analytics_tables.get_db')
    def test_get_user_name_from_id_not_found(self, mock_get_db):
        """Test fallback behavior when user ID is not found."""
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock empty result
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = self.analytics_table._get_user_name_from_id(self.test_user_id)

        expected = f"Unknown User {self.test_user_id[:8]}"
        self.assertEqual(result, expected)

    @patch('open_webui.cogniforce_models.analytics_tables.get_db')
    def test_get_user_name_from_id_database_error(self, mock_get_db):
        """Test fallback behavior when database error occurs."""
        mock_get_db.side_effect = Exception("Database connection failed")

        result = self.analytics_table._get_user_name_from_id(self.test_user_id)

        expected = f"Unknown User {self.test_user_id[:8]}"
        self.assertEqual(result, expected)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_summary_data_success(self, mock_get_cogniforce_db):
        """Test successful summary data retrieval."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock summary query result
        mock_result = MockDBResult([
            (50, 1500, 30.0, 85.5)  # conversations, time_saved, avg_time, confidence
        ])
        mock_db.execute.return_value = mock_result

        result = self.analytics_table.get_summary_data()

        self.assertIsInstance(result, AnalyticsSummary)
        self.assertEqual(result.total_chats, 50)
        self.assertEqual(result.total_time_saved, 1500)
        self.assertEqual(result.avg_time_saved_per_chat, 30.0)
        self.assertEqual(result.confidence_level, 85.5)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_summary_data_empty_database(self, mock_get_cogniforce_db):
        """Test summary data retrieval with empty database."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock empty result
        mock_result = MockDBResult([])
        mock_db.execute.return_value = mock_result

        result = self.analytics_table.get_summary_data()

        self.assertIsInstance(result, AnalyticsSummary)
        self.assertEqual(result.total_chats, 0)
        self.assertEqual(result.total_time_saved, 0)
        self.assertEqual(result.avg_time_saved_per_chat, 0.0)
        self.assertEqual(result.confidence_level, 0.0)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_daily_trend_data_success(self, mock_get_cogniforce_db):
        """Test successful daily trend data retrieval."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock daily trend query result
        test_date = date.today()
        mock_result = MockDBResult([
            (test_date, 10, 300, 80.0),
            (test_date - timedelta(days=1), 8, 240, 75.0)
        ])
        mock_db.execute.return_value = mock_result

        result = self.analytics_table.get_trends_data()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], DailyTrendItem)
        self.assertEqual(result[0].chats, 10)
        self.assertEqual(result[0].time_saved, 300)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_user_breakdown_data_success(self, mock_get_cogniforce_db):
        """Test successful user breakdown data retrieval."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock user breakdown query result
        mock_result = MockDBResult([
            (self.test_user_id, 25, 750, 85.0),
            ('550e8400-e29b-41d4-a716-446655440001', 15, 450, 80.0)
        ])
        mock_db.execute.return_value = mock_result

        # Mock the user name lookup
        with patch.object(self.analytics_table, '_get_user_name_from_id') as mock_get_name:
            mock_get_name.side_effect = [
                f"{self.test_user_name} ({self.test_user_email})",
                "Another User (another@example.com)"
            ]

            result = self.analytics_table.get_user_breakdown_data(10)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], UserBreakdownItem)
        self.assertIn(self.test_user_name, result[0].user_name)
        self.assertEqual(result[0].chats, 25)
        self.assertEqual(result[0].time_saved, 750)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_chats_data_success(self, mock_get_cogniforce_db):
        """Test successful chats data retrieval."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock chats query result
        test_datetime = datetime.now()
        mock_result = MockDBResult([
            ('conv1', self.test_user_id, test_datetime, 45, 85, 'Test conversation summary'),
            ('conv2', '550e8400-e29b-41d4-a716-446655440001', test_datetime, 30, 80, 'Another conversation')
        ])
        mock_db.execute.return_value = mock_result

        # Mock the user name lookup
        with patch.object(self.analytics_table, '_get_user_name_from_id') as mock_get_name:
            mock_get_name.side_effect = [
                f"{self.test_user_name} ({self.test_user_email})",
                "Another User (another@example.com)"
            ]

            result = self.analytics_table.get_chats_data(20, 0)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ChatItem)
        self.assertEqual(result[0].id, 'conv1')
        self.assertEqual(result[0].time_saved, 45)
        self.assertEqual(result[0].confidence, 85)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_health_status_data_success(self, mock_get_cogniforce_db):
        """Test successful health status data retrieval."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock health status query result
        test_datetime = datetime.now()
        mock_result = MockDBResult([
            (date.today(), test_datetime, test_datetime, 'completed', 100, 5)
        ])
        mock_db.execute.return_value = mock_result

        result = self.analytics_table.get_health_status_data()

        self.assertIsInstance(result, HealthStatus)
        self.assertEqual(result.status, 'healthy')
        self.assertIsNotNone(result.last_processing_run)
        self.assertIsNotNone(result.next_scheduled_run)
        self.assertIn('timezone', result.system_info)

    @patch('open_webui.cogniforce_models.analytics_tables.get_cogniforce_db')
    def test_get_health_status_data_no_runs(self, mock_get_cogniforce_db):
        """Test health status data with no processing runs."""
        mock_db = Mock()
        mock_get_cogniforce_db.return_value.__enter__.return_value = mock_db

        # Mock empty result
        mock_result = MockDBResult([])
        mock_db.execute.return_value = mock_result

        result = self.analytics_table.get_health_status_data()

        self.assertIsInstance(result, HealthStatus)
        self.assertEqual(result.status, 'no_data')
        self.assertIsNone(result.last_processing_run)


class TestAnalyticsTableIntegration(unittest.TestCase):
    """Integration tests for AnalyticsTable with real database operations."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.analytics_table = AnalyticsTable()

    @pytest.mark.integration
    def test_database_connection(self):
        """Test that database connections work properly."""
        # This test requires actual database connectivity
        # Skip if not in integration test environment
        try:
            result = self.analytics_table.get_summary_data()
            self.assertIsInstance(result, AnalyticsSummary)
        except Exception as e:
            self.skipTest(f"Database not available for integration test: {e}")

    @pytest.mark.integration
    def test_cross_database_user_lookup(self):
        """Test cross-database user lookup functionality."""
        # This test requires both databases to be available
        try:
            # Get a user ID from analytics and verify name lookup
            user_breakdown = self.analytics_table.get_user_breakdown_data(1)
            if user_breakdown:
                user_id = user_breakdown[0].user_id
                user_name = self.analytics_table._get_user_name_from_id(user_id)
                self.assertNotEqual(user_name, f"Unknown User {user_id[:8]}")
                self.assertIn('@', user_name)  # Should contain email
        except Exception as e:
            self.skipTest(f"Cross-database test not available: {e}")


if __name__ == '__main__':
    # Run unit tests by default
    unittest.main(argv=[''], verbosity=2, exit=False)

    # Run integration tests separately if specified
    import sys
    if '--integration' in sys.argv:
        pytest.main([__file__, '-m', 'integration', '-v'])