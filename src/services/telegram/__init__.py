# Telegram Services Package
"""
Telegram notification services for Backfin.

This package provides:
- TelegramBotService: Handles user subscription management
- TelegramNotifier: Handles sending notifications
"""

from .telegram_notifier import (
    TelegramNotifier,
    get_notifier,
    send_announcement_notification,
    send_announcement_notification_sync,
    NotificationResult
)

__all__ = [
    'TelegramNotifier',
    'get_notifier',
    'send_announcement_notification',
    'send_announcement_notification_sync',
    'NotificationResult'
]
