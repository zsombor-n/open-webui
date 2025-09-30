"""
Enhanced API Documentation for Analytics Endpoints

This module provides comprehensive documentation, examples, and utility endpoints
for the analytics API system.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict, Any, List
from datetime import datetime

from open_webui.utils.auth import get_admin_user
from open_webui.cogniforce_models.analytics_tables import Analytics
from open_webui.cogniforce_models.analytics_monitoring import get_analytics_monitor
from open_webui.cogniforce_models.analytics_cache import get_analytics_cache

router = APIRouter()


@router.get("/docs/examples", response_model=Dict[str, Any])
async def get_api_examples(user=Depends(get_admin_user)):
    """
    Get comprehensive API usage examples for all analytics endpoints.

    Returns example requests, responses, and common use cases for each endpoint.
    """
    return {
        "api_base_url": "/api/v1/analytics",
        "authentication": {
            "required": True,
            "method": "Bearer Token",
            "role_required": "admin",
            "header_example": "Authorization: Bearer your_jwt_token_here"
        },
        "endpoints": {
            "summary": {
                "url": "/summary",
                "method": "GET",
                "description": "Get overall analytics summary with key metrics",
                "parameters": "None",
                "example_response": {
                    "totalConversations": 150,
                    "totalTimeSaved": 4500,
                    "avgTimeSavedPerConversation": 30.0,
                    "confidenceLevel": 85.2
                },
                "use_cases": [
                    "Dashboard overview display",
                    "Executive reporting",
                    "Performance monitoring alerts"
                ]
            },
            "daily_trend": {
                "url": "/daily-trend",
                "method": "GET",
                "description": "Get time-series data for analytics trending",
                "parameters": {
                    "days": {
                        "type": "integer",
                        "required": False,
                        "default": 7,
                        "range": "1-90",
                        "description": "Number of days to retrieve"
                    }
                },
                "example_request": "/daily-trend?days=30",
                "example_response": {
                    "data": [
                        {
                            "date": "2025-01-20",
                            "conversations": 15,
                            "timeSaved": 450,
                            "avgConfidence": 82.5
                        }
                    ]
                },
                "use_cases": [
                    "Trend analysis charts",
                    "Performance over time visualization",
                    "Seasonal pattern identification"
                ]
            },
            "user_breakdown": {
                "url": "/user-breakdown",
                "method": "GET",
                "description": "Get top users ranked by time saved",
                "parameters": {
                    "limit": {
                        "type": "integer",
                        "required": False,
                        "default": 10,
                        "range": "1-50",
                        "description": "Maximum number of users to return"
                    }
                },
                "example_request": "/user-breakdown?limit=5",
                "example_response": {
                    "users": [
                        {
                            "userIdHash": "a1b2c3d4",
                            "userName": "John Doe (john@example.com)",
                            "conversations": 45,
                            "timeSaved": 1350,
                            "avgConfidence": 88.0
                        }
                    ]
                },
                "use_cases": [
                    "User leaderboards",
                    "Individual performance tracking",
                    "User engagement analysis"
                ]
            },
            "conversations": {
                "url": "/conversations",
                "method": "GET",
                "description": "Get paginated list of analyzed conversations",
                "parameters": {
                    "limit": {
                        "type": "integer",
                        "required": False,
                        "default": 20,
                        "range": "1-100",
                        "description": "Maximum number of conversations to return"
                    },
                    "offset": {
                        "type": "integer",
                        "required": False,
                        "default": 0,
                        "description": "Number of conversations to skip for pagination"
                    }
                },
                "example_request": "/conversations?limit=10&offset=20",
                "example_response": {
                    "conversations": [
                        {
                            "id": "conv_123",
                            "userName": "Jane Smith (jane@example.com)",
                            "createdAt": "2025-01-20T10:30:00",
                            "timeSaved": 25,
                            "confidence": 85,
                            "summary": "Data analysis discussion with AI assistance"
                        }
                    ]
                },
                "use_cases": [
                    "Detailed conversation browsing",
                    "Individual conversation analysis",
                    "Data export preparation"
                ]
            },
            "health": {
                "url": "/health",
                "method": "GET",
                "description": "Get system health and processing status",
                "parameters": "None",
                "example_response": {
                    "status": "healthy",
                    "lastProcessingRun": "2025-01-20T02:00:00",
                    "nextScheduledRun": "2025-01-21T02:00:00",
                    "systemInfo": {
                        "timezone": "UTC",
                        "idleThresholdMinutes": 10,
                        "processingVersion": "1.0",
                        "databaseStatus": "connected"
                    }
                },
                "use_cases": [
                    "System monitoring dashboards",
                    "Health check automation",
                    "Processing status verification"
                ]
            },
            "export": {
                "url": "/export/{format}",
                "method": "GET",
                "description": "Export analytics data in specified format",
                "path_parameters": {
                    "format": {
                        "type": "string",
                        "allowed_values": ["csv"],
                        "description": "Export format (currently only CSV supported)"
                    }
                },
                "query_parameters": {
                    "type": {
                        "type": "string",
                        "required": False,
                        "default": "summary",
                        "allowed_values": ["summary", "daily", "detailed"],
                        "description": "Type of data to export"
                    }
                },
                "example_request": "/export/csv?type=daily",
                "response_type": "File download (CSV)",
                "use_cases": [
                    "Data backup and archival",
                    "External reporting tools",
                    "Compliance and audit requirements"
                ]
            }
        },
        "common_error_responses": {
            "401": {
                "description": "Unauthorized - Invalid or missing authentication token",
                "example": {"detail": "Not authenticated"}
            },
            "403": {
                "description": "Forbidden - User does not have admin role",
                "example": {"detail": "Insufficient permissions"}
            },
            "422": {
                "description": "Validation Error - Invalid request parameters",
                "example": {
                    "detail": [
                        {
                            "loc": ["query", "days"],
                            "msg": "ensure this value is greater than or equal to 1",
                            "type": "value_error.number.not_ge"
                        }
                    ]
                }
            },
            "500": {
                "description": "Internal Server Error - Database or system error",
                "example": {"detail": "Database connection failed"}
            }
        },
        "rate_limiting": {
            "description": "No rate limiting currently implemented",
            "recommendation": "Implement rate limiting for production use"
        },
        "caching": {
            "description": "Response caching is enabled",
            "cache_durations": {
                "summary": "5 minutes",
                "daily_trend": "3 minutes",
                "user_breakdown": "4 minutes",
                "conversations": "2 minutes",
                "health": "1 minute"
            }
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/docs/schema", response_model=Dict[str, Any])
async def get_response_schemas(user=Depends(get_admin_user)):
    """
    Get detailed schema definitions for all API responses.

    Provides complete field descriptions, types, and constraints.
    """
    return {
        "schemas": {
            "AnalyticsSummary": {
                "description": "Overall analytics summary data",
                "fields": {
                    "totalConversations": {
                        "type": "integer",
                        "description": "Total number of analyzed conversations",
                        "minimum": 0
                    },
                    "totalTimeSaved": {
                        "type": "integer",
                        "description": "Total time saved in minutes across all conversations",
                        "minimum": 0
                    },
                    "avgTimeSavedPerConversation": {
                        "type": "number",
                        "description": "Average time saved per conversation in minutes",
                        "minimum": 0.0
                    },
                    "confidenceLevel": {
                        "type": "number",
                        "description": "Average confidence level percentage (0-100)",
                        "minimum": 0.0,
                        "maximum": 100.0
                    }
                }
            },
            "DailyTrendItem": {
                "description": "Single day's analytics data point",
                "fields": {
                    "date": {
                        "type": "string",
                        "format": "date",
                        "description": "Date in ISO format (YYYY-MM-DD)"
                    },
                    "conversations": {
                        "type": "integer",
                        "description": "Number of conversations on this date",
                        "minimum": 0
                    },
                    "timeSaved": {
                        "type": "integer",
                        "description": "Total time saved in minutes on this date",
                        "minimum": 0
                    },
                    "avgConfidence": {
                        "type": "number",
                        "description": "Average confidence level for this date",
                        "minimum": 0.0,
                        "maximum": 100.0
                    }
                }
            },
            "UserBreakdownItem": {
                "description": "Per-user analytics breakdown",
                "fields": {
                    "userIdHash": {
                        "type": "string",
                        "description": "Anonymized user identifier (SHA-256 hash)",
                        "pattern": "^[a-f0-9]{8,64}$"
                    },
                    "userName": {
                        "type": "string",
                        "description": "User display name in format 'Name (email)'"
                    },
                    "conversations": {
                        "type": "integer",
                        "description": "Number of conversations for this user",
                        "minimum": 0
                    },
                    "timeSaved": {
                        "type": "integer",
                        "description": "Total time saved by this user in minutes",
                        "minimum": 0
                    },
                    "avgConfidence": {
                        "type": "number",
                        "description": "Average confidence level for this user",
                        "minimum": 0.0,
                        "maximum": 100.0
                    }
                }
            },
            "ConversationItem": {
                "description": "Individual conversation analytics",
                "fields": {
                    "id": {
                        "type": "string",
                        "description": "Unique conversation identifier"
                    },
                    "userName": {
                        "type": "string",
                        "description": "User who participated in the conversation"
                    },
                    "createdAt": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Conversation creation timestamp in ISO format"
                    },
                    "timeSaved": {
                        "type": "integer",
                        "description": "Time saved for this conversation in minutes",
                        "minimum": 0
                    },
                    "confidence": {
                        "type": "integer",
                        "description": "Confidence level for time estimate (0-100)",
                        "minimum": 0,
                        "maximum": 100
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of the conversation content"
                    }
                }
            },
            "HealthStatus": {
                "description": "System health and status information",
                "fields": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "warning", "error", "no_data"],
                        "description": "Overall system health status"
                    },
                    "lastProcessingRun": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Timestamp of last successful processing run",
                        "nullable": True
                    },
                    "nextScheduledRun": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Timestamp of next scheduled processing run"
                    },
                    "systemInfo": {
                        "type": "object",
                        "description": "Additional system configuration information",
                        "properties": {
                            "timezone": {"type": "string"},
                            "idleThresholdMinutes": {"type": "integer"},
                            "processingVersion": {"type": "string"},
                            "databaseStatus": {"type": "string"}
                        }
                    }
                }
            }
        },
        "field_naming_convention": {
            "description": "API uses camelCase for JSON field names",
            "examples": {
                "database_field": "total_time_saved",
                "json_field": "totalTimeSaved"
            }
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/docs/performance", response_model=Dict[str, Any])
async def get_performance_info(user=Depends(get_admin_user)):
    """
    Get performance metrics and optimization information.

    Shows current system performance, caching status, and optimization tips.
    """
    monitor = get_analytics_monitor()
    cache = get_analytics_cache()

    performance_summary = monitor.get_performance_summary(time_window_minutes=60)
    cache_stats = cache.get_stats()

    return {
        "performance_metrics": performance_summary,
        "cache_status": cache_stats,
        "optimization_tips": [
            "Use appropriate query parameters (e.g., limit conversations results)",
            "Cache responses on the client side for frequently accessed data",
            "Use the daily-trend endpoint with specific day ranges to reduce data transfer",
            "Monitor the health endpoint for system status before making requests",
            "Export large datasets during off-peak hours to reduce system load"
        ],
        "performance_thresholds": {
            "acceptable_response_time": "< 2 seconds",
            "slow_query_threshold": "5 seconds",
            "cache_hit_rate_target": "> 70%",
            "error_rate_threshold": "< 5%"
        },
        "caching_strategy": {
            "summary_data": "5 minutes TTL - Updated less frequently",
            "daily_trends": "3 minutes TTL - Medium volatility",
            "user_breakdown": "4 minutes TTL - Changes with new conversations",
            "conversations": "2 minutes TTL - Most volatile data",
            "health_status": "1 minute TTL - Needs frequent updates"
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/docs/integration-guide", response_class=HTMLResponse)
async def get_integration_guide(user=Depends(get_admin_user)):
    """
    Get comprehensive integration guide as HTML documentation.

    Provides step-by-step integration instructions for different scenarios.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analytics API Integration Guide</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .section { margin: 30px 0; }
            .code-block { background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }
            .endpoint { background: #e8f4fd; padding: 10px; border-left: 4px solid #0066cc; margin: 10px 0; }
            .warning { background: #fff3cd; padding: 10px; border-left: 4px solid #ffa500; margin: 10px 0; }
            .success { background: #d4edda; padding: 10px; border-left: 4px solid #28a745; margin: 10px 0; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Analytics API Integration Guide</h1>

        <div class="section">
            <h2>Quick Start</h2>
            <p>The Analytics API provides comprehensive insights into AI conversation efficiency and time savings.</p>

            <div class="endpoint">
                <strong>Base URL:</strong> /api/v1/analytics<br>
                <strong>Authentication:</strong> Bearer Token (Admin role required)<br>
                <strong>Content-Type:</strong> application/json
            </div>
        </div>

        <div class="section">
            <h2>Authentication Setup</h2>
            <div class="code-block">
                <pre>
# JavaScript/TypeScript Example
const token = 'your_jwt_token_here';
const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
};

const response = await fetch('/api/v1/analytics/summary', {
    method: 'GET',
    headers: headers
});

const data = await response.json();
                </pre>
            </div>

            <div class="warning">
                <strong>Important:</strong> Only admin users can access analytics endpoints.
                Ensure your authentication token has admin privileges.
            </div>
        </div>

        <div class="section">
            <h2>Common Integration Patterns</h2>

            <h3>Dashboard Overview</h3>
            <div class="code-block">
                <pre>
// Fetch all dashboard data in parallel
const [summary, dailyTrend, topUsers] = await Promise.all([
    fetch('/api/v1/analytics/summary', { headers }),
    fetch('/api/v1/analytics/daily-trend?days=30', { headers }),
    fetch('/api/v1/analytics/user-breakdown?limit=5', { headers })
]);

const dashboardData = {
    summary: await summary.json(),
    trends: await dailyTrend.json(),
    topUsers: await topUsers.json()
};
                </pre>
            </div>

            <h3>Real-time Health Monitoring</h3>
            <div class="code-block">
                <pre>
// Check system health periodically
setInterval(async () => {
    try {
        const response = await fetch('/api/v1/analytics/health', { headers });
        const health = await response.json();

        if (health.status !== 'healthy') {
            console.warn('Analytics system health warning:', health);
            // Trigger alerts or notifications
        }
    } catch (error) {
        console.error('Health check failed:', error);
    }
}, 60000); // Check every minute
                </pre>
            </div>

            <h3>Data Export Integration</h3>
            <div class="code-block">
                <pre>
// Export data as CSV
async function exportAnalytics(type = 'summary') {
    const response = await fetch(`/api/v1/analytics/export/csv?type=${type}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `analytics-${type}-${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        window.URL.revokeObjectURL(url);
    }
}
                </pre>
            </div>
        </div>

        <div class="section">
            <h2>Error Handling Best Practices</h2>

            <div class="code-block">
                <pre>
async function fetchAnalytics(endpoint) {
    try {
        const response = await fetch(`/api/v1/analytics/${endpoint}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Redirect to login or refresh token
                throw new Error('Authentication required');
            } else if (response.status === 403) {
                // Show access denied message
                throw new Error('Admin access required');
            } else if (response.status === 404) {
                // Handle API not available
                throw new Error('Analytics API not available');
            } else {
                // Handle other errors
                const error = await response.json();
                throw new Error(error.detail || 'API request failed');
            }
        }

        return await response.json();
    } catch (error) {
        console.error(`Analytics API error for ${endpoint}:`, error);

        // Return fallback data or empty state
        return null;
    }
}
                </pre>
            </div>
        </div>

        <div class="section">
            <h2>Performance Optimization</h2>

            <table>
                <tr>
                    <th>Strategy</th>
                    <th>Implementation</th>
                    <th>Benefits</th>
                </tr>
                <tr>
                    <td>Client-side Caching</td>
                    <td>Cache responses for 2-5 minutes</td>
                    <td>Reduced API calls, faster UI</td>
                </tr>
                <tr>
                    <td>Parallel Requests</td>
                    <td>Use Promise.all() for independent data</td>
                    <td>Faster page loads</td>
                </tr>
                <tr>
                    <td>Pagination</td>
                    <td>Use limit/offset for conversations</td>
                    <td>Reduced memory usage</td>
                </tr>
                <tr>
                    <td>Selective Updates</td>
                    <td>Only refresh changed components</td>
                    <td>Better user experience</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>Production Deployment Checklist</h2>

            <div class="success">
                <h4>✓ Pre-deployment Checklist:</h4>
                <ul>
                    <li>Verify admin authentication is working</li>
                    <li>Test all endpoints with expected data volumes</li>
                    <li>Implement proper error handling for all API calls</li>
                    <li>Set up monitoring for API response times</li>
                    <li>Configure appropriate caching strategies</li>
                    <li>Test export functionality with large datasets</li>
                    <li>Verify health endpoint monitoring setup</li>
                </ul>
            </div>
        </div>

        <div class="section">
            <h2>Troubleshooting Common Issues</h2>

            <h3>Issue: 403 Forbidden Error</h3>
            <p><strong>Cause:</strong> User doesn't have admin role</p>
            <p><strong>Solution:</strong> Verify user has admin privileges in OpenWebUI</p>

            <h3>Issue: Slow Response Times</h3>
            <p><strong>Cause:</strong> Large data volumes or database performance</p>
            <p><strong>Solution:</strong> Use pagination, check system health endpoint</p>

            <h3>Issue: Cache Miss Rates High</h3>
            <p><strong>Cause:</strong> Frequent cache invalidation or low TTL</p>
            <p><strong>Solution:</strong> Review caching strategy, implement client-side caching</p>
        </div>

        <div class="section">
            <h2>Support and Resources</h2>
            <ul>
                <li><strong>API Examples:</strong> GET /api/v1/analytics/docs/examples</li>
                <li><strong>Schema Reference:</strong> GET /api/v1/analytics/docs/schema</li>
                <li><strong>Performance Metrics:</strong> GET /api/v1/analytics/docs/performance</li>
                <li><strong>OpenAPI Specification:</strong> Available in Swagger UI</li>
            </ul>
        </div>

        <footer style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666;">
            <p>Analytics API Integration Guide - Generated on """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </footer>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@router.get("/docs/postman-collection", response_model=Dict[str, Any])
async def get_postman_collection(user=Depends(get_admin_user)):
    """
    Get Postman collection for easy API testing and integration.

    Returns a complete Postman collection with all endpoints and examples.
    """
    return {
        "info": {
            "name": "Analytics API Collection",
            "description": "Complete collection for OpenWebUI Analytics API",
            "version": "1.0.0",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{JWT_TOKEN}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "BASE_URL",
                "value": "http://localhost:8080/api/v1/analytics",
                "type": "string"
            },
            {
                "key": "JWT_TOKEN",
                "value": "your_jwt_token_here",
                "type": "string"
            }
        ],
        "item": [
            {
                "name": "Analytics Summary",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/summary",
                        "host": ["{{BASE_URL}}"],
                        "path": ["summary"]
                    }
                },
                "response": []
            },
            {
                "name": "Daily Trend",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/daily-trend?days=30",
                        "host": ["{{BASE_URL}}"],
                        "path": ["daily-trend"],
                        "query": [
                            {
                                "key": "days",
                                "value": "30"
                            }
                        ]
                    }
                },
                "response": []
            },
            {
                "name": "User Breakdown",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/user-breakdown?limit=10",
                        "host": ["{{BASE_URL}}"],
                        "path": ["user-breakdown"],
                        "query": [
                            {
                                "key": "limit",
                                "value": "10"
                            }
                        ]
                    }
                },
                "response": []
            },
            {
                "name": "System Health",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/health",
                        "host": ["{{BASE_URL}}"],
                        "path": ["health"]
                    }
                },
                "response": []
            },
            {
                "name": "Recent Conversations",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/conversations?limit=20&offset=0",
                        "host": ["{{BASE_URL}}"],
                        "path": ["conversations"],
                        "query": [
                            {
                                "key": "limit",
                                "value": "20"
                            },
                            {
                                "key": "offset",
                                "value": "0"
                            }
                        ]
                    }
                },
                "response": []
            },
            {
                "name": "Export CSV Summary",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/export/csv?type=summary",
                        "host": ["{{BASE_URL}}"],
                        "path": ["export", "csv"],
                        "query": [
                            {
                                "key": "type",
                                "value": "summary"
                            }
                        ]
                    }
                },
                "response": []
            }
        ],
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "// Ensure JWT token is set",
                        "if (!pm.variables.get('JWT_TOKEN') || pm.variables.get('JWT_TOKEN') === 'your_jwt_token_here') {",
                        "    throw new Error('Please set your JWT_TOKEN variable in the collection');",
                        "}"
                    ]
                }
            }
        ]
    }