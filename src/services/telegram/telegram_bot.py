#!/usr/bin/env python3
"""
Telegram Bot Service for Backfin

Handles user subscription management and bot commands.
Runs as a standalone service with long-polling or webhook mode.
"""

import os
import sys
import logging
import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Telegram imports
try:
    from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, 
        CommandHandler, 
        MessageHandler, 
        CallbackQueryHandler,
        ContextTypes,
        filters
    )
    from telegram.constants import ParseMode
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
logger = logging.getLogger('TelegramBot')

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
VERIFICATION_CODE_EXPIRY_MINUTES = 10
BOT_NAME = os.getenv('TELEGRAM_BOT_NAME', 'ScreenAlphaBot')


class TelegramBotService:
    """Main Telegram Bot Service for user subscription management"""
    
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL2 and SUPABASE_SERVICE_ROLE_KEY are required")
        
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.application: Optional[Application] = None
        self.pending_verifications: Dict[int, Dict[str, Any]] = {}  # chat_id -> verification data
    
    def generate_verification_code(self) -> str:
        """Generate a 6-digit verification code"""
        return ''.join(random.choices(string.digits, k=6))
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email address"""
        try:
            response = self.supabase.table('UserData').select('*').ilike('emailID', email.strip()).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error finding user by email: {e}")
            return None
    
    async def get_user_by_phone(self, phone: str) -> Optional[Dict]:
        """Find user by phone number"""
        try:
            # Clean phone number
            clean_phone = ''.join(filter(str.isdigit, phone))
            response = self.supabase.table('UserData').select('*').eq('Phone_Number', clean_phone).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error finding user by phone: {e}")
            return None
    
    async def get_existing_subscription(self, chat_id: int) -> Optional[Dict]:
        """Check if chat_id already has a subscription"""
        try:
            response = self.supabase.table('user_telegram_subscriptions').select('*').eq('telegram_chat_id', chat_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error checking existing subscription: {e}")
            return None
    
    async def get_user_watchlist_count(self, user_id: str) -> int:
        """Get count of companies in user's watchlist"""
        try:
            response = self.supabase.table('watchlistdata').select('isin', count='exact').eq('user_id_uuid', user_id).execute()
            return response.count if response.count else 0
        except Exception as e:
            logger.error(f"Error getting watchlist count: {e}")
            return 0
    
    async def create_subscription(self, user_id: str, chat_id: int, username: str, first_name: str, last_name: str) -> bool:
        """Create or update Telegram subscription for user"""
        try:
            # Check if subscription already exists
            existing = await self.get_existing_subscription(chat_id)
            
            if existing:
                # Update existing subscription
                self.supabase.table('user_telegram_subscriptions').update({
                    'user_id': user_id,
                    'telegram_username': username,
                    'telegram_first_name': first_name,
                    'telegram_last_name': last_name,
                    'is_active': True,
                    'is_verified': True,
                    'subscribed_at': datetime.utcnow().isoformat(),
                    'unsubscribed_at': None,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('telegram_chat_id', chat_id).execute()
            else:
                # Create new subscription
                self.supabase.table('user_telegram_subscriptions').insert({
                    'user_id': user_id,
                    'telegram_chat_id': chat_id,
                    'telegram_username': username,
                    'telegram_first_name': first_name,
                    'telegram_last_name': last_name,
                    'is_active': True,
                    'is_verified': True,
                    'subscribed_at': datetime.utcnow().isoformat()
                }).execute()
            
            logger.info(f"Created/updated subscription for user {user_id}, chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return False
    
    async def deactivate_subscription(self, chat_id: int) -> bool:
        """Deactivate Telegram subscription"""
        try:
            self.supabase.table('user_telegram_subscriptions').update({
                'is_active': False,
                'unsubscribed_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }).eq('telegram_chat_id', chat_id).execute()
            
            logger.info(f"Deactivated subscription for chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error deactivating subscription: {e}")
            return False
    
    async def reactivate_subscription(self, chat_id: int) -> bool:
        """Reactivate Telegram subscription"""
        try:
            self.supabase.table('user_telegram_subscriptions').update({
                'is_active': True,
                'unsubscribed_at': None,
                'subscribed_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }).eq('telegram_chat_id', chat_id).execute()
            
            logger.info(f"Reactivated subscription for chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error reactivating subscription: {e}")
            return False

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Check if already subscribed
        existing = await self.get_existing_subscription(chat_id)
        
        if existing and existing.get('is_verified') and existing.get('is_active'):
            watchlist_count = await self.get_user_watchlist_count(existing['user_id'])
            await update.message.reply_text(
                f"👋 Welcome back, {user.first_name}!\n\n"
                f"✅ You're already subscribed to ScreenAlpha notifications.\n"
                f"📊 Tracking: {watchlist_count} companies in your watchlist\n\n"
                f"Commands:\n"
                f"/status - Check subscription status\n"
                f"/unsubscribe - Pause notifications\n"
                f"/help - Get help",
                parse_mode=ParseMode.HTML
            )
            return
        
        welcome_message = (
            f"👋 Welcome to <b>ScreenAlpha Alerts</b>, {user.first_name}!\n\n"
            f"🔔 Get instant notifications when companies in your watchlist make announcements.\n\n"
            f"To get started, I need to link your Telegram to your ScreenAlpha account.\n\n"
            f"Please enter your <b>registered email address</b>:"
        )
        
        # Store pending verification state
        self.pending_verifications[chat_id] = {
            'state': 'awaiting_email',
            'started_at': datetime.utcnow(),
            'user_info': {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name or ''
            }
        }
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)
    
    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command"""
        chat_id = update.effective_chat.id
        existing = await self.get_existing_subscription(chat_id)
        
        if existing:
            if existing.get('is_active') and existing.get('is_verified'):
                await update.message.reply_text(
                    "✅ You're already subscribed to notifications!\n\n"
                    "Use /status to check your subscription details."
                )
            elif existing.get('is_verified') and not existing.get('is_active'):
                # Reactivate subscription
                if await self.reactivate_subscription(chat_id):
                    await update.message.reply_text(
                        "✅ Welcome back! Your notifications have been reactivated.\n\n"
                        "You'll now receive alerts for companies in your watchlist."
                    )
                else:
                    await update.message.reply_text(
                        "❌ Sorry, something went wrong. Please try again later."
                    )
            else:
                # Not verified - restart verification
                await self.cmd_start(update, context)
        else:
            # No subscription - start fresh
            await self.cmd_start(update, context)
    
    async def cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unsubscribe command"""
        chat_id = update.effective_chat.id
        existing = await self.get_existing_subscription(chat_id)
        
        if not existing:
            await update.message.reply_text(
                "You don't have an active subscription.\n\n"
                "Use /start to subscribe to notifications."
            )
            return
        
        if not existing.get('is_active'):
            await update.message.reply_text(
                "Your notifications are already paused.\n\n"
                "Use /subscribe to reactivate them."
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, unsubscribe", callback_data="confirm_unsub"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_unsub")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ Are you sure you want to unsubscribe?\n\n"
            "You won't receive notifications for new announcements.\n"
            "You can resubscribe anytime with /subscribe.",
            reply_markup=reply_markup
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        chat_id = update.effective_chat.id
        existing = await self.get_existing_subscription(chat_id)
        
        if not existing:
            await update.message.reply_text(
                "❌ You don't have a subscription.\n\n"
                "Use /start to subscribe to notifications."
            )
            return
        
        user_id = existing.get('user_id')
        watchlist_count = await self.get_user_watchlist_count(user_id) if user_id else 0
        notification_count = existing.get('notification_count', 0)
        last_notification = existing.get('last_notification_at', 'Never')
        
        status_emoji = "✅" if existing.get('is_active') else "⏸️"
        status_text = "Active" if existing.get('is_active') else "Paused"
        
        status_message = (
            f"📊 <b>Subscription Status</b>\n\n"
            f"{status_emoji} Status: <b>{status_text}</b>\n"
            f"📈 Companies tracked: <b>{watchlist_count}</b>\n"
            f"🔔 Notifications received: <b>{notification_count}</b>\n"
            f"🕐 Last notification: <b>{last_notification}</b>\n\n"
        )
        
        if existing.get('is_active'):
            status_message += "Use /unsubscribe to pause notifications."
        else:
            status_message += "Use /subscribe to resume notifications."
        
        await update.message.reply_text(status_message, parse_mode=ParseMode.HTML)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🔔 <b>ScreenAlpha Alerts Bot</b>\n\n"
            "Get instant Telegram notifications when companies in your ScreenAlpha watchlist make announcements.\n\n"
            "<b>Commands:</b>\n"
            "/start - Link your Telegram to ScreenAlpha account\n"
            "/subscribe - Reactivate notifications\n"
            "/unsubscribe - Pause notifications\n"
            "/status - Check your subscription status\n"
            "/help - Show this help message\n\n"
            "<b>How it works:</b>\n"
            "1. Create your watchlist at screenalpha.in\n"
            "2. Link your Telegram here (one-time setup)\n"
            "3. Get instant alerts for your watchlist companies!\n\n"
            "💡 Manage your watchlist at screenalpha.in\n"
            "📧 Need help? Contact support@screenalpha.in"
        )
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline buttons"""
        query = update.callback_query
        await query.answer()
        
        chat_id = update.effective_chat.id
        
        if query.data == "confirm_unsub":
            if await self.deactivate_subscription(chat_id):
                await query.edit_message_text(
                    "✅ You've been unsubscribed.\n\n"
                    "You won't receive notifications anymore.\n"
                    "Use /subscribe anytime to reactivate."
                )
            else:
                await query.edit_message_text(
                    "❌ Something went wrong. Please try again."
                )
        
        elif query.data == "cancel_unsub":
            await query.edit_message_text(
                "👍 Unsubscribe cancelled.\n\n"
                "You'll continue receiving notifications."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages (for verification flow)"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        
        # Check if user is in verification flow
        if chat_id not in self.pending_verifications:
            await update.message.reply_text(
                "I didn't understand that. Use /help to see available commands."
            )
            return
        
        verification = self.pending_verifications[chat_id]
        state = verification.get('state')
        
        # Check if verification expired (10 minutes)
        if datetime.utcnow() - verification['started_at'] > timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES):
            del self.pending_verifications[chat_id]
            await update.message.reply_text(
                "⏰ Verification session expired.\n\n"
                "Please use /start to try again."
            )
            return
        
        if state == 'awaiting_email':
            # User sent their email
            email = text.lower()
            
            # Basic email validation
            if '@' not in email or '.' not in email:
                await update.message.reply_text(
                    "❌ That doesn't look like a valid email address.\n\n"
                    "Please enter your registered email:"
                )
                return
            
            # Look up user by email
            user = await self.get_user_by_email(email)
            
            if not user:
                await update.message.reply_text(
                    "❌ No account found with this email.\n\n"
                    "Please make sure you're using the email registered with ScreenAlpha, "
                    "or sign up at screenalpha.in first."
                )
                return
            
            # Generate and store verification code
            code = self.generate_verification_code()
            verification['state'] = 'awaiting_code'
            verification['email'] = email
            verification['user'] = user
            verification['code'] = code
            verification['code_sent_at'] = datetime.utcnow()
            
            # In production, send code via email
            # For now, we'll skip email verification for simplicity
            # and just verify immediately (you can add email sending later)
            
            # AUTO-VERIFY for now (remove this block and send actual email in production)
            user_info = verification['user_info']
            if await self.create_subscription(
                user_id=user['UserID'],
                chat_id=chat_id,
                username=user_info['username'],
                first_name=user_info['first_name'],
                last_name=user_info['last_name']
            ):
                watchlist_count = await self.get_user_watchlist_count(user['UserID'])
                del self.pending_verifications[chat_id]
                
                await update.message.reply_text(
                    f"✅ <b>Successfully subscribed!</b>\n\n"
                    f"Your Telegram is now linked to your ScreenAlpha account.\n\n"
                    f"📊 Currently tracking: <b>{watchlist_count}</b> companies\n\n"
                    f"You'll receive instant notifications when companies in your "
                    f"watchlist make announcements.\n\n"
                    f"💡 Tip: Add more companies to your watchlist at screenalpha.in",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    "❌ Something went wrong. Please try again with /start"
                )
            
            return
            
            # PRODUCTION CODE (uncomment when email sending is set up):
            # try:
            #     # Send verification email
            #     await self.send_verification_email(email, code)
            #     await update.message.reply_text(
            #         f"📧 Verification code sent to {email}\n\n"
            #         f"Please enter the 6-digit code:"
            #     )
            # except Exception as e:
            #     logger.error(f"Failed to send verification email: {e}")
            #     await update.message.reply_text(
            #         "❌ Failed to send verification email. Please try again."
            #     )
        
        elif state == 'awaiting_code':
            # User sent verification code
            if text == verification.get('code'):
                # Code matches - create subscription
                user = verification['user']
                user_info = verification['user_info']
                
                if await self.create_subscription(
                    user_id=user['UserID'],
                    chat_id=chat_id,
                    username=user_info['username'],
                    first_name=user_info['first_name'],
                    last_name=user_info['last_name']
                ):
                    watchlist_count = await self.get_user_watchlist_count(user['UserID'])
                    del self.pending_verifications[chat_id]
                    
                    await update.message.reply_text(
                        f"✅ <b>Successfully subscribed!</b>\n\n"
                        f"📊 Currently tracking: <b>{watchlist_count}</b> companies\n\n"
                        f"You'll receive instant notifications when companies in your "
                        f"watchlist make announcements.",
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await update.message.reply_text(
                        "❌ Something went wrong. Please try again with /start"
                    )
            else:
                await update.message.reply_text(
                    "❌ Invalid code. Please try again or use /start to restart."
                )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Error: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    
    def setup_handlers(self):
        """Set up command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.application.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_status))  # Alias
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        self.application.add_error_handler(self.error_handler)
    
    async def run(self):
        """Run the bot with long polling"""
        logger.info("Starting Telegram Bot...")
        
        self.application = Application.builder().token(self.bot_token).build()
        self.setup_handlers()
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        logger.info(f"Bot started! Listening for messages...")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for an hour, check periodically
        except asyncio.CancelledError:
            pass
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()


async def main():
    """Main entry point"""
    bot = TelegramBotService()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)
