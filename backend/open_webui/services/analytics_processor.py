"""
Analytics Processor Service

This service handles the core analytics processing pipeline:
1. Fetches chats from OpenWebUI database
2. Creates intelligent summaries with privacy-preserving redaction
3. Calls GPT-5-mini API for time estimation analysis
4. Calculates time savings metrics
5. Stores results in Cogniforce analytics database
6. Tracks processing statistics and costs

The processor is designed to handle both manual triggers and scheduled runs.
"""

import json
import time
import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import re

import openai
import aiohttp
from open_webui.internal.db import get_db
from open_webui.internal.cogniforce_db import get_cogniforce_db
from open_webui.cogniforce_models.analytics_tables import (
    ChatAnalysis, DailyAggregate, ProcessingLog,
    ChatAnalysisResult, TimeMetrics, TimeEstimates, ProcessingLogResult
)
from open_webui.models.chats import Chat
from open_webui.models.users import User

log = logging.getLogger(__name__)


class AnalyticsProcessor:
    """
    Core analytics processing engine for chat analysis and time estimation.

    This processor integrates with GPT-5-mini to provide accurate manual time estimates
    for chats, calculating how much time users saved by using AI assistance.
    """

    def __init__(self, openai_api_key: str = None, model: str = "gpt-5-mini"):
        """
        Initialize the analytics processor.

        Args:
            openai_api_key: OpenAI API key for GPT-5-mini calls
            model: The GPT model to use for time estimation
        """
        self.model = model
        self.temperature = 0.3  # Low temperature for consistent estimates
        self.max_tokens = 4096   # Generous tokens for GPT-5-mini reasoning + output
        self.idle_threshold_minutes = 10  # Gap threshold for active time calculation
        self.openai_api_key = openai_api_key  # Store for logging

        # Initialize OpenAI client
        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        else:
            # Will use environment variables
            self.openai_client = openai.OpenAI()

    async def process_chats_for_date(self, target_date: date) -> Dict[str, Any]:
        """
        Main entry point for processing chats for a specific date.

        Args:
            target_date: Date to process chats for

        Returns:
            Processing results with statistics and metrics
        """
        processing_start = datetime.now()

        # Create processing log entry
        processing_log_id = await self._create_processing_log(target_date, processing_start)

        try:
            log.info("=" * 60)
            log.info("🚀 ANALYTICS PROCESSING STARTED")
            log.info("=" * 60)
            log.info(f"[CONFIG] Target Date: {target_date}")
            log.info(f"[CONFIG] Model: {self.model}")
            log.info(f"[CONFIG] Temperature: {self.temperature}")
            log.info(f"[CONFIG] Max Tokens: {self.max_tokens}")
            log.info(f"[CONFIG] Idle Threshold: {self.idle_threshold_minutes} minutes")

            # Fetch chats for the target date
            log.info("\n[STEP 1] 📥 FETCHING chatS...")
            chats = await self._fetch_chats_for_date(target_date)
            log.info(f"[STEP 1] ✅ Found {len(chats)} chats to process")

            if chats:
                log.info("[STEP 1] 📋 chat Summary:")
                for i, conv in enumerate(chats, 1):
                    log.info(f"[STEP 1]   {i}. ID: {conv['id'][:8]}... | Title: {conv['title'][:50]}...")
            else:
                log.warning("[STEP 1] ⚠️  No chats found for processing")

            if not chats:
                return await self._complete_processing_log(
                    processing_log_id, processing_start,
                    chats_processed=0, status="completed"
                )

            # Process each chat
            log.info(f"\n[STEP 2] ⚙️  PROCESSING {len(chats)} chatS...")
            results = []
            processed_count = 0
            failed_count = 0
            total_cost = 0.0
            total_llm_requests = 0

            for i, chat_data in enumerate(chats, 1):
                try:
                    log.info(f"\n[STEP 2.{i}] 🔄 Processing chat {i}/{len(chats)}")
                    log.info(f"[STEP 2.{i}] 📝 ID: {chat_data['id']}")
                    log.info(f"[STEP 2.{i}] 👤 User: {chat_data.get('user_name', 'Unknown')} ({chat_data.get('user_email', 'N/A')})")
                    log.info(f"[STEP 2.{i}] 📋 Title: {chat_data.get('title', 'Untitled')}")

                    result = await self._analyze_chat(chat_data)
                    if result:
                        results.append(result)
                        processed_count += 1
                        total_cost += result.llm_cost
                        total_llm_requests += 1

                        log.info(f"[STEP 2.{i}] ✅ Successfully processed!")
                        log.info(f"[STEP 2.{i}] 💰 Cost: ${result.llm_cost:.4f}")
                        log.info(f"[STEP 2.{i}] ⏱️  Time Saved: {result.time_saved_minutes} minutes")
                        log.info(f"[STEP 2.{i}] 🎯 Confidence: {result.confidence_level}%")
                    else:
                        failed_count += 1
                        log.warning(f"[STEP 2.{i}] ❌ Failed to process chat {chat_data['id']}")

                except Exception as e:
                    failed_count += 1
                    log.error(f"[STEP 2.{i}] 💥 Error processing chat {chat_data['id']}: {str(e)}")
                    continue

            # Update daily aggregates
            log.info(f"\n[STEP 3] 📊 UPDATING DAILY AGGREGATES...")
            await self._update_daily_aggregates(target_date, results)
            log.info(f"[STEP 3] ✅ Daily aggregates updated for {target_date}")

            # Complete processing log
            log.info(f"\n[STEP 4] 📝 COMPLETING PROCESSING LOG...")
            processing_result = await self._complete_processing_log(
                processing_log_id, processing_start,
                chats_processed=processed_count,
                chats_failed=failed_count,
                total_llm_requests=total_llm_requests,
                total_llm_cost_usd=total_cost,
                status="completed"
            )

            # Final summary
            total_time_saved = sum(r.time_saved_minutes for r in results if r is not None)
            duration_seconds = processing_result.duration_seconds

            log.info("=" * 60)
            log.info("🎉 ANALYTICS PROCESSING COMPLETED SUCCESSFULLY!")
            log.info("=" * 60)
            log.info(f"[SUMMARY] 📈 chats Processed: {processed_count}")
            log.info(f"[SUMMARY] ❌ chats Failed: {failed_count}")
            log.info(f"[SUMMARY] 🤖 OpenAI API Calls: {total_llm_requests}")
            log.info(f"[SUMMARY] 💰 Total Cost: ${total_cost:.4f}")
            log.info(f"[SUMMARY] ⏱️  Total Time Saved: {total_time_saved} minutes")
            log.info(f"[SUMMARY] ⏲️  Processing Duration: {duration_seconds} seconds")
            log.info(f"[SUMMARY] 📊 Processing Log ID: {processing_log_id}")
            log.info("=" * 60)

            # Invalidate analytics cache after successful processing
            log.info("🔄 Invalidating analytics cache after successful processing...")
            try:
                from open_webui.cogniforce_models.analytics_tables import Analytics

                # Use the decorator's invalidate_cache method for each cached function
                # Invalidate summary data (no parameters)
                Analytics.get_summary_data.invalidate_cache(Analytics)

                # Invalidate common daily trend periods
                for days in [7, 30, 90]:
                    try:
                        Analytics.get_daily_trend_data.invalidate_cache(Analytics, days)
                    except:
                        pass

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
            except Exception as cache_error:
                log.warning(f"Cache invalidation failed: {cache_error}")

            return processing_result

        except Exception as e:
            # Mark processing as failed
            await self._complete_processing_log(
                processing_log_id, processing_start,
                status="failed", error_message=str(e)
            )
            log.error(f"Analytics processing failed: {str(e)}")
            raise

    async def _fetch_chats_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Fetch chats from OpenWebUI database for the target date.

        For development: fetches ALL chats since we only have 2 test chats.
        In production: would filter by date.

        Args:
            target_date: Date to fetch chats for

        Returns:
            List of chat data dictionaries
        """
        try:
            with get_db() as db:
                # Use SQLAlchemy ORM to join chats with users
                query_results = db.query(Chat, User).join(
                    User, Chat.user_id == User.id
                ).order_by(Chat.created_at.desc()).all()

                chats = []
                for chat, user in query_results:
                    chats.append({
                        'id': chat.id,
                        'user_id': chat.user_id,
                        'title': chat.title,
                        'chat': chat.chat,
                        'created_at': chat.created_at,
                        'updated_at': chat.updated_at,
                        'user_email': user.email,
                        'user_name': user.name
                    })

                return chats

        except Exception as e:
            log.error(f"Failed to fetch chats: {str(e)}")
            raise

    async def _analyze_chat(self, conv_data: Dict[str, Any]) -> Optional[ChatAnalysisResult]:
        """
        Analyze a single chat using GPT-5-mini.

        Args:
            conv_data: chat data from database

        Returns:
            Analysis results or None if failed
        """
        try:
            # Extract chat details
            chat_id = conv_data['id']
            chat_data = conv_data['chat']

            log.info(f"    📊 EXTRACTING chat DATA...")
            log.info(f"    📝 chat ID: {chat_id}")

            if not chat_data or 'messages' not in chat_data:
                log.warning(f"    ⚠️  No messages found in chat {chat_id}")
                return None

            messages = chat_data['messages']
            if not messages:
                log.warning(f"    ⚠️  Empty messages list for chat {chat_id}")
                return None

            log.info(f"    💬 Messages found: {len(messages)}")

            # Calculate time metrics
            log.info(f"    ⏱️  CALCULATING TIME METRICS...")
            time_metrics = self._calculate_time_metrics(messages, conv_data)
            log.info(f"    ⏱️  First message: {time_metrics.first_message_at}")
            log.info(f"    ⏱️  Last message: {time_metrics.last_message_at}")
            log.info(f"    ⏱️  Total duration: {time_metrics.total_duration_minutes} minutes")
            log.info(f"    ⏱️  Active duration: {time_metrics.active_duration_minutes} minutes")
            log.info(f"    ⏱️  Idle time: {time_metrics.idle_time_minutes} minutes")

            # Create smart summary for LLM analysis
            log.info(f"    📝 CREATING SMART SUMMARY...")
            chat_summary = self._create_smart_summary(conv_data, messages)
            log.info(f"    📝 Summary length: {len(chat_summary)} characters")

            # Get time estimation from GPT-5-mini
            log.info(f"    🤖 CALLING GPT-5-MINI API...")
            log.info(f"    🤖 Model: {self.model}")
            log.info(f"    🤖 Temperature: default (1) - GPT-5-mini requirement")
            log.info(f"    🤖 Max Completion Tokens: {self.max_tokens}")

            llm_response = await self._estimate_manual_time(chat_summary)

            if not llm_response:
                log.error(f"    ❌ Failed to get LLM response for chat {chat_id}")
                return None

            log.info(f"    🤖 ✅ GPT-5-mini response received!")

            # Parse LLM response
            log.info(f"    🔍 PARSING TIME ESTIMATES...")
            time_estimates = self._parse_time_estimates(llm_response)
            log.info(f"    🔍 Low estimate: {time_estimates.low} minutes")
            log.info(f"    🔍 Most likely: {time_estimates.most_likely} minutes")
            log.info(f"    🔍 High estimate: {time_estimates.high} minutes")
            log.info(f"    🔍 Confidence: {time_estimates.confidence}%")

            # Calculate time saved
            log.info(f"    📈 CALCULATING TIME SAVINGS...")
            manual_time_most_likely = time_estimates.most_likely
            active_duration = time_metrics.active_duration_minutes
            time_saved = max(0, manual_time_most_likely - active_duration)
            log.info(f"    📈 Manual estimate: {manual_time_most_likely} minutes")
            log.info(f"    📈 AI-assisted time: {active_duration} minutes")
            log.info(f"    📈 Time saved: {time_saved} minutes")

            # Store analysis results
            log.info(f"    💾 STORING ANALYSIS RESULTS...")
            # Calculate chat date from creation timestamp
            chat_date = datetime.fromtimestamp(conv_data['created_at']).date()

            analysis_id = await self._store_analysis_results(
                chat_id=chat_id,
                user_id=conv_data['user_id'],
                chat_date=chat_date,
                time_metrics=time_metrics,
                time_estimates=time_estimates,
                time_saved_minutes=time_saved,
                chat_summary=chat_summary,
                llm_response=llm_response,
                message_count=len(messages)
            )
            log.info(f"    💾 ✅ Analysis stored with ID: {analysis_id}")

            return ChatAnalysisResult(
                analysis_id=analysis_id,
                chat_id=chat_id,
                chat_date=chat_date,
                user_id=str(conv_data['user_id']),
                time_saved_minutes=time_saved,
                active_duration_minutes=time_metrics.active_duration_minutes,
                manual_time_most_likely=time_estimates.most_likely,
                message_count=len(messages),
                confidence_level=time_estimates.confidence,
                llm_cost=0.001  # Estimated cost per request for GPT-5-mini
            )

        except Exception as e:
            log.error(f"Error analyzing chat {conv_data.get('id', 'unknown')}: {str(e)}")
            return None

    def _calculate_time_metrics(self, messages: List[Dict], conv_data: Dict) -> TimeMetrics:
        """
        Calculate timing metrics for the chat.

        Args:
            messages: List of chat messages
            conv_data: chat metadata

        Returns:
            Dictionary with timing metrics
        """
        if not messages:
            now = datetime.now()
            return TimeMetrics(
                first_message_at=now,
                last_message_at=now,
                total_duration_minutes=0,
                active_duration_minutes=0,
                idle_time_minutes=0
            )

        # Extract timestamps
        timestamps = []
        for msg in messages:
            if 'timestamp' in msg:
                timestamps.append(datetime.fromtimestamp(msg['timestamp']))

        if not timestamps:
            # Fallback to created/updated timestamps
            first_message_at = datetime.fromtimestamp(conv_data['created_at'])
            last_message_at = datetime.fromtimestamp(conv_data['updated_at'])
        else:
            first_message_at = min(timestamps)
            last_message_at = max(timestamps)

        # Calculate total duration
        total_duration = last_message_at - first_message_at
        total_duration_minutes = int(total_duration.total_seconds() / 60)

        # Calculate active duration (excluding idle gaps > threshold)
        active_duration_minutes = self._calculate_active_duration(timestamps)

        # Calculate idle time
        idle_time_minutes = max(0, total_duration_minutes - active_duration_minutes)

        return TimeMetrics(
            first_message_at=first_message_at,
            last_message_at=last_message_at,
            total_duration_minutes=total_duration_minutes,
            active_duration_minutes=active_duration_minutes,
            idle_time_minutes=idle_time_minutes
        )

    def _calculate_active_duration(self, timestamps: List[datetime]) -> int:
        """
        Calculate active duration excluding idle gaps longer than threshold.

        Args:
            timestamps: List of message timestamps

        Returns:
            Active duration in minutes
        """
        if len(timestamps) < 2:
            return 0

        active_minutes = 0
        sorted_timestamps = sorted(timestamps)

        for i in range(1, len(sorted_timestamps)):
            gap = sorted_timestamps[i] - sorted_timestamps[i-1]
            gap_minutes = gap.total_seconds() / 60

            # If gap is within threshold, count it as active time
            if gap_minutes <= self.idle_threshold_minutes:
                active_minutes += gap_minutes
            # Otherwise, don't count the gap (idle time)

        return int(active_minutes)

    def _create_smart_summary(self, conv_data: Dict, messages: List[Dict]) -> str:
        """
        Create an intelligent summary with smart redaction.

        Preserves public/historical information while redacting private data.

        Args:
            conv_data: chat metadata
            messages: List of messages

        Returns:
            Redacted chat summary
        """
        # Extract chat content
        title = conv_data.get('title', 'Untitled chat')
        user_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'user']
        assistant_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'assistant']

        # Combine all content for analysis
        full_content = f"Title: {title}\n"
        full_content += "User Messages:\n" + "\n".join(user_messages[:3])  # First 3 user messages
        full_content += "\nAssistant Messages:\n" + "\n".join(assistant_messages[:2])  # First 2 assistant messages

        # Smart redaction - preserve public information
        redacted_summary = self._apply_smart_redaction(full_content)

        # Add metadata for context
        summary = f"""chat Analysis Summary:

