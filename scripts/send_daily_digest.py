#!/usr/bin/env python3
"""
Daily Digest Email Sender
Sends watchlist-based announcement digests to users

This script processes pending notifications and sends daily digest emails
to users with announcements from companies in their watchlist.

Usage:
    python3 send_daily_digest.py [--date YYYY-MM-DD] [--test-user USER_ID] [--dry-run]

Cron Setup:
    0 18 * * * cd /Users/anshulkumar/backfin && python3 scripts/send_daily_digest.py >> /var/log/backfin/digest.log 2>&1
"""

import os
import sys
import argparse
from datetime import datetime, date
from typing import List, Dict, Optional
import logging
import traceback

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client

# Setup logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_DIR = os.path.abspath(LOG_DIR)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{LOG_DIR}/digest_{date.today().isoformat()}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('daily_digest')

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')
RESEND_API_KEY = os.getenv('RESEND_API_KEY')

if not all([SUPABASE_URL, SUPABASE_KEY, RESEND_API_KEY]):
    logger.error("❌ Missing required environment variables: SUPABASE_URL2, SUPABASE_KEY2, RESEND_API")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import notification service
try:
    from src.services.notification_service import AnnouncementMailer
    mailer = AnnouncementMailer(api_key=RESEND_API_KEY)
except ImportError as e:
    logger.error(f"❌ Failed to import notification service: {e}")
    sys.exit(1)


def get_users_with_pending_notifications(target_date: date) -> List[str]:
    """Get list of users with pending notifications for the given date"""
    try:
        response = supabase.table('user_notification_queue')\
            .select('user_id')\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        # Deduplicate user IDs
        user_ids = list(set([row['user_id'] for row in response.data]))
        logger.info(f"📊 Found {len(user_ids)} users with pending notifications")
        return user_ids
    except Exception as e:
        logger.error(f"❌ Failed to fetch users: {e}")
        return []


def get_user_notifications(user_id: str, target_date: date) -> List[Dict]:
    """Get all pending notifications for a user on the given date"""
    try:
        response = supabase.table('user_notification_queue')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"❌ Failed to fetch notifications for user {user_id}: {e}")
        return []


def get_announcement_details(corp_ids: List[str]) -> List[Dict]:
    """Fetch full announcement details from corporatefilings"""
    try:
        response = supabase.table('corporatefilings')\
            .select('*')\
            .in_('corp_id', corp_ids)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"❌ Failed to fetch announcement details: {e}")
        return []


def get_user_info(user_id: str) -> Optional[Dict]:
    """Get user's email and other info"""
    try:
        response = supabase.table('UserData')\
            .select('emailID, Phone_Number, AccountType')\
            .eq('UserID', user_id)\
            .single()\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"❌ Failed to fetch info for user {user_id}: {e}")
        return None


def check_user_preferences(user_id: str, announcement_count: int) -> tuple[bool, str]:
    """
    Check if user wants to receive email based on preferences
    Returns: (should_send: bool, reason: str)
    """
    try:
        response = supabase.table('user_notification_preferences')\
            .select('*')\
            .eq('user_id', user_id)\
            .single()\
            .execute()
        
        if response.data:
            prefs = response.data
            
            # Check if email is enabled
            if not prefs.get('email_enabled', True):
                return False, "User has disabled email notifications"
            
            # Check minimum announcement threshold
            min_announcements = prefs.get('minimum_announcements', 1)
            if announcement_count < min_announcements:
                return False, f"Only {announcement_count} announcements, user minimum is {min_announcements}"
            
            return True, "Preferences allow email"
        else:
            # No preferences = default behavior (send email)
            return True, "No preferences set, using defaults"
    except Exception as e:
        # If preferences table doesn't exist or query fails, default to sending
        logger.warning(f"⚠️  Failed to fetch preferences for user {user_id}, defaulting to send: {e}")
        return True, "Preference check failed, defaulting to send"


def group_announcements_by_company(announcements: List[Dict]) -> Dict[str, Dict]:
    """Group announcements by company for better email organization"""
    grouped = {}
    
    for announcement in announcements:
        # Use ISIN as primary key, fallback to symbol or company name
        company_key = announcement.get('isin') or announcement.get('symbol') or announcement.get('companyname', 'Unknown')
        
        if company_key not in grouped:
            grouped[company_key] = {
                'companyname': announcement.get('companyname', 'Unknown Company'),
                'symbol': announcement.get('symbol', ''),
                'isin': announcement.get('isin', ''),
                'announcements': []
            }
        
        # Build announcement URL (update with your actual frontend URL)
        app_base_url = os.getenv('APP_BASE_URL', 'https://marketwire.ai')
        ai_url = f"{app_base_url}/announcement/{announcement.get('corp_id')}"
        
        grouped[company_key]['announcements'].append({
            'summary': announcement.get('summary', 'No summary available'),
            'ai_summary': announcement.get('ai_summary', ''),
            'category': announcement.get('category', ''),
            'date': announcement.get('date', ''),
            'url': announcement.get('fileurl', '#'),
            'ai_url': ai_url,
            'corp_id': announcement.get('corp_id')
        })
    
    return grouped


