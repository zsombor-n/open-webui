import logging
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from functools import wraps
import io
import csv

from open_webui.utils.auth import get_admin_user
from open_webui.cogniforce_models.analytics_tables import (
    Analytics,
    AnalyticsSummary,
    DailyTrendItem,
    UserBreakdownItem,
    ConversationItem,
    HealthStatus,
)

log = logging.getLogger(__name__)


def log_api_request(endpoint_name: str):
    """Decorator to log API requests and responses for analytics endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())[:8]
            start_time = time.time()

            # Extract request object from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            # Log request
            log.info(
                "Analytics API request started",
                extra={
                    "endpoint": endpoint_name,
                    "request_id": request_id,
                    "method": request.method if request else "UNKNOWN",
                    "url": str(request.url) if request else "UNKNOWN",
                    "user_agent": request.headers.get("user-agent", "unknown") if request else "unknown",
                    "timestamp": datetime.now().isoformat()
                }
            )

            try:
                # Execute the endpoint function
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Log successful response
                log.info(
                    "Analytics API request completed successfully",
                    extra={
                        "endpoint": endpoint_name,
                        "request_id": request_id,
                        "duration_seconds": round(duration, 3),
                        "status_code": 200,
                        "response_type": type(result).__name__,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                return result

            except HTTPException as e:
                duration = time.time() - start_time

                log.warning(
                    "Analytics API request failed with HTTP error",
                    extra={
                        "endpoint": endpoint_name,
                        "request_id": request_id,
                        "duration_seconds": round(duration, 3),
                        "status_code": e.status_code,
                        "error_detail": e.detail,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                raise

            except Exception as e:
                duration = time.time() - start_time

                log.error(
                    "Analytics API request failed with unexpected error",
                    extra={
                        "endpoint": endpoint_name,
                        "request_id": request_id,
                        "duration_seconds": round(duration, 3),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp": datetime.now().isoformat()
                    },
                    exc_info=True
                )

                raise

        return wrapper
    return decorator

router = APIRouter()


# Wrapper response models for array endpoints
from pydantic import BaseModel
from typing import List

class DailyTrendResponse(BaseModel):
    data: List[DailyTrendItem]

class UserBreakdownResponse(BaseModel):
    users: List[UserBreakdownItem]

class ConversationsResponse(BaseModel):
    conversations: List[ConversationItem]




############################
# Analytics Endpoints
############################

@router.get("/summary", response_model=AnalyticsSummary)
@log_api_request("analytics_summary")
async def get_analytics_summary(user=Depends(get_admin_user)):
    """
    Get analytics summary including total conversations, time saved,
    average per conversation, and confidence level.
    """
    return Analytics.get_summary_data()


@router.get("/daily-trend", response_model=DailyTrendResponse)
@log_api_request("analytics_daily_trend")
async def get_daily_trend(
    days: int = Query(7, ge=1, le=90, description="Number of days to retrieve"),
    user=Depends(get_admin_user)
):
    """
    Get daily analytics trend data for the specified number of days.
    """
    trend_data = Analytics.get_daily_trend_data(days)
    return DailyTrendResponse(data=trend_data)


@router.get("/user-breakdown", response_model=UserBreakdownResponse)
@log_api_request("analytics_user_breakdown")
async def get_user_breakdown(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of users to return"),
    user=Depends(get_admin_user)
):
    """
    Get top users by time saved with their conversation counts and average confidence.
    """
    users = Analytics.get_user_breakdown_data(limit)
    return UserBreakdownResponse(users=users)


@router.get("/health", response_model=HealthStatus)
@log_api_request("analytics_health")
async def get_analytics_health(user=Depends(get_admin_user)):
    """
    Get analytics system health status and configuration information.
    """
    return Analytics.get_health_status_data()


@router.get("/conversations", response_model=ConversationsResponse)
@log_api_request("analytics_conversations")
async def get_analytics_conversations(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    user=Depends(get_admin_user)
):
    """
    Get recent conversations with analytics data.
    """
    conversations = Analytics.get_conversations_data(limit, offset)
    return ConversationsResponse(conversations=conversations)


@router.get("/export/{format}")
@log_api_request("analytics_export")
async def export_analytics_data(
    format: str,
    type: str = Query("summary", description="Export type: summary, daily, detailed"),
    user=Depends(get_admin_user)
):
    """
    Export analytics data in the specified format.
    Currently supports CSV format.
    """
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is currently supported")

    # Generate CSV data based on type
    output = io.StringIO()
    writer = csv.writer(output)

    if type == "summary":
        summary_data = Analytics.get_summary_data()
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Conversations", summary_data.total_conversations])
        writer.writerow(["Total Time Saved (minutes)", summary_data.total_time_saved])
        writer.writerow(["Average Time Saved per Conversation", summary_data.avg_time_saved_per_conversation])
        writer.writerow(["Confidence Level", summary_data.confidence_level])

    elif type == "daily":
        writer.writerow(["Date", "Conversations", "Time Saved", "Avg Confidence"])
        daily_data = Analytics.get_daily_trend_data(30)  # Last 30 days for export
        for item in daily_data:
            writer.writerow([item.date, item.conversations, item.time_saved, item.avg_confidence])

    elif type == "detailed":
        writer.writerow(["Conversation ID", "User", "Created At", "Time Saved", "Confidence", "Summary"])
        conversations = Analytics.get_conversations_data(1000, 0)  # Large limit for export
        for conv in conversations:
            writer.writerow([conv.id, conv.user_name, conv.created_at, conv.time_saved, conv.confidence, conv.summary])

    else:
        raise HTTPException(status_code=400, detail="Invalid export type. Use: summary, daily, or detailed")

    # Prepare the response
    output.seek(0)
    filename = f"analytics-{type}-export-{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/trigger-processing")
@log_api_request("trigger_processing")
async def trigger_analytics_processing(
    date: str = None,
    user=Depends(get_admin_user)
):
    """
    Manually trigger analytics processing for testing or on-demand processing.
    If no date provided, processes yesterday's data.

    Args:
        date: Optional date in YYYY-MM-DD format

    Returns:
        Processing status and details
    """
    try:
        from datetime import datetime, date as dt, timedelta
        from open_webui.services.analytics_processor import AnalyticsProcessor
        from open_webui.config import (
            ANALYTICS_OPENAI_API_KEY,
            ANALYTICS_MODEL,
            ENABLE_ANALYTICS_PROCESSING
        )

        # Check if analytics processing is enabled
        if not ENABLE_ANALYTICS_PROCESSING.value:
            raise HTTPException(
                status_code=503,
                detail="Analytics processing is currently disabled. Enable it in configuration."
            )

        # Determine target date
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            target_date = (datetime.now() - timedelta(days=1)).date()

        # Initialize processor with configuration
        log.info("🎯 MANUAL ANALYTICS PROCESSING TRIGGERED")
        log.info(f"📅 Target Date: {target_date}")
        log.info(f"👤 Triggered by: Admin user")
        log.info(f"🔧 Configuration:")
        log.info(f"   - Model: {ANALYTICS_MODEL.value}")
        log.info(f"   - API Key configured: {'Yes' if ANALYTICS_OPENAI_API_KEY.value else 'No'}")
        log.info(f"   - Processing enabled: {ENABLE_ANALYTICS_PROCESSING.value}")

        processor = AnalyticsProcessor(
            openai_api_key=ANALYTICS_OPENAI_API_KEY.value,
            model=ANALYTICS_MODEL.value
        )

        log.info("🚀 Starting analytics processor...")

        # Process conversations for the target date
        result = await processor.process_conversations_for_date(target_date)

        log.info("📊 Processing completed, preparing response...")

        # Return detailed processing results
        return {
            "status": "completed" if result.get('status') != 'failed' else "failed",
            "target_date": target_date.isoformat(),
            "message": f"Analytics processing completed for {target_date}",
            "processing_log_id": result.get('processing_log_id'),
            "conversations_processed": result.get('conversations_processed', 0),
            "conversations_failed": result.get('conversations_failed', 0),
            "duration_seconds": result.get('duration_seconds', 0),
            "total_cost_usd": result.get('total_cost_usd', 0.0),
            "model_used": ANALYTICS_MODEL.value
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        log.error(f"Failed to trigger analytics processing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger processing: {str(e)}"
        )