Topic: {title}
Message Count: {len(messages)}
User Messages: {len(user_messages)}
Assistant Messages: {len(assistant_messages)}

Content Overview:
{redacted_summary}

This chat required the user to engage in back-and-forth dialogue with an AI assistant to complete their task."""

        return summary

    def _apply_smart_redaction(self, content: str) -> str:
        """
        Apply intelligent redaction that preserves public information.

        Args:
            content: Original content to redact

        Returns:
            Redacted content with public info preserved
        """
        # Don't redact common historical/public terms
        public_terms = [
            'Nixon', 'Supreme Court', 'United States', 'Constitution',
            'President', 'Congress', 'Senate', 'House', 'Watergate',
            'Executive', 'Legislative', 'Judicial', 'Amendment',
            'case law', 'precedent', 'opinion', 'dissent', 'majority',
            'Chief Justice', 'Associate Justice', 'judicial review'
        ]

        # Redact potential private information patterns
        redacted = content

        # Email patterns
        redacted = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', redacted)

        # Phone numbers
        redacted = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE_REDACTED]', redacted)

        # URLs (except well-known public ones)
        redacted = re.sub(r'https?://(?!(?:www\.)?(wikipedia\.org|supreme\.justia\.com|law\.cornell\.edu))[^\s]+', '[URL_REDACTED]', redacted)

        # API keys or tokens
        redacted = re.sub(r'[a-zA-Z0-9]{32,}', '[KEY_REDACTED]', redacted)

        # Remove excessive whitespace
        redacted = re.sub(r'\n\s*\n', '\n', redacted)

        return redacted.strip()

    async def _estimate_manual_time(self, chat_summary: str) -> Optional[Dict[str, Any]]:
        """
        Use GPT-5-mini to estimate manual completion time.

        Args:
            chat_summary: Redacted chat summary

        Returns:
            LLM response with time estimates or None if failed
        """
        system_prompt = """You are an expert at estimating how long tasks would take to complete manually without AI assistance.

