from mailer import AnnouncementMailer
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import json

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL2")
supabase_key = os.getenv("SUPABASE_KEY2")
supabase: Client = create_client(supabase_url, supabase_key)

mailer = AnnouncementMailer()

announcements = []

def process_announcements(user_id):
    response = supabase.table('UserData').select('emailData').eq('UserID', user_id).execute()

    if not response.data:
        return []
    
    corp_ids = response.data[0]['emailData']

    for corp_id in corp_ids:
        response = supabase.table('corporatefilings').select('*').eq('corp_id', corp_id).execute()
        if response.data:
            announcements.extend(response.data)
    
    processed = []
    for announcement in announcements:
        corp_id = announcement.get('corp_id', '')
        processed_announcement = { 
            'isin': announcement.get('isin'),
            'symbol': announcement.get('symbol'),
            'companyname': announcement.get('companyname'),
            'summary': announcement.get('summary', ''),
            'corp_id': corp_id,
            'ai_url': f"https://finfron-main-2.vercel.app/?corpid={corp_id}",
            'url': announcement.get('fileurl', ''),
        }
        processed.append(processed_announcement)
        
    # Group announcements by ISIN
    grouped_by_isin = {}
    for item in processed:
        isin = item['isin']
        if isin not in grouped_by_isin:
            grouped_by_isin[isin] = {
                'isin': isin,
                'symbol': item['symbol'],
                'companyname': item['companyname'],
                'announcements': []
            }
        # Add this announcement to the group
        grouped_by_isin[isin]['announcements'].append({
            'summary': item['summary'],
            'corp_id': item['corp_id'],
            'ai_url': item['ai_url'],
            'url': item['url']
        })
    
    # Convert dictionary to list
    result = list(grouped_by_isin.values())
    return result

companies_data_list = process_announcements("5616f49c-64b8-42d6-a8a3-3797ae9ce89f")


c = AnnouncementMailer()
d = c.send_combined_mail("harsh@mailwave.io", companies_data_list)