def generate_combined_digest_html(grouped_companies: Dict[str, Dict], user_email: str, total_count: int) -> str:
    """Generate a single email with all companies (alternative to multiple emails)"""
    from datetime import date as date_module
    
    # Build company sections
    company_sections = ""
    for company_key, company_data in grouped_companies.items():
        company_name = company_data['companyname']
        symbol = company_data['symbol']
        announcement_count = len(company_data['announcements'])
        
        # Generate announcement cards for this company
        announcement_cards = ""
        for ann in company_data['announcements']:
            announcement_cards += f"""
            <div style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 16px; margin-bottom: 12px; border-radius: 4px;">
                <div style="font-size: 13px; color: #64748b; margin-bottom: 4px;">
                    <strong>{ann['category']}</strong> • {ann['date']}
                </div>
                <div style="color: #1e293b; margin-bottom: 8px; line-height: 1.5;">
                    {ann['summary'][:300]}{'...' if len(ann['summary']) > 300 else ''}
                </div>
                <div>
                    <a href="{ann['ai_url']}" style="color: #3b82f6; text-decoration: none; font-size: 13px; margin-right: 16px;">📊 View Details</a>
                    <a href="{ann['url']}" style="color: #64748b; text-decoration: none; font-size: 13px;">📄 Original Document</a>
                </div>
            </div>
            """
        
        company_sections += f"""
        <div style="margin-bottom: 32px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; background: white;">
            <div style="margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #f1f5f9;">
                <h2 style="margin: 0 0 8px 0; color: #1e293b; font-size: 20px;">{company_name}</h2>
                <div style="display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; padding: 4px 12px; border-radius: 15px; font-size: 12px; font-weight: 600;">
                    {symbol or 'N/A'}
                </div>
                <span style="color: #64748b; font-size: 13px; margin-left: 8px;">{announcement_count} announcement{'s' if announcement_count > 1 else ''}</span>
            </div>
            {announcement_cards}
        </div>
        """
    
    # Full email template
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Daily Watchlist Digest</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 16px; background-color: #f8fafc;">
        <div style="max-width: 700px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); padding: 32px 24px; text-align: center; color: white;">
                <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 700;">📊 Your Daily Watchlist Digest</h1>
                <p style="margin: 0; font-size: 14px; opacity: 0.9;">{date_module.today().strftime('%B %d, %Y')}</p>
            </div>
            
            <!-- Summary -->
            <div style="padding: 24px; background: #eff6ff; border-bottom: 1px solid #e2e8f0;">
                <p style="margin: 0; color: #1e293b; font-size: 15px;">
                    You have <strong>{total_count} new announcement{'s' if total_count > 1 else ''}</strong> from <strong>{len(grouped_companies)} compan{'ies' if len(grouped_companies) > 1 else 'y'}</strong> in your watchlist.
                </p>
            </div>
            
            <!-- Company Sections -->
            <div style="padding: 24px;">
                {company_sections}
            </div>
            
            <!-- Footer -->
            <div style="padding: 24px; background: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 13px;">
                <p style="margin: 0 0 8px 0;">You're receiving this because companies in your watchlist made announcements today.</p>
                <p style="margin: 0;">
                    <a href="#" style="color: #3b82f6; text-decoration: none;">Manage Watchlist</a> • 
                    <a href="#" style="color: #3b82f6; text-decoration: none;">Notification Settings</a> • 
                    <a href="#" style="color: #64748b; text-decoration: none;">Unsubscribe</a>
                </p>
                <p style="margin: 16px 0 0 0; color: #94a3b8; font-size: 12px;">
                    © {date_module.today().year} Backfin. All rights reserved.
                </p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return html