Analyze the provided chat summary and estimate how long it would have taken the user to complete the same task manually through research, writing, coding, or other methods.

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format (no other text):
{
    "manual_time_low": <lowest estimate in minutes>,
    "manual_time_most_likely": <most likely estimate in minutes>,
    "manual_time_high": <highest estimate in minutes>,
    "confidence_level": <confidence 0-100>,
    "reasoning": "<brief explanation of your estimates>"
}

Consider factors like:
- Research time needed
- Complexity of the topic
- Writing/coding time required
- Learning curve for unfamiliar concepts
- Quality and depth of work expected"""

        try:
            log.info(f"        🔄 Making API call to {self.model}...")
            log.info(f"        📝 System prompt length: {len(system_prompt)} characters")
            log.info(f"        📝 User content length: {len(chat_summary)} characters")
            log.info(f"        🔑 API key configured: {'Yes' if self.openai_api_key else 'Using env var'}")

            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},  # GPT-5-mini uses standard "system" role
                    {"role": "user", "content": chat_summary}
                ],
                # temperature removed - GPT-5-mini only supports default value (1)
                max_completion_tokens=self.max_tokens  # Updated parameter for GPT-5-mini
                # response_format removed - not supported by GPT-5-mini
            )

            # Debug: Log the full response object structure
            log.info(f"        📤 Full response object: {type(response)}")
            log.info(f"        📤 Response ID: {getattr(response, 'id', 'None')}")
            log.info(f"        📤 Model used: {getattr(response, 'model', 'None')}")
            log.info(f"        📤 Usage: {getattr(response, 'usage', 'None')}")

            # Check if response has choices
            if not hasattr(response, 'choices') or not response.choices:
                log.error(f"        ❌ No choices in response: {response}")
                return None

            log.info(f"        📤 Number of choices: {len(response.choices)}")

            choice = response.choices[0]
            log.info(f"        📤 Choice finish reason: {getattr(choice, 'finish_reason', 'None')}")

            message = getattr(choice, 'message', None)
            if not message:
                log.error(f"        ❌ No message in choice: {choice}")
                return None

            response_text = getattr(message, 'content', '') or ""
            log.info(f"        📤 Raw API response length: {len(response_text)} characters")

            if not response_text:
                log.error(f"        ❌ Empty response content from API")
                log.error(f"        📤 Full message object: {message}")
                return None

            # Try to extract JSON from the response (might have extra text)
            import re

            # First, try to find JSON block
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                log.info(f"        🔍 Extracted JSON block: {len(json_text)} characters")
            else:
                # Fallback: use the entire response
                json_text = response_text.strip()
                log.info(f"        🔍 Using entire response as JSON")

            llm_response = json.loads(json_text)

            log.info(f"        ✅ API call successful!")
            log.info(f"        📊 Time estimation result: {llm_response.get('manual_time_most_likely', 0)} minutes")
            log.info(f"        🎯 Confidence level: {llm_response.get('confidence_level', 0)}%")
            if 'reasoning' in llm_response:
                log.info(f"        💭 AI reasoning: {llm_response['reasoning'][:100]}...")

            return llm_response

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse LLM response as JSON: {str(e)}")
            log.error(f"Raw response that failed to parse: {response_text[:500]}...")
            return None
        except openai.AuthenticationError as e:
            log.error(f"        ❌ OpenAI Authentication Error: {str(e)}")
            log.error(f"        🔑 Check API key configuration")
            return None
        except openai.PermissionDeniedError as e:
            log.error(f"        ❌ OpenAI Permission Denied: {str(e)}")
            log.error(f"        📋 Model {self.model} may not be available to your account")
            return None
        except openai.NotFoundError as e:
            log.error(f"        ❌ OpenAI Not Found Error: {str(e)}")
            log.error(f"        📋 Model {self.model} may not exist")
            return None
        except openai.RateLimitError as e:
            log.error(f"        ❌ OpenAI Rate Limit Error: {str(e)}")
            return None
        except openai.APIError as e:
            log.error(f"        ❌ OpenAI API Error: {e.status_code} - {str(e)}")
            return None
        except Exception as e:
            log.error(f"        ❌ Unexpected error calling GPT-5-mini API: {type(e).__name__}: {str(e)}")
            # Log the full exception details
            import traceback
            log.error(f"        📋 Full traceback: {traceback.format_exc()}")
            return None

    async def _estimate_manual_time_http(self, chat_summary: str) -> Optional[Dict[str, Any]]:
        """
        Estimate manual completion time using direct HTTP calls to GPT-5-mini API.
        This bypasses the OpenAI Python library parsing issue with GPT-5-mini responses.

        Args:
            chat_summary: Redacted chat summary

        Returns:
            LLM response with time estimates or None if failed
        """
        system_prompt = """You are an expert at estimating how long tasks would take to complete manually without AI assistance.

