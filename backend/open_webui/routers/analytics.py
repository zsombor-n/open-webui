import logging
import time
import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from functools import wraps
import io
import csv

from open_webui.utils.auth import get_admin_user
from open_webui.utils.date_ranges import calculate_date_range
from open_webui.cogniforce_models.analytics_tables import (
    Analytics,
    AnalyticsSummary,
    DailyTrendItem,
    UserBreakdownItem,
    ChatItem,
    HealthStatus,
    ProcessingTriggerResponse,
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

class TrendsResponse(BaseModel):
    data: List[DailyTrendItem]

class UserBreakdownResponse(BaseModel):
    users: List[UserBreakdownItem]

class ChatsResponse(BaseModel):
    chats: List[ChatItem]




############################
# Analytics Endpoints
############################

@router.get("/summary", response_model=AnalyticsSummary)
@log_api_request("analytics_summary")
async def get_analytics_summary(
    start_date: str = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date filter (YYYY-MM-DD)"),
    range_type: str = Query(None, description="Date range type: this_week, last_week, this_month, etc."),
    user=Depends(get_admin_user)
):
    """
    Get analytics summary including total chats, time saved,
    average per chat, and confidence level.

    Use either individual start_date/end_date OR range_type parameter.
    If range_type is provided, it takes precedence over individual dates.
    """
    # Parse date parameters if provided
    start_date_obj = None
    end_date_obj = None

    if range_type:
        # Use Pendulum-based date range calculation
        try:
            start_date_obj, end_date_obj = calculate_date_range(range_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid range_type: {str(e)}")
    else:
        # Parse individual dates as before
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    return Analytics.get_summary_data(start_date_obj, end_date_obj)


@router.get("/trends", response_model=TrendsResponse)
@log_api_request("analytics_trends")
async def get_trends(
    start_date: str = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date filter (YYYY-MM-DD)"),
    range_type: str = Query(None, description="Date range type: this_week, last_week, this_month, etc."),
    user=Depends(get_admin_user)
):
    """
    Get analytics trend data for the specified date range.
    If no dates provided, defaults to last 7 days.

    Use either individual start_date/end_date OR range_type parameter.
    If range_type is provided, it takes precedence over individual dates.
    """
    # Parse date parameters if provided
    start_date_obj = None
    end_date_obj = None

    if range_type:
        # Use Pendulum-based date range calculation
        try:
            start_date_obj, end_date_obj = calculate_date_range(range_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid range_type: {str(e)}")
    else:
        # Parse individual dates as before
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    trend_data = Analytics.get_trends_data(start_date_obj, end_date_obj)
    return TrendsResponse(data=trend_data)


@router.get("/user-breakdown", response_model=UserBreakdownResponse)
@log_api_request("analytics_user_breakdown")
async def get_user_breakdown(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of users to return"),
    start_date: str = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date filter (YYYY-MM-DD)"),
    range_type: str = Query(None, description="Date range type: this_week, last_week, this_month, etc."),
    user=Depends(get_admin_user)
):
    """
    Get top users by time saved with their chat counts and average confidence.

    Use either individual start_date/end_date OR range_type parameter.
    If range_type is provided, it takes precedence over individual dates.
    """
    # Parse date parameters if provided
    start_date_obj = None
    end_date_obj = None

    if range_type:
        # Use Pendulum-based date range calculation
        try:
            start_date_obj, end_date_obj = calculate_date_range(range_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid range_type: {str(e)}")
    else:
        # Parse individual dates as before
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    users = Analytics.get_user_breakdown_data(limit, start_date_obj, end_date_obj)
    return UserBreakdownResponse(users=users)


@router.get("/health", response_model=HealthStatus)
@log_api_request("analytics_health")
async def get_analytics_health(user=Depends(get_admin_user)):
    """
    Get analytics system health status and configuration information.
    """
    return Analytics.get_health_status_data()


@router.get("/chats", response_model=ChatsResponse)
@log_api_request("analytics_chats")
async def get_analytics_chats(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of chats to return"),
    offset: int = Query(0, ge=0, description="Number of chats to skip"),
    full_summary: bool = Query(False, description="Include full chat summary text"),
    start_date: str = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date filter (YYYY-MM-DD)"),
    range_type: str = Query(None, description="Date range type: this_week, last_week, this_month, etc."),
    user=Depends(get_admin_user)
):
    """
    Get recent chats with analytics data.
    By default returns structured data (topic, message counts) without full summary.
    Set full_summary=true to include the complete chat summary text.

    Use either individual start_date/end_date OR range_type parameter.
    If range_type is provided, it takes precedence over individual dates.
    """
    # Parse date parameters if provided
    start_date_obj = None
    end_date_obj = None

    if range_type:
        # Use Pendulum-based date range calculation
        try:
            start_date_obj, end_date_obj = calculate_date_range(range_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid range_type: {str(e)}")
    else:
        # Parse individual dates as before
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    chats = Analytics.get_chats_data(limit, offset, full_summary, start_date_obj, end_date_obj)
    return ChatsResponse(chats=chats)


@router.get("/export/{format}")
@log_api_request("analytics_export")
async def export_analytics_data(
    format: str,
    type: str = Query("summary", description="Export type: summary, daily, detailed"),
    start_date: str = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date filter (YYYY-MM-DD)"),
    range_type: str = Query(None, description="Date range type: this_week, last_week, this_month, etc."),
    user=Depends(get_admin_user)
):
    """
    Export analytics data in the specified format.
    Currently supports CSV format.

    Use either individual start_date/end_date OR range_type parameter.
    If range_type is provided, it takes precedence over individual dates.
    """
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is currently supported")

    # Parse date parameters if provided
    start_date_obj = None
    end_date_obj = None

    if range_type:
        # Use Pendulum-based date range calculation
        try:
            start_date_obj, end_date_obj = calculate_date_range(range_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid range_type: {str(e)}")
    else:
        # Parse individual dates as before
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    # Generate CSV data based on type
    output = io.StringIO()
    writer = csv.writer(output)

    if type == "summary":
        summary_data = Analytics.get_summary_data(start_date_obj, end_date_obj)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total chats", summary_data.total_chats])
        writer.writerow(["Total Time Saved (minutes)", summary_data.total_time_saved])
        writer.writerow(["Average Time Saved per chat", summary_data.avg_time_saved_per_chat])
        writer.writerow(["Confidence Level", summary_data.confidence_level])

    elif type == "daily":
        writer.writerow(["Date", "chats", "Time Saved", "Avg Confidence"])
        daily_data = Analytics.get_trends_data(start_date_obj, end_date_obj)  # Use date range for export
        for item in daily_data:
            writer.writerow([item.date, item.chats, item.time_saved, item.avg_confidence])

    elif type == "detailed":
        writer.writerow(["chat ID", "User", "Created At", "Time Saved", "Confidence", "Summary"])
        chats = Analytics.get_chats_data(1000, 0, False, start_date_obj, end_date_obj)  # Large limit for export
        for conv in chats:
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


@router.post("/trigger-processing", response_model=ProcessingTriggerResponse)
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

        # Process chats for the target date
        result = await processor.process_chats_for_date(target_date)

        log.info("📊 Processing completed, preparing response...")

        # Invalidate analytics cache after successful processing
        if result.status != 'failed':
            from open_webui.cogniforce_models.analytics_tables import Analytics

            log.info("🔄 Invalidating analytics cache after successful processing...")

            # Use the decorator's invalidate_cache method for each cached function
            # Note: We need to call with the same parameters that might be cached

            # Invalidate summary data (no parameters)
            Analytics.get_summary_data.invalidate_cache(Analytics)

            # Invalidate trends data cache
            try:
                Analytics.get_trends_data.invalidate_cache(Analytics)
            except:
                pass  # Skip if this specific cache key doesn't exist

            # Invalidate common user breakdown limits
            for limit in [10, 20, 50]:
                try:
                    Analytics.get_user_breakdown_data.invalidate_cache(Analytics, limit)
                except:
                    pass

            # Invalidate common chat data pages
            for limit in [20, 50, 100]:
                for offset in [0, 20, 40]:
                    try:
                        Analytics.get_chats_data.invalidate_cache(Analytics, limit, offset)
                    except:
                        pass

            # Invalidate health status (no parameters)
            Analytics.get_health_status_data.invalidate_cache(Analytics)

            log.info("✅ Cache invalidation completed using decorator methods")

        # Return detailed processing results
        return ProcessingTriggerResponse(
            status="completed" if result.status != 'failed' else "failed",
            target_date=target_date.isoformat(),
            message=f"Analytics processing completed for {target_date}",
            processing_log_id=result.processing_log_id,
            chats_processed=result.chats_processed,
            chats_failed=result.chats_failed,
            duration_seconds=result.duration_seconds,
            total_cost_usd=result.total_cost_usd,
            model_used=ANALYTICS_MODEL.value
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        log.error(f"Failed to trigger analytics processing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger processing: {str(e)}"
        )