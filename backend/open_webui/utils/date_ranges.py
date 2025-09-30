"""
Date range utilities using Pendulum for consistent date calculations.

This module provides centralized date range calculation logic with proper
week boundary handling (Monday as start of week) and timezone awareness.
"""

import pendulum
from typing import Tuple
from datetime import date


def calculate_date_range(range_type: str) -> Tuple[date, date]:
    """
    Calculate date ranges using Pendulum with Monday as start of week.

    Args:
        range_type: One of 'this_week', 'last_week', 'this_month', 'last_month',
                   'this_quarter', 'last_quarter', 'this_year', 'last_year'

    Returns:
        Tuple of (start_date, end_date) as date objects.
        'This' periods include today. 'Last' periods are complete periods.
    """
    today = pendulum.today()

    if range_type == 'this_week':
        # Monday of current week to today (inclusive)
        start = today.start_of('week')  # Monday
        end = today

    elif range_type == 'last_week':
        # Previous full week (Monday to Sunday)
        last_week = today.subtract(weeks=1)
        start = last_week.start_of('week')  # Monday
        end = last_week.end_of('week')  # Sunday

    elif range_type == 'this_month':
        # First day of current month to today
        start = today.start_of('month')
        end = today

    elif range_type == 'last_month':
        # Previous full month
        last_month = today.subtract(months=1)
        start = last_month.start_of('month')
        end = last_month.end_of('month')

    elif range_type == 'this_quarter':
        # First day of current quarter to today
        start = today.start_of('quarter')
        end = today

    elif range_type == 'last_quarter':
        # Previous full quarter
        last_quarter = today.subtract(months=3)
        start = last_quarter.start_of('quarter')
        end = last_quarter.end_of('quarter')

    elif range_type == 'this_year':
        # January 1st to today
        start = today.start_of('year')
        end = today

    elif range_type == 'last_year':
        # Previous full year
        last_year = today.subtract(years=1)
        start = last_year.start_of('year')
        end = last_year.end_of('year')

    else:
        # Default to this week
        start = today.start_of('week')
        end = today

    # Convert to Python date objects for compatibility with existing code
    return start.date(), end.date()


def format_date_range(start_date: date, end_date: date) -> str:
    """
    Format a date range for human-readable display.

    Args:
        start_date: Start of range
        end_date: End of range

    Returns:
        Formatted string like "Jan 20 - Jan 26, 2025"
    """
    start_pendulum = pendulum.instance(start_date)
    end_pendulum = pendulum.instance(end_date)

    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            # Same month: "Jan 20-26, 2025"
            return f"{start_pendulum.format('MMM D')}-{end_pendulum.format('D, YYYY')}"
        else:
            # Different months same year: "Jan 20 - Feb 26, 2025"
            return f"{start_pendulum.format('MMM D')} - {end_pendulum.format('MMM D, YYYY')}"
    else:
        # Different years: "Dec 20, 2024 - Jan 26, 2025"
        return f"{start_pendulum.format('MMM D, YYYY')} - {end_pendulum.format('MMM D, YYYY')}"


def get_date_range_description(range_type: str) -> str:
    """
    Get a human-readable description of what a range type represents.

    Args:
        range_type: The range type identifier

    Returns:
        Human-readable description
    """
    descriptions = {
        'this_week': 'This Week (Monday to Today)',
        'last_week': 'Last Week (Monday to Sunday)',
        'this_month': 'This Month (1st to Today)',
        'last_month': 'Last Month (Complete)',
        'this_quarter': 'This Quarter (Start to Today)',
        'last_quarter': 'Last Quarter (Complete)',
        'this_year': 'This Year (Jan 1 to Today)',
        'last_year': 'Last Year (Complete)'
    }
    return descriptions.get(range_type, 'Custom Range')