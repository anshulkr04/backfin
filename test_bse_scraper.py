"""Test BSE insider trading scraper specifically"""
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.exchange_data.insider_trading.insider_trading_detector import BSEInsiderScraper

def test_bse_scraper():
    """Test BSE scraper and verify sec_code handling"""
    print("=" * 80)
    print("TESTING BSE INSIDER TRADING SCRAPER")
    print("=" * 80)
    
    # Use today's date
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = end_date  # Just today
    
    print(f"\nDate range: {start_date} to {end_date}")
    
    # Initialize scraper
    scraper = BSEInsiderScraper()
    
    try:
        print("\nScraping BSE data...")
        df = scraper.scrape_data(start_date, end_date)
        
        if df.empty:
            print("\n⚠️  No data returned from BSE")
            return
        
        print(f"\n✅ Retrieved {len(df)} records from BSE")
        
        # Check sec_code field
        print("\n" + "=" * 80)
        print("SEC_CODE VERIFICATION")
        print("=" * 80)
        
        if 'sec_code' in df.columns:
            print(f"\nTotal records: {len(df)}")
            print(f"Non-null sec_code: {df['sec_code'].notna().sum()}")
            print(f"Null sec_code: {df['sec_code'].isna().sum()}")
            
            # Sample sec_code values
            sample = df[df['sec_code'].notna()].head(10)
            print("\nSample sec_code values:")
            for idx, row in sample.iterrows():
                sec_code = row.get('sec_code')
                sec_name = row.get('sec_name', 'N/A')
                print(f"  {sec_code} ({type(sec_code).__name__}) - {sec_name}")
            
            # Check for decimal points in sec_code
            sec_codes_with_decimals = df[df['sec_code'].notna()]['sec_code'].apply(
                lambda x: '.' in str(x) if x is not None else False
            ).sum()
            print(f"\nSec codes with decimal points: {sec_codes_with_decimals}")
        else:
            print("\n❌ sec_code column not found!")
        
        # Check other key fields
        print("\n" + "=" * 80)
        print("OTHER FIELDS VERIFICATION")
        print("=" * 80)
        
        key_fields = ['sec_name', 'person_name', 'trans_sec_num', 'trans_value', 'exchange', 'symbol']
        for field in key_fields:
            if field in df.columns:
                non_null = df[field].notna().sum()
                pct = (non_null / len(df) * 100) if len(df) > 0 else 0
                print(f"{field:20s}: {non_null:4d}/{len(df):4d} ({pct:6.2f}% non-null)")
            else:
                print(f"{field:20s}: ❌ Column not found")
        
        # Show sample record
        print("\n" + "=" * 80)
        print("SAMPLE RECORD")
        print("=" * 80)
        if len(df) > 0:
            sample_record = df.iloc[0].to_dict()
            for key, value in sample_record.items():
                print(f"{key:20s}: {value} ({type(value).__name__})")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bse_scraper()
