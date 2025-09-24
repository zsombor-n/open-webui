"""
Analytics Processor Service

This service handles the core analytics processing pipeline:
1. Fetches conversations from OpenWebUI database
2. Creates intelligent summaries with privacy-preserving redaction
3. Calls GPT-5-mini API for time estimation analysis
4. Calculates time savings metrics
5. Stores results in Cogniforce analytics database
6. Tracks processing statistics and costs

The processor is designed to handle both manual triggers and scheduled runs.
"""

import json
import time
import hashlib
import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import re

import openai
import aiohttp
from sqlalchemy import text
from open_webui.internal.db import get_db
from open_webui.internal.cogniforce_db import get_cogniforce_db
from open_webui.cogniforce_models.analytics_tables import (
    ConversationAnalysis, DailyAggregate, ProcessingLog
)

log = logging.getLogger(__name__)


class AnalyticsProcessor:
    """
    Core analytics processing engine for conversation analysis and time estimation.

    This processor integrates with GPT-5-mini to provide accurate manual time estimates
    for conversations, calculating how much time users saved by using AI assistance.
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

    async def process_conversations_for_date(self, target_date: date) -> Dict[str, Any]:
        """
        Main entry point for processing conversations for a specific date.

        Args:
            target_date: Date to process conversations for

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

            # Fetch conversations for the target date
            log.info("\n[STEP 1] 📥 FETCHING CONVERSATIONS...")
            conversations = await self._fetch_conversations_for_date(target_date)
            log.info(f"[STEP 1] ✅ Found {len(conversations)} conversations to process")

            if conversations:
                log.info("[STEP 1] 📋 Conversation Summary:")
                for i, conv in enumerate(conversations, 1):
                    log.info(f"[STEP 1]   {i}. ID: {conv['id'][:8]}... | Title: {conv['title'][:50]}...")
            else:
                log.warning("[STEP 1] ⚠️  No conversations found for processing")

            if not conversations:
                return await self._complete_processing_log(
                    processing_log_id, processing_start,
                    conversations_processed=0, status="completed"
                )

            # Process each conversation
            log.info(f"\n[STEP 2] ⚙️  PROCESSING {len(conversations)} CONVERSATIONS...")
            results = []
            processed_count = 0
            failed_count = 0
            total_cost = 0.0
            total_llm_requests = 0

            for i, conv_data in enumerate(conversations, 1):
                try:
                    log.info(f"\n[STEP 2.{i}] 🔄 Processing conversation {i}/{len(conversations)}")
                    log.info(f"[STEP 2.{i}] 📝 ID: {conv_data['id']}")
                    log.info(f"[STEP 2.{i}] 👤 User: {conv_data.get('user_name', 'Unknown')} ({conv_data.get('user_email', 'N/A')})")
                    log.info(f"[STEP 2.{i}] 📋 Title: {conv_data.get('title', 'Untitled')}")

                    result = await self._analyze_conversation(conv_data)
                    if result:
                        results.append(result)
                        processed_count += 1
                        total_cost += result.get('llm_cost', 0.0)
                        total_llm_requests += 1

                        log.info(f"[STEP 2.{i}] ✅ Successfully processed!")
                        log.info(f"[STEP 2.{i}] 💰 Cost: ${result.get('llm_cost', 0.0):.4f}")
                        log.info(f"[STEP 2.{i}] ⏱️  Time Saved: {result.get('time_saved_minutes', 0)} minutes")
                        log.info(f"[STEP 2.{i}] 🎯 Confidence: {result.get('confidence_level', 0)}%")
                    else:
                        failed_count += 1
                        log.warning(f"[STEP 2.{i}] ❌ Failed to process conversation {conv_data['id']}")

                except Exception as e:
                    failed_count += 1
                    log.error(f"[STEP 2.{i}] 💥 Error processing conversation {conv_data['id']}: {str(e)}")
                    continue

            # Update daily aggregates
            log.info(f"\n[STEP 3] 📊 UPDATING DAILY AGGREGATES...")
            await self._update_daily_aggregates(target_date, results)
            log.info(f"[STEP 3] ✅ Daily aggregates updated for {target_date}")

            # Complete processing log
            log.info(f"\n[STEP 4] 📝 COMPLETING PROCESSING LOG...")
            processing_result = await self._complete_processing_log(
                processing_log_id, processing_start,
                conversations_processed=processed_count,
                conversations_failed=failed_count,
                total_llm_requests=total_llm_requests,
                total_llm_cost_usd=total_cost,
                status="completed"
            )

            # Final summary
            total_time_saved = sum(r.get('time_saved_minutes', 0) for r in results)
            duration_seconds = processing_result.get('duration_seconds', 0)

            log.info("=" * 60)
            log.info("🎉 ANALYTICS PROCESSING COMPLETED SUCCESSFULLY!")
            log.info("=" * 60)
            log.info(f"[SUMMARY] 📈 Conversations Processed: {processed_count}")
            log.info(f"[SUMMARY] ❌ Conversations Failed: {failed_count}")
            log.info(f"[SUMMARY] 🤖 OpenAI API Calls: {total_llm_requests}")
            log.info(f"[SUMMARY] 💰 Total Cost: ${total_cost:.4f}")
            log.info(f"[SUMMARY] ⏱️  Total Time Saved: {total_time_saved} minutes")
            log.info(f"[SUMMARY] ⏲️  Processing Duration: {duration_seconds} seconds")
            log.info(f"[SUMMARY] 📊 Processing Log ID: {processing_log_id}")
            log.info("=" * 60)

            return processing_result

        except Exception as e:
            # Mark processing as failed
            await self._complete_processing_log(
                processing_log_id, processing_start,
                status="failed", error_message=str(e)
            )
            log.error(f"Analytics processing failed: {str(e)}")
            raise

    async def _fetch_conversations_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Fetch conversations from OpenWebUI database for the target date.

        For development: fetches ALL conversations since we only have 2 test conversations.
        In production: would filter by date.

        Args:
            target_date: Date to fetch conversations for

        Returns:
            List of conversation data dictionaries
        """
        try:
            with get_db() as db:
                # For development: get ALL conversations (we only have 2)
                # In production: add date filtering
                result = db.execute(text("""
                    SELECT
                        c.id,
                        c.user_id,
                        c.title,
                        c.chat,
                        c.created_at,
                        c.updated_at,
                        u.email as user_email,
                        u.name as user_name
                    FROM chat c
                    JOIN "user" u ON c.user_id = u.id
                    ORDER BY c.created_at DESC
                """))

                conversations = []
                for row in result.fetchall():
                    conversations.append({
                        'id': row[0],
                        'user_id': row[1],
                        'title': row[2],
                        'chat': row[3],
                        'created_at': row[4],
                        'updated_at': row[5],
                        'user_email': row[6],
                        'user_name': row[7]
                    })

                return conversations

        except Exception as e:
            log.error(f"Failed to fetch conversations: {str(e)}")
            raise

    async def _analyze_conversation(self, conv_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze a single conversation using GPT-5-mini.

        Args:
            conv_data: Conversation data from database

        Returns:
            Analysis results or None if failed
        """
        try:
            # Extract conversation details
            conversation_id = conv_data['id']
            chat_data = conv_data['chat']

            log.info(f"    📊 EXTRACTING CONVERSATION DATA...")
            log.info(f"    📝 Conversation ID: {conversation_id}")

            if not chat_data or 'messages' not in chat_data:
                log.warning(f"    ⚠️  No messages found in conversation {conversation_id}")
                return None

            messages = chat_data['messages']
            if not messages:
                log.warning(f"    ⚠️  Empty messages list for conversation {conversation_id}")
                return None

            log.info(f"    💬 Messages found: {len(messages)}")

            # Calculate time metrics
            log.info(f"    ⏱️  CALCULATING TIME METRICS...")
            time_metrics = self._calculate_time_metrics(messages, conv_data)
            log.info(f"    ⏱️  First message: {time_metrics['first_message_at']}")
            log.info(f"    ⏱️  Last message: {time_metrics['last_message_at']}")
            log.info(f"    ⏱️  Total duration: {time_metrics['total_duration_minutes']} minutes")
            log.info(f"    ⏱️  Active duration: {time_metrics['active_duration_minutes']} minutes")
            log.info(f"    ⏱️  Idle time: {time_metrics['idle_time_minutes']} minutes")

            # Create smart summary for LLM analysis
            log.info(f"    📝 CREATING SMART SUMMARY...")
            conversation_summary = self._create_smart_summary(conv_data, messages)
            log.info(f"    📝 Summary length: {len(conversation_summary)} characters")

            # Get time estimation from GPT-5-mini
            log.info(f"    🤖 CALLING GPT-5-MINI API...")
            log.info(f"    🤖 Model: {self.model}")
            log.info(f"    🤖 Temperature: default (1) - GPT-5-mini requirement")
            log.info(f"    🤖 Max Completion Tokens: {self.max_tokens}")

            llm_response = await self._estimate_manual_time(conversation_summary)

            if not llm_response:
                log.error(f"    ❌ Failed to get LLM response for conversation {conversation_id}")
                return None

            log.info(f"    🤖 ✅ GPT-5-mini response received!")

            # Parse LLM response
            log.info(f"    🔍 PARSING TIME ESTIMATES...")
            time_estimates = self._parse_time_estimates(llm_response)
            log.info(f"    🔍 Low estimate: {time_estimates.get('low', 0)} minutes")
            log.info(f"    🔍 Most likely: {time_estimates.get('most_likely', 0)} minutes")
            log.info(f"    🔍 High estimate: {time_estimates.get('high', 0)} minutes")
            log.info(f"    🔍 Confidence: {time_estimates.get('confidence', 0)}%")

            # Calculate time saved
            log.info(f"    📈 CALCULATING TIME SAVINGS...")
            manual_time_most_likely = time_estimates.get('most_likely', 0)
            active_duration = time_metrics['active_duration_minutes']
            time_saved = max(0, manual_time_most_likely - active_duration)
            log.info(f"    📈 Manual estimate: {manual_time_most_likely} minutes")
            log.info(f"    📈 AI-assisted time: {active_duration} minutes")
            log.info(f"    📈 Time saved: {time_saved} minutes")

            # Store analysis results
            log.info(f"    💾 STORING ANALYSIS RESULTS...")
            analysis_id = await self._store_analysis_results(
                conversation_id=conversation_id,
                user_email=conv_data['user_email'],
                time_metrics=time_metrics,
                time_estimates=time_estimates,
                time_saved_minutes=time_saved,
                conversation_summary=conversation_summary,
                llm_response=llm_response,
                message_count=len(messages)
            )
            log.info(f"    💾 ✅ Analysis stored with ID: {analysis_id}")

            return {
                'analysis_id': analysis_id,
                'conversation_id': conversation_id,
                'time_saved_minutes': time_saved,
                'active_duration_minutes': time_metrics['active_duration_minutes'],
                'manual_time_most_likely': time_estimates.get('most_likely', 0),
                'message_count': len(messages),
                'confidence_level': time_estimates.get('confidence', 0),
                'llm_cost': 0.001  # Estimated cost per request for GPT-5-mini
            }

        except Exception as e:
            log.error(f"Error analyzing conversation {conv_data.get('id', 'unknown')}: {str(e)}")
            return None

    def _calculate_time_metrics(self, messages: List[Dict], conv_data: Dict) -> Dict[str, Any]:
        """
        Calculate timing metrics for the conversation.

        Args:
            messages: List of conversation messages
            conv_data: Conversation metadata

        Returns:
            Dictionary with timing metrics
        """
        if not messages:
            return {
                'first_message_at': datetime.now(),
                'last_message_at': datetime.now(),
                'total_duration_minutes': 0,
                'active_duration_minutes': 0,
                'idle_time_minutes': 0
            }

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

        return {
            'first_message_at': first_message_at,
            'last_message_at': last_message_at,
            'total_duration_minutes': total_duration_minutes,
            'active_duration_minutes': active_duration_minutes,
            'idle_time_minutes': idle_time_minutes
        }

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
            conv_data: Conversation metadata
            messages: List of messages

        Returns:
            Redacted conversation summary
        """
        # Extract conversation content
        title = conv_data.get('title', 'Untitled Conversation')
        user_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'user']
        assistant_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'assistant']

        # Combine all content for analysis
        full_content = f"Title: {title}\n"
        full_content += "User Messages:\n" + "\n".join(user_messages[:3])  # First 3 user messages
        full_content += "\nAssistant Messages:\n" + "\n".join(assistant_messages[:2])  # First 2 assistant messages

        # Smart redaction - preserve public information
        redacted_summary = self._apply_smart_redaction(full_content)

        # Add metadata for context
        summary = f"""Conversation Analysis Summary:

Topic: {title}
Message Count: {len(messages)}
User Messages: {len(user_messages)}
Assistant Messages: {len(assistant_messages)}

Content Overview:
{redacted_summary}

This conversation required the user to engage in back-and-forth dialogue with an AI assistant to complete their task."""

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

    async def _estimate_manual_time(self, conversation_summary: str) -> Optional[Dict[str, Any]]:
        """
        Use GPT-5-mini to estimate manual completion time.

        Args:
            conversation_summary: Redacted conversation summary

        Returns:
            LLM response with time estimates or None if failed
        """
        system_prompt = """You are an expert at estimating how long tasks would take to complete manually without AI assistance.

Analyze the provided conversation summary and estimate how long it would have taken the user to complete the same task manually through research, writing, coding, or other methods.

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
            log.info(f"        📝 User content length: {len(conversation_summary)} characters")
            log.info(f"        🔑 API key configured: {'Yes' if self.openai_api_key else 'Using env var'}")

            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},  # GPT-5-mini uses standard "system" role
                    {"role": "user", "content": conversation_summary}
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

    async def _estimate_manual_time_http(self, conversation_summary: str) -> Optional[Dict[str, Any]]:
        """
        Estimate manual completion time using direct HTTP calls to GPT-5-mini API.
        This bypasses the OpenAI Python library parsing issue with GPT-5-mini responses.

        Args:
            conversation_summary: Redacted conversation summary

        Returns:
            LLM response with time estimates or None if failed
        """
        system_prompt = """You are an expert at estimating how long tasks would take to complete manually without AI assistance.

Analyze the provided conversation summary and estimate how long it would have taken the user to complete the same task manually through research, writing, coding, or other methods.

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
                {"role": "user", "content": conversation_summary}
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
            log.info(f"        📝 User content length: {len(conversation_summary)} characters")
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

    def _parse_time_estimates(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate time estimates from LLM response.

        Args:
            llm_response: Raw LLM response

        Returns:
            Validated time estimates
        """
        try:
            return {
                'low': max(0, int(llm_response.get('manual_time_low', 0))),
                'most_likely': max(0, int(llm_response.get('manual_time_most_likely', 0))),
                'high': max(0, int(llm_response.get('manual_time_high', 0))),
                'confidence': max(0, min(100, int(llm_response.get('confidence_level', 0))))
            }
        except (ValueError, TypeError):
            log.warning("Failed to parse time estimates, using defaults")
            return {
                'low': 0,
                'most_likely': 0,
                'high': 0,
                'confidence': 0
            }

    async def _store_analysis_results(self, **kwargs) -> str:
        """
        Store conversation analysis results in the database.

        Returns:
            Analysis record ID
        """
        try:
            with get_cogniforce_db() as db:
                # Hash user email for privacy
                user_email = kwargs['user_email']
                user_id_hash = hashlib.sha256(user_email.encode()).hexdigest()

                # Create analysis record
                analysis = ConversationAnalysis(
                    conversation_id=kwargs['conversation_id'],
                    user_id_hash=user_id_hash,
                    first_message_at=kwargs['time_metrics']['first_message_at'],
                    last_message_at=kwargs['time_metrics']['last_message_at'],
                    total_duration_minutes=kwargs['time_metrics']['total_duration_minutes'],
                    active_duration_minutes=kwargs['time_metrics']['active_duration_minutes'],
                    idle_time_minutes=kwargs['time_metrics']['idle_time_minutes'],
                    manual_time_low=kwargs['time_estimates']['low'],
                    manual_time_most_likely=kwargs['time_estimates']['most_likely'],
                    manual_time_high=kwargs['time_estimates']['high'],
                    confidence_level=kwargs['time_estimates']['confidence'],
                    time_saved_minutes=kwargs['time_saved_minutes'],
                    message_count=kwargs['message_count'],
                    conversation_summary=kwargs['conversation_summary'],
                    llm_response=kwargs['llm_response']
                )

                db.add(analysis)
                db.commit()

                log.info(f"Stored analysis results for conversation {kwargs['conversation_id']}")
                return str(analysis.id)

        except Exception as e:
            log.error(f"Failed to store analysis results: {str(e)}")
            raise

    async def _create_processing_log(self, run_date: date, started_at: datetime) -> str:
        """Create processing log entry and return its ID."""
        try:
            with get_cogniforce_db() as db:
                log_entry = ProcessingLog(
                    run_date=run_date,
                    started_at=started_at,
                    status='running'
                )
                db.add(log_entry)
                db.commit()
                return str(log_entry.id)
        except Exception as e:
            log.error(f"Failed to create processing log: {str(e)}")
            raise

    async def _complete_processing_log(self, log_id: str, started_at: datetime, **kwargs) -> Dict[str, Any]:
        """Complete processing log with final statistics."""
        try:
            with get_cogniforce_db() as db:
                completed_at = datetime.now()
                duration_seconds = int((completed_at - started_at).total_seconds())

                db.execute(text("""
                    UPDATE processing_log
                    SET completed_at = :completed_at,
                        status = :status,
                        conversations_processed = :conversations_processed,
                        conversations_failed = :conversations_failed,
                        total_llm_requests = :total_llm_requests,
                        total_llm_cost_usd = :total_llm_cost_usd,
                        processing_duration_seconds = :processing_duration_seconds,
                        error_message = :error_message
                    WHERE id = :log_id
                """), {
                    'log_id': log_id,
                    'completed_at': completed_at,
                    'status': kwargs.get('status', 'completed'),
                    'conversations_processed': kwargs.get('conversations_processed', 0),
                    'conversations_failed': kwargs.get('conversations_failed', 0),
                    'total_llm_requests': kwargs.get('total_llm_requests', 0),
                    'total_llm_cost_usd': kwargs.get('total_llm_cost_usd', 0.0),
                    'processing_duration_seconds': duration_seconds,
                    'error_message': kwargs.get('error_message')
                })
                db.commit()

                return {
                    'processing_log_id': log_id,
                    'status': kwargs.get('status', 'completed'),
                    'duration_seconds': duration_seconds,
                    'conversations_processed': kwargs.get('conversations_processed', 0),
                    'conversations_failed': kwargs.get('conversations_failed', 0),
                    'total_cost_usd': kwargs.get('total_llm_cost_usd', 0.0)
                }

        except Exception as e:
            log.error(f"Failed to complete processing log: {str(e)}")
            raise

    async def _update_daily_aggregates(self, target_date: date, results: List[Dict]) -> None:
        """Update daily aggregates with processing results."""
        if not results:
            return

        try:
            with get_cogniforce_db() as db:
                # Global aggregate (user_id_hash = NULL)
                total_conversations = len(results)
                total_time_saved = sum(r['time_saved_minutes'] for r in results)
                total_messages = sum(r.get('message_count', 0) for r in results)
                total_active_time = sum(r.get('active_duration_minutes', 0) for r in results)
                total_manual_time_estimated = sum(r.get('manual_time_most_likely', 0) for r in results)
                avg_confidence = sum(r['confidence_level'] for r in results) / len(results)

                # Insert or update global aggregate
                aggregate_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO daily_aggregates
                    (id, analysis_date, user_id_hash, conversation_count, message_count, total_time_saved, total_active_time, total_manual_time_estimated, avg_confidence_level)
                    VALUES (:id, :date, NULL, :conversations, :messages, :time_saved, :active_time, :manual_time, :confidence)
                    ON CONFLICT (analysis_date, user_id_hash)
                    DO UPDATE SET
                        conversation_count = daily_aggregates.conversation_count + EXCLUDED.conversation_count,
                        message_count = daily_aggregates.message_count + EXCLUDED.message_count,
                        total_time_saved = daily_aggregates.total_time_saved + EXCLUDED.total_time_saved,
                        total_active_time = daily_aggregates.total_active_time + EXCLUDED.total_active_time,
                        total_manual_time_estimated = daily_aggregates.total_manual_time_estimated + EXCLUDED.total_manual_time_estimated,
                        avg_confidence_level = (daily_aggregates.avg_confidence_level + EXCLUDED.avg_confidence_level) / 2,
                        updated_at = :updated_at
                """), {
                    'id': aggregate_id,
                    'date': target_date,
                    'conversations': total_conversations,
                    'messages': total_messages,
                    'time_saved': total_time_saved,
                    'active_time': total_active_time,
                    'manual_time': total_manual_time_estimated,
                    'confidence': avg_confidence,
                    'updated_at': datetime.now()
                })

                db.commit()
                log.info(f"Updated daily aggregates for {target_date}")

        except Exception as e:
            log.error(f"Failed to update daily aggregates: {str(e)}")
            raise