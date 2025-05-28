import resend
import os
from dotenv import load_dotenv
import datetime
from typing import List, Dict, Any, Optional

class AnnouncementMailer:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the mailer with optional API key"""
        # Use provided API key or try to load from environment
        if api_key:
            self.api_key = api_key
            resend.api_key = api_key
        else:
            load_dotenv()  # Load environment variables
            self.api_key = os.getenv("RESEND_API")
            if self.api_key:
                resend.api_key = self.api_key

    def get_headline(self, announcement: Dict[str, Any]) -> str:
        """Extract headline from the announcement summary or use full summary"""
        # If summary exists, use it directly
        if announcement.get('summary'):
            return announcement['summary']
        
        return ''

    def get_category(self, announcement: Dict[str, Any]) -> str:
        """Get the category from announcement"""
        return announcement.get('category', '')

    def get_sentiment(self, announcement: Dict[str, Any]) -> str:
        """Determine sentiment based on content analysis and existing sentiment"""
        # Start with existing sentiment or default to "Neutral"
        sentiment = announcement.get('sentiment', "Neutral")
        
        # Check summary for sentiment keywords
        summary = announcement.get('summary', '') + ' ' + announcement.get('ai_summary', '')
        
        import re
        if re.search(r'increase|growth|higher|positive|improvement|grow|up|rise|benefit|profit|success', summary, re.IGNORECASE):
            sentiment = "Positive"
        elif re.search(r'decrease|decline|lower|negative|drop|down|fall|loss|concern|risk|adverse', summary, re.IGNORECASE):
            sentiment = "Negative"
        
        return sentiment

    def format_date(self, date_str: str) -> str:
        """Format date string to a more readable format"""
        try:
            if 'T' in date_str:
                # Parse date and time
                date_part = date_str.split('T')[0]
                time_part = date_str.split('T')[1].split('.')[0]
                # Format as YYYY-MM-DD HH:MM:SS
                return f"{date_part} {time_part}"
            else:
                return date_str
        except:
            # Return original if parsing fails
            return date_str

    def generate_email_template(self, announcement: Dict[str, Any]) -> str:
        """Generate HTML email template based on announcement data"""
        
        headline = self.get_headline(announcement)
        category = self.get_category(announcement)
        sentiment = self.get_sentiment(announcement)
        
        # Format date to show date and time
        date_str = self.format_date(announcement.get('date', ''))
        
        # Set the sentiment color based on sentiment value
        sentiment_color = "#10B981" if sentiment == "Positive" else "#F59E0B" if sentiment == "Neutral" else "#EF4444"
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Announcement: {announcement.get('companyname', '')}</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                    line-height: 1.4;
                    color: #333;
                    margin: 0;
                    padding: 16px;
                    background-color: #ffffff;
                    font-size: 14px;
                }}
                .email-container {{
                    border: 1px solid #eaeaea;
                    border-radius: 8px;
                    overflow: hidden;
                    padding: 24px;
                    width: 100%;
                    max-width: 800px;
                    margin: 0 auto;
                    box-sizing: border-box;
                }}
                .company-name {{
                    font-size: 24px;
                    font-weight: 700;
                    margin-bottom: 16px;
                    color: #111827;
                }}
                .ticker-badge {{
                    display: inline-block;
                    background-color: #f5f5f5;
                    padding: 8px 16px;
                    border-radius: 50px;
                    font-weight: 600;
                    color: #111827;
                    font-size: 15px;
                    margin-bottom: 24px;
                }}
                .headline {{
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 28px;
                    color: #111827;
                    line-height: 1.5;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-evenly;
                    margin-bottom: 28px;
                    width: 100%;
                }}
                .info-box {{
                    flex: 1;
                    padding: 12px 16px;
                    background-color: #f9fafb;
                    border: 1px solid #eaeaea;
                    border-radius: 6px;
                    min-width: 120px;
                    box-sizing: border-box;
                    margin: 0 12px;
                }}
                .info-label {{
                    font-size: 13px;
                    text-transform: uppercase;
                    color: #6B7280;
                    margin-bottom: 6px;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                }}
                .info-value {{
                    font-size: 15px;
                    color: #111827;
                    font-weight: 500;
                }}
                .sentiment-indicator {{
                    display: inline-block;
                    width: 9px;
                    height: 9px;
                    border-radius: 50%;
                    margin-right: 6px;
                    background-color: {sentiment_color};
                    vertical-align: middle;
                }}
                .divider {{
                    height: 1px;
                    background-color: #eaeaea;
                    margin: 0 0 28px 0;
                    width: 100%;
                }}
                .document-link {{
                    color: #2563EB;
                    text-decoration: none;
                    font-weight: 500;
                    font-size: 15px;
                }}
                .document-link:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="company-name">{announcement.get('companyname', '')}</div>
                
                <div>
                    <span class="ticker-badge">{announcement.get('symbol', '')}</span>
                </div>
                
                <div class="headline">{headline}</div>
                
                <div class="info-row">
                    <div class="info-box">
                        <div class="info-label">CATEGORY</div>
                        <div class="info-value">{category}</div>
                    </div>
                    
                    <div class="info-box">
                        <div class="info-label">DATE & TIME</div>
                        <div class="info-value">{date_str}</div>
                    </div>
                    
                    <div class="info-box">
                        <div class="info-label">SENTIMENT</div>
                        <div class="info-value">
                            <span class="sentiment-indicator"></span>
                            {sentiment}
                        </div>
                    </div>
                </div>
                
                <div class="divider"></div>
                
                <a href="{announcement.get('fileurl', '#')}" class="document-link">
                    View Original Document
                </a>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def send_mail(self, email_id: str, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """Send email to a single recipient"""
        # Check if API key is set
        if not self.api_key:
            raise ValueError("Resend API key is not configured")
        
        # Generate email HTML
        email_html = self.generate_email_template(announcement)
        
        # Set up email parameters
        params = {
            "from": "MarketWire <noreply@anshulkr.com>",
            "to": [email_id],
            "subject": "New Announcement Alert!!",
            "html": email_html
        }
        
        # Send email
        email = resend.Emails.send(params)
        return email

    def send_batch_mail(self, announcement: Dict[str, Any], email_ids: List[str]) -> List[Dict[str, Any]]:
        """Send batch emails to multiple recipients"""
        # Check if API key is set
        if not self.api_key:
            raise ValueError("Resend API key is not configured")
        
        # Generate email HTML only once
        email_html = self.generate_email_template(announcement)
        
        # Create a list of email parameters
        mail_list = []
        for email_id in email_ids:
            mail_list.append({
                "from": "MarketWire <noreply@anshulkr.com>",
                "to": [email_id],
                "subject": "New Announcement Alert!!",
                "html": email_html,
            })
        
        # Send batch emails
        emails = resend.Batch.send(mail_list)
        return emails


# Create convenience functions that can be imported directly
def send_batch_mail(announcement: Dict[str, Any], email_ids: List[str], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Function to send batch announcement emails
    
    Args:
        announcement: Dictionary containing announcement details
        email_ids: List of email addresses to send to
        api_key: Optional Resend API key (will use environment variable if not provided)
        
    Returns:
        List of response dictionaries from the email service
    """
    mailer = AnnouncementMailer(api_key)
    return mailer.send_batch_mail(announcement, email_ids)

def send_mail(email_id: str, announcement: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Function to send a single announcement email
    
    Args:
        email_id: Email address to send to
        announcement: Dictionary containing announcement details
        api_key: Optional Resend API key (will use environment variable if not provided)
        
    Returns:
        Response dictionary from the email service
    """
    mailer = AnnouncementMailer(api_key)
    return mailer.send_mail(email_id, announcement)

