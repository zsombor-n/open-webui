"""
Analytics Scheduler Service

This service manages scheduled analytics processing using APScheduler:
1. Daily processing at 00:00 Budapest time
2. Retry logic for failed runs
3. Health monitoring and metrics
4. Graceful shutdown handling
5. Integration with FastAPI lifecycle

The scheduler runs analytics processing automatically and can be controlled
via configuration settings.
"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore

from .analytics_processor import AnalyticsProcessor

log = logging.getLogger(__name__)


class AnalyticsScheduler:
    """
    Manages scheduled analytics processing with APScheduler.

    Handles daily processing runs, retry logic, and health monitoring.
    Integrates with the FastAPI application lifecycle.
    """

    def __init__(self, openai_api_key: str = None, enabled: bool = True):
        """
        Initialize the analytics scheduler.

        Args:
            openai_api_key: OpenAI API key for analytics processor
            enabled: Whether scheduling is enabled
        """
        self.enabled = enabled
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.processor = AnalyticsProcessor(openai_api_key=openai_api_key)

        # Scheduler configuration
        self.job_defaults = {
            'coalesce': True,  # Combine multiple pending runs into one
            'max_instances': 1,  # Only one analytics job at a time
            'misfire_grace_time': 3600  # 1 hour grace period for missed jobs
        }

    async def start(self) -> None:
        """
        Start the analytics scheduler.

        Sets up the APScheduler and adds the daily processing job.
        """
        if not self.enabled:
            log.info("Analytics scheduling disabled")
            return

        try:
            # Configure scheduler
            executors = {
                'default': AsyncIOExecutor()
            }

            job_stores = {
                'default': MemoryJobStore()
            }

            self.scheduler = AsyncIOScheduler(
                executors=executors,
                jobstores=job_stores,
                job_defaults=self.job_defaults,
                timezone='Europe/Budapest'  # Budapest timezone
            )

            # Add daily processing job (00:00 Budapest time)
            self.scheduler.add_job(
                func=self._daily_processing_job,
                trigger=CronTrigger(hour=0, minute=0, second=0),
                id='analytics_daily_processing',
                name='Daily Analytics Processing',
                replace_existing=True
            )

            # Add health check job (every 6 hours)
            self.scheduler.add_job(
                func=self._health_check_job,
                trigger=CronTrigger(hour='*/6'),
                id='analytics_health_check',
                name='Analytics Health Check',
                replace_existing=True
            )

            # Start the scheduler
            self.scheduler.start()
            log.info("Analytics scheduler started successfully")

            # Log next run times
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                log.info(f"Scheduled job '{job.name}' - Next run: {job.next_run_time}")

        except Exception as e:
            log.error(f"Failed to start analytics scheduler: {str(e)}")
            raise

    async def stop(self) -> None:
        """
        Stop the analytics scheduler gracefully.

        Waits for any running jobs to complete before shutting down.
        """
        if self.scheduler and self.scheduler.running:
            log.info("Shutting down analytics scheduler...")

            try:
                # Wait for running jobs to complete
                self.scheduler.shutdown(wait=True)
                log.info("Analytics scheduler stopped successfully")
            except Exception as e:
                log.error(f"Error during scheduler shutdown: {str(e)}")
                # Force shutdown if graceful shutdown fails
                self.scheduler.shutdown(wait=False)

    async def trigger_manual_processing(self, target_date: Optional[date] = None) -> dict:
        """
        Trigger manual analytics processing for a specific date.

        Args:
            target_date: Date to process (defaults to yesterday)

        Returns:
            Processing results
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()

        try:
            log.info(f"Manual processing triggered for date: {target_date}")
            result = await self.processor.process_conversations_for_date(target_date)
            log.info(f"Manual processing completed for date: {target_date}")
            return result

        except Exception as e:
            log.error(f"Manual processing failed for date {target_date}: {str(e)}")
            raise

    async def _daily_processing_job(self) -> None:
        """
        Daily scheduled processing job.

        Processes conversations from the previous day.
        """
        try:
            # Process previous day's conversations
            yesterday = (datetime.now() - timedelta(days=1)).date()

            log.info(f"Starting scheduled analytics processing for {yesterday}")

            result = await self.processor.process_conversations_for_date(yesterday)

            processed = result.get('conversations_processed', 0)
            failed = result.get('conversations_failed', 0)
            cost = result.get('total_cost_usd', 0.0)

            log.info(f"Scheduled processing completed for {yesterday}. "
                    f"Processed: {processed}, Failed: {failed}, Cost: ${cost:.4f}")

        except Exception as e:
            log.error(f"Scheduled analytics processing failed: {str(e)}")
            # Don't re-raise - let APScheduler handle the failure

    async def _health_check_job(self) -> None:
        """
        Periodic health check job.

        Monitors system health and logs status information.
        """
        try:
            log.info("Running analytics system health check...")

            # Check recent processing runs
            from open_webui.internal.cogniforce_db import get_cogniforce_db
            from sqlalchemy import text

            with get_cogniforce_db() as db:
                # Get last processing run
                result = db.execute(text("""
                    SELECT
                        run_date,
                        status,
                        conversations_processed,
                        conversations_failed,
                        completed_at
                    FROM processing_log
                    ORDER BY started_at DESC
                    LIMIT 1
                """))

                last_run = result.fetchone()

                if last_run:
                    status = last_run[1]
                    processed = last_run[2] or 0
                    failed = last_run[3] or 0

                    if status == 'completed' and failed == 0:
                        health_status = "healthy"
                    elif status == 'completed' and failed > 0:
                        health_status = "warning"
                    else:
                        health_status = "unhealthy"

                    log.info(f"Analytics health check: {health_status}. "
                            f"Last run: {last_run[0]}, Processed: {processed}, Failed: {failed}")
                else:
                    log.warning("Analytics health check: No processing runs found")

        except Exception as e:
            log.error(f"Health check failed: {str(e)}")

    def get_scheduler_status(self) -> dict:
        """
        Get current scheduler status and job information.

        Returns:
            Dictionary with scheduler status and job details
        """
        if not self.scheduler:
            return {
                'enabled': self.enabled,
                'running': False,
                'jobs': []
            }

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })

        return {
            'enabled': self.enabled,
            'running': self.scheduler.running,
            'timezone': str(self.scheduler.timezone),
            'jobs': jobs
        }

    async def add_one_time_job(self, target_date: date, delay_seconds: int = 0) -> str:
        """
        Add a one-time processing job for a specific date.

        Args:
            target_date: Date to process
            delay_seconds: Delay before execution (default: immediate)

        Returns:
            Job ID
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not started")

        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job_id = f"analytics_onetime_{target_date}_{int(run_time.timestamp())}"

        self.scheduler.add_job(
            func=self._one_time_processing_job,
            trigger='date',
            run_date=run_time,
            args=[target_date],
            id=job_id,
            name=f'One-time Analytics Processing for {target_date}',
            replace_existing=True
        )

        log.info(f"Added one-time processing job for {target_date}, scheduled for {run_time}")
        return job_id

    async def _one_time_processing_job(self, target_date: date) -> None:
        """
        One-time processing job for a specific date.

        Args:
            target_date: Date to process
        """
        try:
            log.info(f"Starting one-time processing for {target_date}")
            result = await self.processor.process_conversations_for_date(target_date)

            processed = result.get('conversations_processed', 0)
            failed = result.get('conversations_failed', 0)

            log.info(f"One-time processing completed for {target_date}. "
                    f"Processed: {processed}, Failed: {failed}")

        except Exception as e:
            log.error(f"One-time processing failed for {target_date}: {str(e)}")

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: ID of the job to remove

        Returns:
            True if job was removed, False if not found
        """
        if not self.scheduler:
            return False

        try:
            self.scheduler.remove_job(job_id)
            log.info(f"Removed job: {job_id}")
            return True
        except Exception:
            log.warning(f"Job not found: {job_id}")
            return False