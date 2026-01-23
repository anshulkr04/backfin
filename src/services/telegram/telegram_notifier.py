#!/usr/bin/env python3
"""
Telegram Notifier Service

Handles formatting and sending notifications to Telegram users.
Includes rate limiting, retry logic, and error handling.
"""

import os
import sys
import logging
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from collections import deque

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Telegram imports
try:
    from telegram import Bot
    from telegram.constants import ParseMode
    from telegram.error import TelegramError, RetryAfter, Forbidden, BadRequest
except ImportError:
    print("Error: python-telegram-bot not installed. Run: pip install python-telegram-bot")
    sys.exit(1)

# Supabase
try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed. Run: pip install supabase")
    sys.exit(1)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TelegramNotifier')

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Rate limiting: Telegram allows ~30 messages/second
RATE_LIMIT_MESSAGES_PER_SECOND = 25  # Stay under limit
RATE_LIMIT_WINDOW_SECONDS = 1.0
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff


@dataclass
class NotificationResult:
    """Result of a notification attempt"""
    success: bool
    telegram_message_id: Optional[int] = None
    error_message: Optional[str] = None
    status: str = 'sent'  # 'sent', 'failed', 'rate_limited', 'blocked', 'user_stopped'


class RateLimiter:
    """Simple rate limiter using sliding window"""
    
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait until we can make another call"""
        async with self._lock:
            now = time.time()
            
            # Remove old calls outside the window
            while self.calls and now - self.calls[0] > self.window_seconds:
                self.calls.popleft()
            
            # If at limit, wait for oldest call to expire
            if len(self.calls) >= self.max_calls:
                sleep_time = self.window_seconds - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                self.calls.popleft()
            
            self.calls.append(time.time())


class TelegramNotifier:
    """Service for sending Telegram notifications"""
    
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL2 and SUPABASE_SERVICE_ROLE_KEY are required")
        
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.rate_limiter = RateLimiter(RATE_LIMIT_MESSAGES_PER_SECOND, RATE_LIMIT_WINDOW_SECONDS)
    
    def format_announcement_message(
        self,
        company_name: str,
        symbol: str,
        category: str,
        summary: str,
        headline: str = None,
        sentiment: str = None,
        date: str = None,
        file_url: str = None,
        corp_id: str = None
    ) -> str:
        """Format announcement notification message with Markdown"""
        
        # Emoji based on category
        category_emojis = {
            'Financial Results': '📊',
            'Investor Presentation': '📈',
            'Board Meeting': '🏢',
            'Dividend': '💰',
            'Bonus': '🎁',
            'Stock Split': '✂️',
            'Merger': '🤝',
            'Acquisition': '🛒',
            'Annual Report': '📘',
            'Quarterly Results': '📊',
            'Credit Rating': '⭐',
            'Insider Trading': '👤',
            'Corporate Action': '⚙️',
            'Regulatory': '📋',
        }
        
        emoji = category_emojis.get(category, '🔔')
        
        # Sentiment emoji
        sentiment_display = ''
        if sentiment:
            sentiment_lower = sentiment.lower()
            if 'positive' in sentiment_lower:
                sentiment_display = '📈 Positive'
            elif 'negative' in sentiment_lower:
                sentiment_display = '📉 Negative'
            elif 'neutral' in sentiment_lower:
                sentiment_display = '➡️ Neutral'
        
        # Build message
        message_parts = [
            f"{emoji} <b>New Announcement</b>",
            f"",
            f"🏢 <b>{self._escape_html(company_name)}</b>",
        ]
        
        if symbol:
            message_parts.append(f"📌 {self._escape_html(symbol)}")
        
        message_parts.append(f"📂 {self._escape_html(category)}")
        
        if date:
            message_parts.append(f"📅 {date}")
        
        message_parts.append("")  # Empty line
        
        # Add headline if available
        if headline:
            message_parts.append(f"<b>{self._escape_html(headline[:200])}</b>")
            message_parts.append("")
        
        # Add summary (truncated if too long)
        if summary:
            truncated_summary = summary[:500]
            if len(summary) > 500:
                truncated_summary += "..."
            message_parts.append(f"{self._escape_html(truncated_summary)}")
            message_parts.append("")
        
        # Add sentiment if available
        if sentiment_display:
            message_parts.append(f"💡 Sentiment: {sentiment_display}")
        
        # Add links
        message_parts.append("")
        
        if file_url:
            message_parts.append(f"📄 <a href='{file_url}'>View Document</a>")
        
        if corp_id:
            # Link to Backfin for detailed view
            backfin_url = f"https://backfin.in/announcement/{corp_id}"
            message_parts.append(f"🔗 <a href='{backfin_url}'>View on Backfin</a>")
        
        return "\n".join(message_parts)
    
    def format_insider_trading_message(
        self,
        company_name: str,
        symbol: str,
        person_name: str,
        person_category: str,
        transaction_type: str,
        shares: int,
        value: float,
        date: str = None
    ) -> str:
        """Format insider trading notification message"""
        
        # Transaction emoji
        if transaction_type and transaction_type.lower() in ['buy', 'acquisition', 'purchase']:
            txn_emoji = '🟢'
            txn_text = 'BUY'
        elif transaction_type and transaction_type.lower() in ['sell', 'sale', 'disposal']:
            txn_emoji = '🔴'
            txn_text = 'SELL'
        else:
            txn_emoji = '🔵'
            txn_text = transaction_type or 'TRADE'
        
        # Format value
        if value >= 10000000:  # 1 Crore+
            value_str = f"₹{value/10000000:.2f} Cr"
        elif value >= 100000:  # 1 Lakh+
            value_str = f"₹{value/100000:.2f} L"
        else:
            value_str = f"₹{value:,.0f}"
        
        # Format shares
        if shares >= 10000000:
            shares_str = f"{shares/10000000:.2f} Cr"
        elif shares >= 100000:
            shares_str = f"{shares/100000:.2f} L"
        else:
            shares_str = f"{shares:,}"
        
        message = (
            f"👤 <b>Insider Trading Alert</b>\n"
            f"\n"
            f"🏢 <b>{self._escape_html(company_name)}</b>\n"
            f"📌 {self._escape_html(symbol or '')}\n"
            f"\n"
            f"{txn_emoji} <b>{txn_text}</b> by {self._escape_html(person_name)}\n"
            f"👔 {self._escape_html(person_category or 'Insider')}\n"
            f"\n"
            f"📊 Shares: {shares_str}\n"
            f"💰 Value: {value_str}\n"
        )
        
        if date:
            message += f"📅 Date: {date}\n"
        
        return message
    
    def format_deal_message(
        self,
        company_name: str,
        symbol: str,
        client_name: str,
        deal_type: str,
        quantity: int,
        price: float,
        exchange: str,
        date: str = None
    ) -> str:
        """Format large deal notification message"""
        
        # Deal type emoji
        if deal_type and 'block' in deal_type.lower():
            deal_emoji = '📦'
        elif deal_type and 'bulk' in deal_type.lower():
            deal_emoji = '📊'
        else:
            deal_emoji = '💹'
        
        # Calculate total value
        total_value = quantity * price if quantity and price else 0
        
        # Format values
        if total_value >= 10000000:
            value_str = f"₹{total_value/10000000:.2f} Cr"
        elif total_value >= 100000:
            value_str = f"₹{total_value/100000:.2f} L"
        else:
            value_str = f"₹{total_value:,.0f}"
        
        message = (
            f"{deal_emoji} <b>Large Deal Alert</b>\n"
            f"\n"
            f"🏢 <b>{self._escape_html(company_name)}</b>\n"
            f"📌 {self._escape_html(symbol or '')} | {exchange or 'NSE'}\n"
            f"\n"
            f"👤 {self._escape_html(client_name or 'Unknown')}\n"
            f"📋 Deal Type: {self._escape_html(deal_type or 'N/A')}\n"
            f"📊 Quantity: {quantity:,}\n"
            f"💰 Price: ₹{price:,.2f}\n"
            f"💵 Total Value: {value_str}\n"
        )
        
        if date:
            message += f"📅 Date: {date}\n"
        
        return message
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not text:
            return ''
        return (
            str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )
    
    async def send_notification(
        self,
        chat_id: int,
        message: str,
        parse_mode: str = ParseMode.HTML,
        disable_preview: bool = True
    ) -> NotificationResult:
        """Send a single notification with rate limiting and retry logic"""
        
        for attempt in range(MAX_RETRIES):
            try:
                # Wait for rate limiter
                await self.rate_limiter.acquire()
                
                # Send message
                result = await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_preview
                )
                
                return NotificationResult(
                    success=True,
                    telegram_message_id=result.message_id,
                    status='sent'
                )
                
            except RetryAfter as e:
                # Telegram is rate limiting us - wait and retry
                logger.warning(f"Rate limited by Telegram. Waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                continue
                
            except Forbidden as e:
                # User blocked the bot or chat doesn't exist
                logger.warning(f"User {chat_id} blocked bot or chat not found: {e}")
                return NotificationResult(
                    success=False,
                    error_message=str(e),
                    status='user_stopped'
                )
                
            except BadRequest as e:
                # Invalid message or chat
                logger.error(f"Bad request for chat {chat_id}: {e}")
                return NotificationResult(
                    success=False,
                    error_message=str(e),
                    status='failed'
                )
                
            except TelegramError as e:
                # Other Telegram errors
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE * (2 ** attempt)
                    logger.warning(f"Telegram error (attempt {attempt + 1}): {e}. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send to {chat_id} after {MAX_RETRIES} attempts: {e}")
                    return NotificationResult(
                        success=False,
                        error_message=str(e),
                        status='failed'
                    )
        
        return NotificationResult(
            success=False,
            error_message="Max retries exceeded",
            status='failed'
        )
    
    async def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[Tuple[int, NotificationResult]]:
        """Send notifications to multiple users efficiently"""
        
        results = []
        
        for notification in notifications:
            chat_id = notification['chat_id']
            message = notification['message']
            
            result = await self.send_notification(chat_id, message)
            results.append((chat_id, result))
            
            # Log result
            if result.success:
                logger.info(f"Sent notification to {chat_id}")
            else:
                logger.warning(f"Failed to send to {chat_id}: {result.error_message}")
        
        return results
    
    async def log_notification(
        self,
        user_id: Optional[str],
        chat_id: int,
        corp_id: Optional[str],
        isin: Optional[str],
        company_name: Optional[str],
        category: Optional[str],
        notification_type: str,
        message_text: str,
        result: NotificationResult
    ):
        """Log notification result to database"""
        try:
            log_data = {
                'telegram_chat_id': chat_id,
                'notification_type': notification_type,
                'message_text': message_text[:1000] if message_text else None,  # Truncate long messages
                'notification_status': result.status,
                'telegram_message_id': result.telegram_message_id,
                'error_message': result.error_message,
                'sent_at': datetime.utcnow().isoformat() if result.success else None
            }
            
            if user_id:
                log_data['user_id'] = user_id
            if corp_id:
                log_data['corp_id'] = corp_id
            if isin:
                log_data['isin'] = isin
            if company_name:
                log_data['company_name'] = company_name
            if category:
                log_data['category'] = category
            
            self.supabase.table('telegram_notification_log').insert(log_data).execute()
            
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    async def update_subscription_stats(self, chat_id: int):
        """Update notification count and last notification time for subscription"""
        try:
            # Get current subscription
            response = self.supabase.table('user_telegram_subscriptions').select('notification_count').eq('telegram_chat_id', chat_id).execute()
            
            if response.data and len(response.data) > 0:
                current_count = response.data[0].get('notification_count', 0) or 0
                
                self.supabase.table('user_telegram_subscriptions').update({
                    'notification_count': current_count + 1,
                    'last_notification_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('telegram_chat_id', chat_id).execute()
                
        except Exception as e:
            logger.error(f"Failed to update subscription stats: {e}")
    
    async def handle_user_blocked(self, chat_id: int):
        """Handle case where user has blocked the bot"""
        try:
            self.supabase.table('user_telegram_subscriptions').update({
                'is_active': False,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('telegram_chat_id', chat_id).execute()
            
            logger.info(f"Marked subscription as inactive for blocked user {chat_id}")
        except Exception as e:
            logger.error(f"Failed to update blocked user status: {e}")
    
    def get_subscribers_for_isin_sync(self, isin: str) -> List[Dict]:
        """Synchronous version: Get all subscribers who have this ISIN in their watchlist"""
        try:
            # Use the helper function we created in SQL
            response = self.supabase.rpc(
                'get_telegram_subscribers_for_isin',
                {'target_isin': isin}
            ).execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error getting subscribers for ISIN {isin}: {e}")
            
            # Fallback to direct query
            try:
                response = self.supabase.table('watchlistdata').select(
                    'user_id_uuid'
                ).eq('isin', isin).execute()
                
                if not response.data:
                    return []
                
                user_ids = list(set([r['user_id_uuid'] for r in response.data if r.get('user_id_uuid')]))
                
                if not user_ids:
                    return []
                
                # Get telegram subscriptions for these users
                subs_response = self.supabase.table('user_telegram_subscriptions').select(
                    'user_id, telegram_chat_id, telegram_username'
                ).in_('user_id', user_ids).eq('is_active', True).eq('is_verified', True).execute()
                
                return subs_response.data if subs_response.data else []
                
            except Exception as e2:
                logger.error(f"Fallback query also failed: {e2}")
                return []


# Singleton instance for easy import
_notifier_instance: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Get or create singleton notifier instance"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance


async def send_announcement_notification(
    isin: str,
    company_name: str,
    symbol: str,
    category: str,
    summary: str,
    headline: str = None,
    sentiment: str = None,
    date: str = None,
    file_url: str = None,
    corp_id: str = None
) -> Dict[str, int]:
    """
    High-level function to send announcement notifications to all relevant subscribers.
    Returns stats dict with sent/failed counts.
    """
    notifier = get_notifier()
    
    # Get all subscribers for this ISIN
    subscribers = notifier.get_subscribers_for_isin_sync(isin)
    
    if not subscribers:
        logger.info(f"No subscribers for ISIN {isin}")
        return {'sent': 0, 'failed': 0, 'total_subscribers': 0}
    
    logger.info(f"Found {len(subscribers)} subscribers for {company_name} ({isin})")
    
    # Format the message once
    message = notifier.format_announcement_message(
        company_name=company_name,
        symbol=symbol,
        category=category,
        summary=summary,
        headline=headline,
        sentiment=sentiment,
        date=date,
        file_url=file_url,
        corp_id=corp_id
    )
    
    # Send to all subscribers
    sent_count = 0
    failed_count = 0
    
    for sub in subscribers:
        chat_id = sub.get('telegram_chat_id')
        user_id = sub.get('user_id')
        
        if not chat_id:
            continue
        
        result = await notifier.send_notification(chat_id, message)
        
        # Log the notification
        await notifier.log_notification(
            user_id=user_id,
            chat_id=chat_id,
            corp_id=corp_id,
            isin=isin,
            company_name=company_name,
            category=category,
            notification_type='announcement',
            message_text=message,
            result=result
        )
        
        if result.success:
            sent_count += 1
            await notifier.update_subscription_stats(chat_id)
        else:
            failed_count += 1
            if result.status == 'user_stopped':
                await notifier.handle_user_blocked(chat_id)
    
    logger.info(f"Notification complete for {company_name}: {sent_count} sent, {failed_count} failed")
    
    return {
        'sent': sent_count,
        'failed': failed_count,
        'total_subscribers': len(subscribers)
    }


# Synchronous wrapper for use in non-async code
def send_announcement_notification_sync(
    isin: str,
    company_name: str,
    symbol: str,
    category: str,
    summary: str,
    headline: str = None,
    sentiment: str = None,
    date: str = None,
    file_url: str = None,
    corp_id: str = None
) -> Dict[str, int]:
    """Synchronous wrapper for send_announcement_notification"""
    return asyncio.run(send_announcement_notification(
        isin=isin,
        company_name=company_name,
        symbol=symbol,
        category=category,
        summary=summary,
        headline=headline,
        sentiment=sentiment,
        date=date,
        file_url=file_url,
        corp_id=corp_id
    ))
