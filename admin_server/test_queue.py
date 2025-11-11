#!/usr/bin/env python3
"""
Test script to simulate the main Flask backend adding verification tasks to Redis queue.
This simulates what your main backend on the VM will do.
"""

import redis
import json
import uuid
from datetime import datetime
import time
import random

# Connect to local Redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Queue configuration (same as main Flask app)
ADMIN_STREAM = "admin:verification:stream"

def create_sample_announcement():
    """Create a sample announcement similar to what main backend generates"""
    companies = [
        {"name": "Reliance Industries", "symbol": "RELIANCE", "isin": "INE002A01018"},
        {"name": "TCS", "symbol": "TCS", "isin": "INE467B01029"},
        {"name": "HDFC Bank", "symbol": "HDFCBANK", "isin": "INE040A01034"},
        {"name": "Infosys", "symbol": "INFY", "isin": "INE009A01021"},
        {"name": "ICICI Bank", "symbol": "ICICIBANK", "isin": "INE090A01013"}
    ]
    
    categories = [
        "Board Meeting", 
        "Financial Results", 
        "Dividend Declaration", 
        "Stock Split", 
        "Rights Issue",
        "Merger & Acquisition",
        "Regulatory Compliance"
    ]
    
    company = random.choice(companies)
    category = random.choice(categories)
    corp_id = f"CORP_{random.randint(100000, 999999)}"
    
    # Sample announcement data (what gets broadcast via WebSocket)
    announcement = {
        "corp_id": corp_id,
        "title": f"{category} - {company['name']}",
        "category": category,
        "fileurl": f"https://example.com/files/{corp_id}.pdf",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ai_summary": f"AI Summary: {company['name']} has announced {category.lower()}. This announcement contains important information for investors and stakeholders regarding the company's operations and financial status.",
        "isin": company["isin"],
        "companyname": company["name"],
        "symbol": company["symbol"]
    }
    
    # Sample original data (raw scraping data)
    original_data = {
        "corp_id": corp_id,
        "title": announcement["title"],
        "category": category,
        "fileurl": announcement["fileurl"],
        "date": announcement["date"],
        "isin": company["isin"],
        "companyname": company["name"],
        "symbol": company["symbol"],
        "scrape_timestamp": datetime.now().isoformat(),
        "source": "BSE/NSE"
    }
    
    return announcement, original_data

def add_task_to_queue():
    """Add a verification task to Redis queue (simulates main Flask app)"""
    try:
        announcement, original_data = create_sample_announcement()
        
        # Create task data (same format as main Flask app)
        admin_task = {
            "id": str(uuid.uuid4()),
            "announcement": json.dumps(announcement),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "original_data": json.dumps(original_data),
            "ai_summary": announcement.get("ai_summary", "")
        }
        
        # Add to Redis Stream
        stream_id = redis_client.xadd(ADMIN_STREAM, admin_task)
        
        print(f"✅ Added task to queue:")
        print(f"   Stream ID: {stream_id}")
        print(f"   Company: {announcement['companyname']}")
        print(f"   Category: {announcement['category']}")
        print(f"   Corp ID: {announcement['corp_id']}")
        print()
        
        return stream_id
        
    except Exception as e:
        print(f"❌ Error adding task to queue: {e}")
        return None

def check_queue_status():
    """Check current queue status"""
    try:
        # Get stream info
        info = redis_client.xinfo_stream(ADMIN_STREAM)
        print(f"📊 Queue Status:")
        print(f"   Stream: {ADMIN_STREAM}")
        print(f"   Length: {info.get('length', 0)} tasks")
        print(f"   Last Entry: {info.get('last-generated-id', 'None')}")
        print()
        
        # Get recent messages
        messages = redis_client.xread({ADMIN_STREAM: '0'}, count=5)
        if messages:
            print("📝 Recent Tasks:")
            for stream_name, stream_messages in messages:
                for stream_id, fields in stream_messages:
                    announcement = json.loads(fields.get('announcement', '{}'))
                    print(f"   {stream_id}: {announcement.get('companyname', 'Unknown')} - {announcement.get('category', 'Unknown')}")
            print()
        else:
            print("📝 No tasks in queue")
            print()
            
    except redis.RedisError as e:
        if "no such key" in str(e).lower():
            print(f"📊 Queue Status: Empty (stream doesn't exist yet)")
            print()
        else:
            print(f"❌ Error checking queue: {e}")
            print()

def clear_queue():
    """Clear the queue (for testing)"""
    try:
        redis_client.delete(ADMIN_STREAM)
        print("🗑️ Queue cleared!")
        print()
    except Exception as e:
        print(f"❌ Error clearing queue: {e}")

def main():
    print("🧪 Redis Queue Test Script")
    print("=" * 50)
    print("Commands:")
    print("  1 - Add sample task to queue")
    print("  2 - Check queue status")
    print("  3 - Add 5 sample tasks")
    print("  4 - Clear queue")
    print("  5 - Auto-add tasks (every 10 seconds)")
    print("  q - Quit")
    print()
    
    # Initial status check
    check_queue_status()
    
    while True:
        try:
            choice = input("Enter command (1-5 or q): ").strip().lower()
            print()
            
            if choice == 'q':
                print("👋 Goodbye!")
                break
            elif choice == '1':
                add_task_to_queue()
            elif choice == '2':
                check_queue_status()
            elif choice == '3':
                print("Adding 5 sample tasks...")
                for i in range(5):
                    add_task_to_queue()
                    time.sleep(1)  # Small delay between tasks
            elif choice == '4':
                clear_queue()
            elif choice == '5':
                print("🔄 Auto-adding tasks every 10 seconds (Press Ctrl+C to stop)...")
                try:
                    while True:
                        add_task_to_queue()
                        time.sleep(10)
                except KeyboardInterrupt:
                    print("\n⏹️ Auto-add stopped")
                    print()
            else:
                print("❌ Invalid command")
                print()
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print()

if __name__ == "__main__":
    main()