Analyze the provided chat summary and estimate how long it would have taken the user to complete the same task manually through research, writing, coding, or other methods.

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format (no other text):
{
    "manual_time_low": <lowest estimate in minutes>,
    "manual_time_most_likely": <most likely estimate in minutes>,
    "manual_time_high": <highest estimate in minutes>,
    "confidence_level": <confidence 0-100>,
    "reasoning": "<brief explanation of your estimates>"
}

Consider factors like:
- Research time needed
- Complexity of the topic
- Writing/coding time required
- Learning curve for unfamiliar concepts
- Quality and depth of work expected"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat_summary}
            ],
            "max_completion_tokens": self.max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

        try:
            log.info(f"        🔄 Making direct HTTP call to {self.model}...")
            log.info(f"        📝 System prompt length: {len(system_prompt)} characters")
            log.info(f"        📝 User content length: {len(chat_summary)} characters")
            log.info(f"        🔑 API key configured: {'Yes' if self.openai_api_key else 'No'}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:

                    response_text = await response.text()
                    log.info(f"        📤 HTTP status: {response.status}")
                    log.info(f"        📤 Response length: {len(response_text)} characters")

                    if response.status != 200:
                        log.error(f"        ❌ HTTP error {response.status}: {response_text[:500]}...")
                        return None

                    try:
                        response_data = json.loads(response_text)
                        log.info(f"        📤 Response ID: {response_data.get('id', 'None')}")
                        log.info(f"        📤 Model used: {response_data.get('model', 'None')}")
                        log.info(f"        📤 Usage: {response_data.get('usage', 'None')}")

                        # Extract content from response
                        choices = response_data.get('choices', [])
                        if not choices:
                            log.error(f"        ❌ No choices in response: {response_data}")
                            return None

                        choice = choices[0]
                        finish_reason = choice.get('finish_reason', 'None')
                        log.info(f"        📤 Finish reason: {finish_reason}")

                        message = choice.get('message', {})
                        content = message.get('content', '')

                        log.info(f"        📤 Raw content length: {len(content)} characters")
                        log.info(f"        📤 Raw content preview: {content[:100]}...")

                        if not content:
                            log.error(f"        ❌ Empty content from API")
                            log.error(f"        📤 Full message: {message}")
                            return None

                        # Try to extract JSON from the response
                        import re

                        # First, try to find JSON block
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_text = json_match.group()
                            log.info(f"        🔍 Extracted JSON block: {len(json_text)} characters")
                        else:
                            # Fallback: use the entire response
                            json_text = content.strip()
                            log.info(f"        🔍 Using entire response as JSON")

                        llm_response = json.loads(json_text)

                        log.info(f"        ✅ HTTP API call successful!")
                        log.info(f"        📊 Time estimation result: {llm_response.get('manual_time_most_likely', 0)} minutes")
                        log.info(f"        🎯 Confidence level: {llm_response.get('confidence_level', 0)}%")
                        if 'reasoning' in llm_response:
                            log.info(f"        💭 AI reasoning: {llm_response['reasoning'][:100]}...")

                        return llm_response

                    except json.JSONDecodeError as e:
                        log.error(f"        ❌ Failed to parse API response as JSON: {str(e)}")
                        log.error(f"        📤 Raw response that failed: {response_text[:500]}...")
                        return None

        except aiohttp.ClientTimeout:
            log.error(f"        ❌ HTTP request timeout after 120 seconds")
            return None
        except aiohttp.ClientError as e:
            log.error(f"        ❌ HTTP client error: {str(e)}")
            return None
        except Exception as e:
            log.error(f"        ❌ Unexpected error in HTTP API call: {type(e).__name__}: {str(e)}")
            import traceback
            log.error(f"        📋 Full traceback: {traceback.format_exc()}")
            return None

    def _parse_time_estimates(self, llm_response: Dict[str, Any]) -> TimeEstimates:
        """
        Parse and validate time estimates from LLM response.

        Args:
            llm_response: Raw LLM response

        Returns:
            Validated time estimates
        """
        try:
            return TimeEstimates(
                low=max(0, int(llm_response.get('manual_time_low', 0))),
                most_likely=max(0, int(llm_response.get('manual_time_most_likely', 0))),
                high=max(0, int(llm_response.get('manual_time_high', 0))),
                confidence=max(0, min(100, int(llm_response.get('confidence_level', 0))))
            )
        except (ValueError, TypeError):
            log.warning("Failed to parse time estimates, using defaults")
            return TimeEstimates(
                low=0,
                most_likely=0,
                high=0,
                confidence=0
            )

    async def _store_analysis_results(self, **kwargs) -> str:
        """
        Store chat analysis results in the database.

        Returns:
            Analysis record ID
        """
        try:
            with get_cogniforce_db() as db:
                # Create analysis record
                analysis = ChatAnalysis(
                    chat_id=kwargs['chat_id'],
                    user_id=kwargs['user_id'],
                    chat_date=kwargs['chat_date'],
                    first_message_at=kwargs['time_metrics'].first_message_at,
                    last_message_at=kwargs['time_metrics'].last_message_at,
                    total_duration_minutes=kwargs['time_metrics'].total_duration_minutes,
                    active_duration_minutes=kwargs['time_metrics'].active_duration_minutes,
                    idle_time_minutes=kwargs['time_metrics'].idle_time_minutes,
                    manual_time_low=kwargs['time_estimates'].low,
                    manual_time_most_likely=kwargs['time_estimates'].most_likely,
                    manual_time_high=kwargs['time_estimates'].high,
                    confidence_level=kwargs['time_estimates'].confidence,
                    time_saved_minutes=kwargs['time_saved_minutes'],
                    message_count=kwargs['message_count'],
                    chat_summary=kwargs['chat_summary'],
                    llm_response=kwargs['llm_response']
                )

                db.add(analysis)
                db.commit()

                log.info(f"Stored analysis results for chat {kwargs['chat_id']}")
                return str(analysis.id)

        except Exception as e:
            log.error(f"Failed to store analysis results: {str(e)}")
            raise

    async def _create_processing_log(self, target_date: date, started_at: datetime) -> str:
        """Create processing log entry and return its ID."""
        try:
            with get_cogniforce_db() as db:
                log_entry = ProcessingLog(
                    target_date=target_date,
                    started_at=started_at,
                    status='running'
                )
                db.add(log_entry)
                db.commit()
                return str(log_entry.id)
        except Exception as e:
            log.error(f"Failed to create processing log: {str(e)}")
            raise

    async def _complete_processing_log(self, log_id: str, started_at: datetime, **kwargs) -> ProcessingLogResult:
        """Complete processing log with final statistics."""
        try:
            with get_cogniforce_db() as db:
                completed_at = datetime.now()
                duration_seconds = int((completed_at - started_at).total_seconds())

                # Update processing log using SQLAlchemy ORM
                processing_log = db.query(ProcessingLog).filter_by(id=log_id).first()
                if processing_log:
                    processing_log.completed_at = completed_at
                    processing_log.status = kwargs.get('status', 'completed')
                    processing_log.chats_processed = kwargs.get('chats_processed', 0)
                    processing_log.chats_failed = kwargs.get('chats_failed', 0)
                    processing_log.total_llm_requests = kwargs.get('total_llm_requests', 0)
                    processing_log.total_llm_cost_usd = kwargs.get('total_llm_cost_usd', 0.0)
                    processing_log.processing_duration_seconds = duration_seconds
                    processing_log.error_message = kwargs.get('error_message')
                db.commit()

                return ProcessingLogResult(
                    processing_log_id=log_id,
                    status=kwargs.get('status', 'completed'),
                    duration_seconds=duration_seconds,
                    chats_processed=kwargs.get('chats_processed', 0),
                    chats_failed=kwargs.get('chats_failed', 0),
                    total_cost_usd=kwargs.get('total_llm_cost_usd', 0.0)
                )

        except Exception as e:
            log.error(f"Failed to complete processing log: {str(e)}")
            raise

    async def _update_daily_aggregates(self, target_date: date, results: List[ChatAnalysisResult]) -> None:
        """Update daily aggregates with processing results grouped by chat_date."""
        if not results:
            return

        try:
            with get_cogniforce_db() as db:
                # Group results by their actual chat date (not processing date)
                valid_results = [r for r in results if r is not None]
                results_by_date = {}

                for result in valid_results:
                    chat_date = result.chat_date
                    if chat_date not in results_by_date:
                        results_by_date[chat_date] = []
                    results_by_date[chat_date].append(result)

                # Update aggregates for each chat date
                for chat_date, date_results in results_by_date.items():
                    total_chats = len(date_results)
                    total_time_saved = sum(r.time_saved_minutes for r in date_results)
                    total_messages = sum(r.message_count for r in date_results)
                    total_active_time = sum(r.active_duration_minutes for r in date_results)
                    total_manual_time_estimated = sum(r.manual_time_most_likely for r in date_results)
                    avg_confidence = sum(r.confidence_level for r in date_results) / len(date_results)

                    # Insert or update global aggregate using SQLAlchemy ORM
                    existing_aggregate = db.query(DailyAggregate).filter_by(
                        analysis_date=chat_date,  # Use actual chat date, not processing date
                        user_id=None
                    ).first()

                    if existing_aggregate:
                        # Update existing record
                        existing_aggregate.chat_count += total_chats
                        existing_aggregate.message_count += total_messages
                        existing_aggregate.total_time_saved += total_time_saved
                        existing_aggregate.total_active_time += total_active_time
                        existing_aggregate.total_manual_time_estimated += total_manual_time_estimated
                        # Update average confidence (weighted average)
                        existing_weight = existing_aggregate.chat_count - total_chats
                        if existing_weight > 0:
                            existing_aggregate.avg_confidence_level = (
                                (existing_aggregate.avg_confidence_level * existing_weight + avg_confidence * total_chats)
                                / existing_aggregate.chat_count
                            )
                        else:
                            existing_aggregate.avg_confidence_level = avg_confidence
                        existing_aggregate.updated_at = datetime.now()
                    else:
                        # Create new record
                        new_aggregate = DailyAggregate(
                            id=uuid.uuid4(),
                            analysis_date=chat_date,  # Use actual chat date, not processing date
                            user_id=None,
                            chat_count=total_chats,
                            message_count=total_messages,
                            total_time_saved=total_time_saved,
                            total_active_time=total_active_time,
                            total_manual_time_estimated=total_manual_time_estimated,
                            avg_confidence_level=avg_confidence,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(new_aggregate)

                    log.info(f"Updated daily aggregates for chat date: {chat_date} (processed on {target_date})")

                    # Also create per-user aggregates for this date
                    results_by_user = {}
                    for result in date_results:
                        user_id = result.user_id
                        if user_id not in results_by_user:
                            results_by_user[user_id] = []
                        results_by_user[user_id].append(result)

                    # Create or update per-user aggregates
                    for user_id, user_results in results_by_user.items():
                        user_total_chats = len(user_results)
                        user_total_time_saved = sum(r.time_saved_minutes for r in user_results)
                        user_total_messages = sum(r.message_count for r in user_results)
                        user_total_active_time = sum(r.active_duration_minutes for r in user_results)
                        user_total_manual_time_estimated = sum(r.manual_time_most_likely for r in user_results)
                        user_avg_confidence = sum(r.confidence_level for r in user_results) / len(user_results)

                        # Check if per-user aggregate exists
                        existing_user_aggregate = db.query(DailyAggregate).filter_by(
                            analysis_date=chat_date,
                            user_id=user_id
                        ).first()

                        if existing_user_aggregate:
                            # Update existing per-user aggregate
                            existing_user_aggregate.chat_count += user_total_chats
                            existing_user_aggregate.total_time_saved += user_total_time_saved
                            existing_user_aggregate.message_count += user_total_messages
                            existing_user_aggregate.total_active_time += user_total_active_time
                            existing_user_aggregate.total_manual_time_estimated += user_total_manual_time_estimated
                            # Recalculate average confidence
                            existing_user_aggregate.avg_confidence_level = user_avg_confidence
                            existing_user_aggregate.updated_at = datetime.now()
                        else:
                            # Create new per-user aggregate
                            new_user_aggregate = DailyAggregate(
                                id=uuid.uuid4(),
                                analysis_date=chat_date,
                                user_id=user_id,  # Set to actual user UUID
                                chat_count=user_total_chats,
                                message_count=user_total_messages,
                                total_time_saved=user_total_time_saved,
                                total_active_time=user_total_active_time,
                                total_manual_time_estimated=user_total_manual_time_estimated,
                                avg_confidence_level=user_avg_confidence,
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            db.add(new_user_aggregate)

                        log.debug(f"Updated per-user aggregate for user {str(user_id)[:8]}... on {chat_date}")

                db.commit()
                log.info(f"Updated daily aggregates for {len(results_by_date)} different chat dates")

        except Exception as e:
            log.error(f"Failed to update daily aggregates: {str(e)}")
            raise