def send_digest_to_user(user_id: str, target_date: date, dry_run: bool = False) -> bool:
    """
    Send daily digest email to a single user
    
    Args:
        user_id: User ID to send digest to
        target_date: Date of notifications to process
        dry_run: If True, don't actually send email
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get user info
        user_info = get_user_info(user_id)
        if not user_info:
            logger.warning(f"⚠️  No user info found for {user_id}")
            return False
        
        email = user_info.get('emailID')
        if not email:
            logger.warning(f"⚠️  No email found for user {user_id}")
            return False
        
        # Get pending notifications
        notifications = get_user_notifications(user_id, target_date)
        if not notifications:
            logger.info(f"ℹ️  No notifications for user {user_id}")
            return True  # Not an error, just nothing to send
        
        # Check user preferences
        should_send, reason = check_user_preferences(user_id, len(notifications))
        if not should_send:
            logger.info(f"⏭️  Skipping user {user_id}: {reason}")
            mark_notifications_processed(user_id, target_date, 'skipped')
            log_digest_attempt(user_id, email, target_date, 0, 0, [], 'skipped', reason)
            return True  # Not a failure
        
        # Get full announcement details
        corp_ids = [n['corp_id'] for n in notifications]
        announcements = get_announcement_details(corp_ids)
        
        if not announcements:
            logger.warning(f"⚠️  No announcement details found for user {user_id}")
            return False
        
        # Group by company
        grouped = group_announcements_by_company(announcements)
        company_count = len(grouped)
        announcement_count = len(announcements)
        
        logger.info(f"📧 Preparing digest for {email}: {announcement_count} announcements from {company_count} companies")
        
        # Generate combined digest email
        html_content = generate_combined_digest_html(grouped, email, announcement_count)
        subject = f"📊 Daily Watchlist Digest: {announcement_count} new announcement{'s' if announcement_count > 1 else ''}"
        
        # Send email (unless dry run)
        if dry_run:
            logger.info(f"🧪 DRY RUN: Would send email to {email}")
            logger.info(f"   Subject: {subject}")
            logger.info(f"   Companies: {', '.join([c['companyname'] for c in grouped.values()])}")
            return True
        
        # Actually send the email
        import resend
        resend.api_key = RESEND_API_KEY
        
        try:
            params = {
                "from": "Marketwire Alerts <notifications@anshulkr.com>",  # Update with your verified domain
                "to": [email],
                "subject": subject,
                "html": html_content,
            }
            
            result = resend.Emails.send(params)
            message_id = result.get('id')
            
            logger.info(f"✅ Email sent to {email}: {message_id}")
            
            # Mark notifications as processed
            mark_notifications_processed(user_id, target_date, 'sent', corp_ids)
            
            # Log successful send
            log_digest_attempt(user_id, email, target_date, announcement_count, company_count, corp_ids, 'sent', None, message_id)
            
            return True
            
        except Exception as email_error:
            logger.error(f"❌ Failed to send email to {email}: {email_error}")
            log_digest_attempt(user_id, email, target_date, announcement_count, company_count, corp_ids, 'failed', str(email_error))
            return False
        
    except Exception as e:
        logger.error(f"❌ Error processing digest for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        return False


def mark_notifications_processed(user_id: str, target_date: date, status: str, corp_ids: List[str] = None):
    """Mark notifications as processed"""
    try:
        update_query = supabase.table('user_notification_queue')\
            .update({
                'is_processed': True,
                'processed_at': datetime.now().isoformat()
            })\
            .eq('user_id', user_id)\
            .eq('notification_date', target_date.isoformat())
        
        if corp_ids:
            update_query = update_query.in_('corp_id', corp_ids)
        
        update_query.execute()
        logger.info(f"✓ Marked {len(corp_ids) if corp_ids else 'all'} notifications processed for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to mark notifications processed: {e}")


def log_digest_attempt(user_id: str, email: str, digest_date: date, 
                       announcement_count: int, company_count: int, 
                       corp_ids: List[str], status: str, error_msg: str = None,
                       message_id: str = None):
    """Log digest email attempt to audit table"""
    try:
        supabase.table('user_email_digest_log').insert({
            'user_id': user_id,
            'email_address': email,
            'digest_date': digest_date.isoformat(),
            'announcement_count': announcement_count,
            'company_count': company_count,
            'status': status,
            'error_message': error_msg,
            'email_provider_id': message_id,
            'corp_ids': corp_ids,
            'sent_at': datetime.now().isoformat() if status == 'sent' else None
        }).execute()
    except Exception as e:
        logger.error(f"❌ Failed to log digest attempt: {e}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Send daily digest emails to users')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--test-user', type=str, help='Send only to this user ID (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate sending without actually sending emails')
    
    args = parser.parse_args()
    
    # Parse target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
            return 1
    else:
        target_date = date.today()
    
    logger.info(f"{'🧪 DRY RUN: ' if args.dry_run else ''}Starting daily digest processing for {target_date}")
    
    # Get users to process
    if args.test_user:
        user_ids = [args.test_user]
        logger.info(f"🧪 TEST MODE: Processing only user {args.test_user}")
    else:
        user_ids = get_users_with_pending_notifications(target_date)
    
    if not user_ids:
        logger.info("ℹ️  No users with pending notifications")
        return 0
    
    # Process each user
    success_count = 0
    failure_count = 0
    skipped_count = 0
    
    for i, user_id in enumerate(user_ids, 1):
        logger.info(f"📤 Processing user {i}/{len(user_ids)}: {user_id}")
        
        try:
            result = send_digest_to_user(user_id, target_date, dry_run=args.dry_run)
            if result:
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            logger.error(f"❌ Unhandled error for user {user_id}: {e}")
            logger.error(traceback.format_exc())
            failure_count += 1
    
    # Summary
    logger.info("=" * 60)
    logger.info(f"{'🧪 DRY RUN ' if args.dry_run else ''}DIGEST PROCESSING COMPLETE")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {failure_count}")
    logger.info(f"⏭️  Skipped: {skipped_count}")
    logger.info(f"📊 Total: {len(user_ids)}")
    logger.info("=" * 60)
    
    return 0 if failure_count == 0 else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
