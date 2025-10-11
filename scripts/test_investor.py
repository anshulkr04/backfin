from supabase import create_client, Client
from typing import List, Dict
import os
from dotenv import load_dotenv
import json

load_dotenv()
# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL2")  # Replace with your
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_corporate_filings_with_investors(
    date_from=None,
    date_to=None,
    category=None,
    isin=None,
    symbol=None,
    companyname=None,
    sentiment=None,
    verified_investors_only=False,
    investor_type=None
):
    """
    Query corporate filings with filters and join with investor data.
    Uses LEFT JOIN to include all filings, even those without investors.
    
    Args:
        date_from (str): Start date filter (YYYY-MM-DD format)
        date_to (str): End date filter (YYYY-MM-DD format)
        category (str): Category filter
        isin (str): ISIN filter
        symbol (str): Symbol filter
        companyname (str): Company name filter (partial match)
        sentiment (str): Sentiment filter
        verified_investors_only (bool): If True, only return verified investors. Default False (includes all)
        investor_type (str): Filter by investor type ('individual' or 'institution')
    
    Returns:
        dict: Query result with combined corporate filings and investor data
    """
    
    try:
        # Build the base query for corporate filings with LEFT JOIN
        query = supabase.table("corporatefilings2").select(
            """
            corp_id,
            securityid,
            summary,
            fileurl,
            date,
            ai_summary,
            category,
            isin,
            companyname,
            symbol,
            headline,
            sentiment,
            investorCorp!left(
                id,
                investor_id,
                investor_name,
                aliasBool,
                aliasName,
                verified,
                type,
                alias_id
            )
            """
        )
        
        # Apply filters to corporate filings
        if date_from:
            query = query.gte("date", date_from)
        
        if date_to:
            query = query.lte("date", date_to)
        
        if category:
            query = query.eq("category", category)
        
        if isin:
            query = query.eq("isin", isin)
        
        if symbol:
            query = query.eq("symbol", symbol)
        
        if companyname:
            query = query.ilike("companyname", f"%{companyname}%")
        
        if sentiment:
            query = query.eq("sentiment", sentiment)
        
        # # Apply filters to investor data (only when investors exist)
        # if verified_investors_only:
        #     query = query.eq("investorCorp.verified", "True")
        
        # if investor_type:
        #     query = query.eq("investorCorp.type", investor_type)
        
        # Execute the query
        response = query.execute()
        
        if response.data:
            print(f"Found {len(response.data)} corporate filings (including those without investors)")
            
            # Count how many have investors vs no investors
            with_investors = len([r for r in response.data if r.get('investorCorp') and len(r['investorCorp']) > 0])
            without_investors = len([r for r in response.data if not r.get('investorCorp') or len(r['investorCorp']) == 0])
            
            print(f"  - {with_investors} filings with investors")
            print(f"  - {without_investors} filings without investors")
            
            return {
                "success": True,
                "data": response.data,
                "count": len(response.data),
                "with_investors": with_investors,
                "without_investors": without_investors
            }
        else:
            print("No data found matching the criteria")
            return {
                "success": True,
                "data": [],
                "count": 0,
                "with_investors": 0,
                "without_investors": 0
            }
            
    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "count": 0
        }



print("=== Method 1: Using LEFT JOIN ===")
result1 = get_corporate_filings_with_investors(date_from="2025-08-09")
print(json.dumps(result1, indent=2))