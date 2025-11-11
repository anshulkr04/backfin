import resend
import os
from dotenv import load_dotenv
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

    def generate_announcement_cards(self, announcements: List[Dict[str, Any]]) -> str:
        """Generate HTML cards for individual announcements"""
        cards_html = ""
        
        for announcement in announcements:
            summary = announcement.get('summary', 'No summary available')
            ai_url = announcement.get('ai_url', '#')
            original_url = announcement.get('url', '#')
            
            card_html = f"""
            <a href="{ai_url}" target="_blank" class="announcement-card-link">
                <div class="announcement-card">
                    <div class="announcement-summary">{summary}</div>
                    <div class="announcement-actions">
                        <a href="{original_url}" class="original-link" target="_blank" onclick="event.stopPropagation(); event.preventDefault(); window.open('{original_url}', '_blank');">📄 Original Document</a>
                    </div>
                </div>
            </a>
            """
            cards_html += card_html
            
        return cards_html

    def generate_email_template(self, company_data: Dict[str, Any]) -> str:
        """Generate HTML email template for grouped announcements"""
        
        company_name = company_data.get('companyname', 'Unknown Company')
        symbol = company_data.get('symbol', '')
        announcements = company_data.get('announcements', [])
        
        announcement_cards = self.generate_announcement_cards(announcements)
        announcement_count = len(announcements)
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Announcements: {company_name}</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                    line-height: 1.5;
                    color: #333;
                    margin: 0;
                    padding: 16px;
                    background-color: #f8fafc;
                    font-size: 14px;
                }}
                .email-container {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    overflow: hidden;
                    padding: 32px;
                    width: 100%;
                    max-width: 700px;
                    margin: 0 auto;
                    box-sizing: border-box;
                    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    margin-bottom: 32px;
                    text-align: center;
                    border-bottom: 2px solid #f1f5f9;
                    padding-bottom: 24px;
                }}
                .company-name {{
                    font-size: 28px;
                    font-weight: 700;
                    margin-bottom: 8px;
                    color: #1e293b;
                }}
                .ticker-badge {{
                    display: inline-block;
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    color: white;
                    padding: 8px 20px;
                    border-radius: 25px;
                    font-weight: 600;
                    font-size: 14px;
                    margin-bottom: 16px;
                    text-align: center;
                    min-width: 60px;
                }}
                .announcement-count {{
                    font-size: 16px;
                    color: #64748b;
                    font-weight: 500;
                }}
                .announcements-section {{
                    margin-bottom: 24px;
                }}
                .section-title {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #1e293b;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                }}
                .section-title::before {{
                    content: '';
                    width: 4px;
                    height: 20px;
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    border-radius: 2px;
                    margin-right: 12px;
                }}
                .announcement-card-link {{
                    text-decoration: none;
                    color: inherit;
                    display: block;
                    margin-bottom: 16px;
                }}
                .announcement-card-link:last-child {{
                    margin-bottom: 0;
                }}
                .announcement-card {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
                }}
                .announcement-card-link:hover .announcement-card {{
                    border-color: #3b82f6;
                    box-shadow: 0 4px 12px 0 rgba(59, 130, 246, 0.15);
                    transform: translateY(-2px);
                }}
                .announcement-summary {{
                    font-size: 15px;
                    color: #334155;
                    margin-bottom: 16px;
                    line-height: 1.6;
                    font-weight: 600;
                }}
                .announcement-actions {{
                    display: flex;
                    align-items: center;
                    font-size: 13px;
                }}
                .original-link {{
                    color: #3b82f6;
                    text-decoration: none;
                    font-weight: 500;
                    transition: color 0.2s ease;
                }}
                .original-link:hover {{
                    color: #1d4ed8;
                    text-decoration: underline;
                }}
                .footer {{
                    margin-top: 32px;
                    padding-top: 24px;
                    border-top: 1px solid #e2e8f0;
                    text-align: center;
                    color: #64748b;
                    font-size: 12px;
                }}
                .footer-note {{
                    margin-bottom: 8px;
                }}
                
                /* Mobile responsiveness */
                @media (max-width: 600px) {{
                    .email-container {{
                        padding: 20px;
                        margin: 8px;
                    }}
                    .company-name {{
                        font-size: 24px;
                    }}
                    .announcement-card {{
                        padding: 16px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="company-name">{company_name}</div>
                    <div class="ticker-badge">{symbol}</div>
                    <div class="announcement-count">{announcement_count} New Announcement{'s' if announcement_count != 1 else ''}</div>
                </div>
                
                <div class="announcements-section">
                    <div class="section-title">Latest Announcements</div>
                    {announcement_cards}
                </div>
                
                <div class="footer">
                    <div class="footer-note">Click on any announcement card to view AI analysis</div>
                    <div>Financial Updates - Stay informed with the latest announcements</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def send_mail(self, email_id: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send email for a company's grouped announcements"""
        # Check if API key is set
        if not self.api_key:
            raise ValueError("Resend API key is not configured")
        
        # Generate email HTML
        email_html = self.generate_email_template(company_data)
        
        company_name = company_data.get('companyname', 'Unknown Company')
        announcement_count = len(company_data.get('announcements', []))
        
        # Set up email parameters
        params = {
            "from": "Announcements <noreply@anshulkr.com>",
            "to": [email_id],
            "subject": f"{announcement_count} new announcement{'s' if announcement_count != 1 else ''} from {company_name}",
            "html": email_html
        }
        
        # Send email
        email = resend.Emails.send(params)
        return email

    def generate_all_companies_template(self, companies_data: List[Dict[str, Any]]) -> str:
        """Generate HTML email template for all companies in one email"""
        
        total_announcements = sum(len(company.get('announcements', [])) for company in companies_data)
        company_count = len(companies_data)
        
        companies_html = ""
        
        for company_data in companies_data:
            company_name = company_data.get('companyname', 'Unknown Company')
            symbol = company_data.get('symbol', '')
            announcements = company_data.get('announcements', [])
            
            announcement_cards = self.generate_announcement_cards(announcements)
            
            company_section = f"""
            <div class="company-section">
                <div class="company-header">
                    <div class="company-title">
                        <span class="company-name-text">{company_name}</span>
                        <span class="company-ticker">{symbol}</span>
                    </div>
                    <div class="announcement-count-badge">{len(announcements)} announcement{'s' if len(announcements) != 1 else ''}</div>
                </div>
                <div class="company-announcements">
                    {announcement_cards}
                </div>
            </div>
            """
            companies_html += company_section
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Market Announcements Update</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                    line-height: 1.5;
                    color: #333;
                    margin: 0;
                    padding: 16px;
                    background-color: #f8fafc;
                    font-size: 14px;
                }}
                .email-container {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    overflow: hidden;
                    padding: 32px;
                    width: 100%;
                    max-width: 800px;
                    margin: 0 auto;
                    box-sizing: border-box;
                    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
                }}
                .main-header {{
                    margin-bottom: 32px;
                    text-align: center;
                    border-bottom: 2px solid #f1f5f9;
                    padding-bottom: 24px;
                }}
                .main-title {{
                    font-size: 32px;
                    font-weight: 700;
                    margin-bottom: 12px;
                    color: #1e293b;
                }}
                .main-summary {{
                    font-size: 16px;
                    color: #64748b;
                    font-weight: 500;
                }}
                .company-section {{
                    margin-bottom: 40px;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    overflow: hidden;
                    background-color: #fafbfc;
                }}
                .company-section:last-child {{
                    margin-bottom: 0;
                }}
                .company-header {{
                    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                    padding: 20px 24px;
                    border-bottom: 1px solid #e2e8f0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .company-title {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }}
                .company-name-text {{
                    font-size: 20px;
                    font-weight: 600;
                    color: #1e293b;
                }}
                .company-ticker {{
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-weight: 600;
                    font-size: 12px;
                    text-align: center;
                    display: inline-block;
                    min-width: 60px;
                }}
                .announcement-count-badge {{
                    background-color: #f1f5f9;
                    color: #475569;
                    padding: 6px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 500;
                    border: 1px solid #e2e8f0;
                }}
                .company-announcements {{
                    padding: 24px;
                }}
                .announcement-card-link {{
                    text-decoration: none;
                    color: inherit;
                    display: block;
                    margin-bottom: 16px;
                }}
                .announcement-card-link:last-child {{
                    margin-bottom: 0;
                }}
                .announcement-card {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
                }}
                .announcement-card-link:hover .announcement-card {{
                    border-color: #3b82f6;
                    box-shadow: 0 4px 12px 0 rgba(59, 130, 246, 0.15);
                    transform: translateY(-2px);
                }}
                .announcement-summary {{
                    font-size: 15px;
                    color: #334155;
                    margin-bottom: 16px;
                    line-height: 1.6;
                    font-weight: 600;
                }}
                .announcement-actions {{
                    display: flex;
                    align-items: center;
                    font-size: 13px;
                }}
                .original-link {{
                    color: #3b82f6;
                    text-decoration: none;
                    font-weight: 500;
                    transition: color 0.2s ease;
                }}
                .original-link:hover {{
                    color: #1d4ed8;
                    text-decoration: underline;
                }}
                .footer {{
                    margin-top: 32px;
                    padding-top: 24px;
                    border-top: 1px solid #e2e8f0;
                    text-align: center;
                    color: #64748b;
                    font-size: 12px;
                }}
                .footer-note {{
                    margin-bottom: 8px;
                }}
                
                /* Mobile responsiveness */
                @media (max-width: 600px) {{
                    .email-container {{
                        padding: 20px;
                        margin: 8px;
                    }}
                    .main-title {{
                        font-size: 28px;
                    }}
                    .company-header {{
                        flex-direction: column;
                        gap: 12px;
                        align-items: flex-start;
                    }}
                    .company-title {{
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 8px;
                    }}
                    .announcement-card {{
                        padding: 16px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="main-header">
                    <div class="main-title">Company Announcements</div>
                    <div class="main-summary">{total_announcements} new announcements from {company_count} companies</div>
                </div>
                
                {companies_html}
                
                <div class="footer">
                    <div class="footer-note">Click on any announcement card to view detailed AI analysis</div>
                    <div>Financial Updates - Your comprehensive market intelligence platform</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def send_combined_mail(self, email_id: str, companies_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send all companies' announcements in a single email"""
        # Check if API key is set
        if not self.api_key:
            raise ValueError("Resend API key is not configured")
        
        if not companies_data:
            raise ValueError("No company data provided")
        
        # Generate email HTML
        email_html = self.generate_all_companies_template(companies_data)
        
        total_announcements = sum(len(company.get('announcements', [])) for company in companies_data)
        company_count = len(companies_data)
        
        # Set up email parameters
        params = {
            "from": "Announcements <noreply@anshulkr.com>",
            "to": [email_id],
            "subject": f"{total_announcements} new announcements from {company_count} companies",
            "html": email_html
        }
        
        # Send email
        email = resend.Emails.send(params)
        return email

    def send_bulk_mail(self, email_id: str, companies_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Send separate emails for each company's announcements"""
        results = []
        
        for company_data in companies_data:
            try:
                result = self.send_mail(email_id, company_data)
                results.append({
                    'company': company_data.get('companyname', 'Unknown'),
                    'status': 'success',
                    'result': result
                })
            except Exception as e:
                results.append({
                    'company': company_data.get('companyname', 'Unknown'),
                    'status': 'error',
                    'error': str(e)
                })
        
        return results

def send_company_announcements(email_id: str, company_data: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Function to send announcements for a single company
    
    Args:
        email_id: Email address to send to
        company_data: Dictionary containing company and its announcements
        api_key: Optional Resend API key (will use environment variable if not provided)
        
    Returns:
        Response dictionary from the email service
    """
    mailer = AnnouncementMailer(api_key)
    return mailer.send_mail(email_id, company_data)

def send_all_company_announcements(email_id: str, companies_data: List[Dict[str, Any]], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Function to send announcements for multiple companies (separate email per company)
    
    Args:
        email_id: Email address to send to
        companies_data: List of dictionaries, each containing company and its announcements
        api_key: Optional Resend API key (will use environment variable if not provided)
        
    Returns:
        List of response dictionaries from the email service
    """
    mailer = AnnouncementMailer(api_key)
    return mailer.send_bulk_mail(email_id, companies_data)

def send_combined_announcements(email_id: str, companies_data: List[Dict[str, Any]], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Function to send all companies' announcements in a single email
    
    Args:
        email_id: Email address to send to
        companies_data: List of dictionaries, each containing company and its announcements
        api_key: Optional Resend API key (will use environment variable if not provided)
        
    Returns:
        Response dictionary from the email service
    """
    mailer = AnnouncementMailer(api_key)
    return mailer.send_combined_mail(email_id, companies_data)

# Example usage:
# Single company announcements
# send_company_announcements("user@example.com", company_data)

# Multiple companies (separate email per company)
# send_all_company_announcements("user@example.com", companies_data_list)

# All companies in one email
# send_combined_announcements("user@example.com", companies_data_list)