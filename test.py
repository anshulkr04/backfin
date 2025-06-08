#!/usr/bin/env python3
"""
Test script for announcement notification system
Tests if corp_id is properly stored in user's emailData when an announcement 
matches their watchlist ISINs or categories.
"""

import requests
import json
import time
import uuid
import sys
from datetime import datetime
import traceback

# Configuration
BASE_URL = "https://fin.anshulkr.com/api"  # Change this to match your server configuration
TEST_EMAIL_PREFIX = f"test_announcement_{int(time.time())}"
TEST_PASSWORD = "Test@123"

# Mock test data
MOCK_ISINS = [
    "INE002A01018",  # Reliance Industries
    "INE009A01021",  # Infosys
    "INE467B01029",  # Tata Consultancy Services
    "INE040A01034",  # HDFC Bank
    "INE062A01020",  # Bharti Airtel
    "INE020B01018",  # ICICI Bank
    "INE481G01011",  # Nestle India
    "INE219A01013",  # Bajaj Auto
    "INE081A01012",  # Tata Steel
    "INE127A01011",  # BHEL
]

MOCK_CATEGORIES = [
    "Financial Results",
    "Dividend",
    "Board Meeting",
    "Mergers & Acquisitions",
    "Rights Issue"
]

# Store test user data
test_users = []
test_watchlists = []
test_announcements = []

class AnnouncementTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        # Disable SSL warnings for localhost testing
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False
        
    def check_server_health(self):
        """Check if the server is running and accessible"""
        try:
            print(f"\n[TEST] Checking server health at {self.base_url}")
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Server is healthy: {data.get('status', 'unknown')}")
                print(f"Supabase connected: {data.get('supabase_connected', 'unknown')}")
                return True
            else:
                print(f"⚠️  Server responded with status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Server health check failed: {e}")
            print(f"Make sure your server is running at {self.base_url}")
            return False
        
    def log_response(self, response, message):
        """Log response details"""
        try:
            print(f"\n{message}")
            print(f"Status Code: {response.status_code}")
            if response.headers.get('content-type', '').startswith('application/json'):
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                return data
            else:
                print(f"Response Text: {response.text[:500]}...")
                return {"text": response.text}
        except Exception as e:
            print(f"Error parsing response: {e}")
            print(f"Raw response: {response.text}")
            return None

    def create_test_user(self, user_number):
        """Create a test user"""
        email = f"{TEST_EMAIL_PREFIX}_user{user_number}@example.com"
        print(f"\n[TEST] Creating user {user_number}: {email}")
        
        response = self.session.post(
            f"{self.base_url}/register",
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "account_type": "free"
            }
        )
        
        data = self.log_response(response, f"User {user_number} Registration Response:")
        
        if response.status_code == 201 and data:
            user_info = {
                "user_number": user_number,
                "email": email,
                "user_id": data.get("user_id"),
                "token": data.get("token"),
                "watchlists": []
            }
            test_users.append(user_info)
            print(f"✅ User {user_number} created successfully. ID: {user_info['user_id']}")
            return user_info
        else:
            print(f"❌ User {user_number} creation failed")
            return None

    def create_watchlist_for_user(self, user_info, watchlist_name, isins, category=None):
        """Create a watchlist for a user and add ISINs"""
        print(f"\n[TEST] Creating watchlist '{watchlist_name}' for user {user_info['user_number']}")
        
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        
        # Create watchlist
        response = self.session.post(
            f"{self.base_url}/watchlist",
            headers=headers,
            json={
                "operation": "create",
                "watchlistName": watchlist_name
            }
        )
        
        data = self.log_response(response, f"Create Watchlist Response for User {user_info['user_number']}:")
        
        if response.status_code != 201 or not data or "watchlist" not in data:
            print(f"❌ Failed to create watchlist for user {user_info['user_number']}")
            return None
            
        watchlist_id = data["watchlist"]["_id"]
        
        # Add category if provided
        if category:
            print(f"Setting category: {category}")
            category_response = self.session.post(
                f"{self.base_url}/watchlist",
                headers=headers,
                json={
                    "operation": "add_isin",
                    "watchlist_id": watchlist_id,
                    "isin": None,
                    "category": category
                }
            )
            self.log_response(category_response, f"Set Category Response for User {user_info['user_number']}:")
        
        # Add ISINs
        added_isins = []
        for isin in isins:
            print(f"Adding ISIN: {isin}")
            isin_response = self.session.post(
                f"{self.base_url}/watchlist",
                headers=headers,
                json={
                    "operation": "add_isin",
                    "watchlist_id": watchlist_id,
                    "isin": isin
                }
            )
            
            isin_data = self.log_response(isin_response, f"Add ISIN {isin} Response:")
            
            if isin_response.status_code in [201, 200]:
                added_isins.append(isin)
                print(f"✅ ISIN {isin} added successfully")
            else:
                print(f"❌ Failed to add ISIN {isin}")
        
        watchlist_info = {
            "watchlist_id": watchlist_id,
            "name": watchlist_name,
            "isins": added_isins,
            "category": category,
            "user_id": user_info['user_id']
        }
        
        user_info['watchlists'].append(watchlist_info)
        test_watchlists.append(watchlist_info)
        
        print(f"✅ Watchlist '{watchlist_name}' created with {len(added_isins)} ISINs for user {user_info['user_number']}")
        
        # Verify the watchlist was created properly
        self.verify_watchlist_creation(user_info, watchlist_id, watchlist_name, added_isins, category)
        
        return watchlist_info
    
    def verify_watchlist_creation(self, user_info, watchlist_id, watchlist_name, expected_isins, expected_category):
        """Verify that the watchlist was created with correct data"""
        print(f"\n[VERIFY] Checking watchlist creation for user {user_info['user_number']}")
        
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        response = self.session.get(f"{self.base_url}/watchlist", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Failed to get watchlists for verification")
            return False
        
        data = response.json()
        watchlists = data.get('watchlists', [])
        
        # Find our watchlist
        target_watchlist = None
        for wl in watchlists:
            if wl.get('_id') == watchlist_id:
                target_watchlist = wl
                break
        
        if not target_watchlist:
            print(f"❌ Watchlist {watchlist_id} not found in user's watchlists")
            return False
        
        print(f"✅ Found watchlist: {target_watchlist}")
        
        # Verify ISINs
        actual_isins = target_watchlist.get('isin', [])
        missing_isins = set(expected_isins) - set(actual_isins)
        if missing_isins:
            print(f"⚠️  Missing ISINs in watchlist: {missing_isins}")
        
        # Verify category
        actual_category = target_watchlist.get('category')
        if actual_category != expected_category:
            print(f"⚠️  Category mismatch. Expected: {expected_category}, Got: {actual_category}")
        
        print(f"✅ Watchlist verification complete")
        return True

    def get_user_email_data(self, user_info):
        """Get user's current emailData"""
        print(f"\n[TEST] Getting emailData for user {user_info['user_number']}")
        
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        response = self.session.get(f"{self.base_url}/user", headers=headers)
        
        data = self.log_response(response, f"User Data Response for User {user_info['user_number']}:")
        
        if response.status_code == 200 and data:
            # Check both possible locations for emailData
            email_data = data.get('emailData', [])
            
            # If emailData is empty or None, try to check if it exists but is empty
            if not email_data:
                email_data = []
            
            print(f"Current emailData: {email_data}")
            print(f"EmailData type: {type(email_data)}")
            return email_data
        else:
            print(f"❌ Failed to get user data for user {user_info['user_number']}")
            return None

    def send_mock_announcement(self, isin=None, category=None, company_name="Mock Company", symbol="MOCK"):
        """Send a mock announcement"""
        corp_id = str(uuid.uuid4())  # Generate proper UUID string
        
        announcement_data = {
            "corp_id": corp_id,
            "companyname": company_name,
            "symbol": symbol,
            "summary": f"Mock announcement from {company_name} - Test notification system",
            "ai_summary": f"**Category:** {category or 'Test'}\n**Headline:** Mock Announcement\n\nThis is a test announcement to verify the notification system works correctly.",
            "date": datetime.now().isoformat(),
            "category": category,
            "isin": isin,
            "securityid": str(uuid.uuid4()),  # Also make this a proper UUID
            "fileurl": "https://example.com/test_announcement.pdf"
        }
        
        print(f"\n[TEST] Sending mock announcement:")
        print(f"Corp ID: {corp_id}")
        print(f"ISIN: {isin}")
        print(f"Category: {category}")
        print(f"Company: {company_name}")
        print(f"Full payload: {json.dumps(announcement_data, indent=2)}")
        
        try:
            response = self.session.post(
                f"{self.base_url}/insert_new_announcement",
                json=announcement_data,
                timeout=30
            )
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return None
        
        data = self.log_response(response, "Mock Announcement Response:")
        
        if response.status_code == 200:
            test_announcements.append({
                "corp_id": corp_id,
                "isin": isin,
                "category": category,
                "company_name": company_name,
                "announcement_data": announcement_data
            })
            print(f"✅ Mock announcement sent successfully. Corp ID: {corp_id}")
            return corp_id
        else:
            print(f"❌ Failed to send mock announcement")
            return None

    def verify_corp_id_in_email_data(self, user_info, expected_corp_id, should_exist=True):
        """Verify if corp_id exists in user's emailData"""
        print(f"\n[TEST] Verifying corp_id {expected_corp_id} in user {user_info['user_number']}'s emailData")
        
        # Wait a moment for the system to process
        print("Waiting 3 seconds for system to process...")
        time.sleep(3)
        
        email_data = self.get_user_email_data(user_info)
        
        if email_data is None:
            print(f"❌ Could not retrieve emailData for user {user_info['user_number']}")
            return False
        
        # Handle case where emailData might be a string instead of list
        if isinstance(email_data, str):
            try:
                email_data = json.loads(email_data)
            except:
                print(f"⚠️  emailData is a string but not valid JSON: {email_data}")
                email_data = []
        
        # Ensure emailData is a list
        if not isinstance(email_data, list):
            print(f"⚠️  emailData is not a list: {type(email_data)} - {email_data}")
            email_data = []
        
        corp_id_exists = expected_corp_id in email_data
        
        if should_exist:
            if corp_id_exists:
                print(f"✅ VERIFIED: Corp ID {expected_corp_id} found in user {user_info['user_number']}'s emailData")
                return True
            else:
                print(f"❌ VERIFICATION FAILED: Corp ID {expected_corp_id} NOT found in user {user_info['user_number']}'s emailData")
                print(f"Expected corp_id: {expected_corp_id}")
                print(f"Current emailData: {email_data}")
                print(f"EmailData length: {len(email_data)}")
                
                # Additional debugging - check if any corp_id matches partially
                for item in email_data:
                    print(f"  - Item in emailData: {item} (type: {type(item)})")
                
                return False
        else:
            if not corp_id_exists:
                print(f"✅ VERIFIED: Corp ID {expected_corp_id} correctly NOT in user {user_info['user_number']}'s emailData")
                return True
            else:
                print(f"❌ VERIFICATION FAILED: Corp ID {expected_corp_id} unexpectedly found in user {user_info['user_number']}'s emailData")
                return False

    def test_isin_matching(self):
        """Test ISIN-based announcement matching"""
        print("\n" + "="*60)
        print("TESTING ISIN-BASED ANNOUNCEMENT MATCHING")
        print("="*60)
        
        results = []
        
        # Test 1: User with matching ISIN should receive corp_id
        user1 = test_users[0] if test_users else None
        if not user1:
            print("❌ No test user available for ISIN matching test")
            return []
        
        # Get an ISIN from user1's watchlist
        test_isin = None
        if user1['watchlists']:
            test_isin = user1['watchlists'][0]['isins'][0] if user1['watchlists'][0]['isins'] else None
        
        if not test_isin:
            print("❌ No ISIN available in user1's watchlist for testing")
            return []
        
        print(f"\nTest 1: Sending announcement for ISIN {test_isin} (should match user {user1['user_number']})")
        corp_id1 = self.send_mock_announcement(
            isin=test_isin,
            company_name="Test Company Alpha",
            symbol="TCA"
        )
        
        if corp_id1:
            result1 = self.verify_corp_id_in_email_data(user1, corp_id1, should_exist=True)
            results.append(("ISIN Match - User Should Receive", result1))
        else:
            results.append(("ISIN Match - User Should Receive", False))
        
        # Test 2: User with non-matching ISIN should NOT receive corp_id
        non_matching_isin = "INE999Z99999"  # Fake ISIN not in any watchlist
        
        print(f"\nTest 2: Sending announcement for non-matching ISIN {non_matching_isin}")
        corp_id2 = self.send_mock_announcement(
            isin=non_matching_isin,
            company_name="Test Company Beta",
            symbol="TCB"
        )
        
        if corp_id2:
            result2 = self.verify_corp_id_in_email_data(user1, corp_id2, should_exist=False)
            results.append(("ISIN No Match - User Should NOT Receive", result2))
        else:
            results.append(("ISIN No Match - User Should NOT Receive", False))
        
        return results

    def test_category_matching(self):
        """Test category-based announcement matching"""
        print("\n" + "="*60)
        print("TESTING CATEGORY-BASED ANNOUNCEMENT MATCHING")
        print("="*60)
        
        results = []
        
        # Test user with category-based watchlist
        user2 = test_users[1] if len(test_users) > 1 else None
        if not user2:
            print("❌ No second test user available for category matching test")
            return []
        
        # Get category from user2's watchlist
        test_category = None
        if user2['watchlists']:
            test_category = user2['watchlists'][0]['category']
        
        if not test_category:
            print("❌ No category available in user2's watchlist for testing")
            return []
        
        print(f"\nTest 1: Sending announcement for category {test_category} (should match user {user2['user_number']})")
        corp_id3 = self.send_mock_announcement(
            category=test_category,
            company_name="Test Company Gamma",
            symbol="TCG"
        )
        
        if corp_id3:
            result3 = self.verify_corp_id_in_email_data(user2, corp_id3, should_exist=True)
            results.append(("Category Match - User Should Receive", result3))
        else:
            results.append(("Category Match - User Should Receive", False))
        
        # Test non-matching category
        non_matching_category = "Non-Existent Category"
        
        print(f"\nTest 2: Sending announcement for non-matching category {non_matching_category}")
        corp_id4 = self.send_mock_announcement(
            category=non_matching_category,
            company_name="Test Company Delta",
            symbol="TCD"
        )
        
        if corp_id4:
            result4 = self.verify_corp_id_in_email_data(user2, corp_id4, should_exist=False)
            results.append(("Category No Match - User Should NOT Receive", result4))
        else:
            results.append(("Category No Match - User Should NOT Receive", False))
        
        return results

    def test_multiple_users_same_isin(self):
        """Test multiple users with same ISIN in watchlist"""
        print("\n" + "="*60)
        print("TESTING MULTIPLE USERS WITH SAME ISIN")
        print("="*60)
        
        results = []
        
        if len(test_users) < 2:
            print("❌ Need at least 2 users for multiple user testing")
            return []
        
        # Find a common ISIN between users
        common_isin = None
        for user1 in test_users:
            for watchlist1 in user1['watchlists']:
                for isin in watchlist1['isins']:
                    # Check if any other user has this ISIN
                    for user2 in test_users:
                        if user2['user_id'] != user1['user_id']:
                            for watchlist2 in user2['watchlists']:
                                if isin in watchlist2['isins']:
                                    common_isin = isin
                                    break
                            if common_isin:
                                break
                    if common_isin:
                        break
                if common_isin:
                    break
            if common_isin:
                break
        
        if not common_isin:
            print("❌ No common ISIN found between users")
            return []
        
        print(f"\nSending announcement for common ISIN {common_isin}")
        corp_id5 = self.send_mock_announcement(
            isin=common_isin,
            company_name="Test Company Echo",
            symbol="TCE"
        )
        
        if corp_id5:
            # Verify all users with this ISIN receive the corp_id
            all_passed = True
            for user in test_users:
                has_isin = False
                for watchlist in user['watchlists']:
                    if common_isin in watchlist['isins']:
                        has_isin = True
                        break
                
                if has_isin:
                    result = self.verify_corp_id_in_email_data(user, corp_id5, should_exist=True)
                    if not result:
                        all_passed = False
                    results.append((f"User {user['user_number']} Should Receive", result))
            
            results.append(("All Users with ISIN Received Notification", all_passed))
        else:
            results.append(("Multiple Users Test", False))
        
        return results

    def run_comprehensive_test(self):
        """Run comprehensive announcement notification test"""
        print("\n" + "="*80)
        print("STARTING COMPREHENSIVE ANNOUNCEMENT NOTIFICATION TESTS")
        print("="*80)
        print(f"Test timestamp: {datetime.now().isoformat()}")
        
        all_results = []
        
        try:
            # Step 0: Check server health
            if not self.check_server_health():
                print("❌ Server health check failed. Cannot proceed with tests.")
                return []
            # Step 1: Create test users
            print("\n" + "="*60)
            print("STEP 1: CREATING TEST USERS")
            print("="*60)
            
            for i in range(3):
                user = self.create_test_user(i + 1)
                if not user:
                    print(f"❌ Failed to create user {i + 1}")
                    return []
            
            print(f"\n✅ Created {len(test_users)} test users")
            
            # Step 2: Create watchlists for each user
            print("\n" + "="*60)
            print("STEP 2: CREATING WATCHLISTS")
            print("="*60)
            
            # User 1: ISIN-based watchlist
            if len(test_users) > 0:
                user1_isins = MOCK_ISINS[:3]  # First 3 ISINs
                self.create_watchlist_for_user(
                    test_users[0], 
                    "Tech Portfolio", 
                    user1_isins
                )
            
            # User 2: Category-based watchlist with some ISINs
            if len(test_users) > 1:
                user2_isins = MOCK_ISINS[2:5]  # ISINs 2-4 (overlap with user 1)
                self.create_watchlist_for_user(
                    test_users[1], 
                    "Financial Alerts", 
                    user2_isins, 
                    category=MOCK_CATEGORIES[0]
                )
            
            # User 3: Mixed watchlist
            if len(test_users) > 2:
                user3_isins = MOCK_ISINS[4:7]  # ISINs 4-6
                self.create_watchlist_for_user(
                    test_users[2], 
                    "Mixed Portfolio", 
                    user3_isins, 
                    category=MOCK_CATEGORIES[1]
                )
            
            print(f"\n✅ Created {len(test_watchlists)} watchlists")
            
            # Step 3: Test ISIN matching
            isin_results = self.test_isin_matching()
            all_results.extend(isin_results)
            
            # Step 4: Test category matching
            category_results = self.test_category_matching()
            all_results.extend(category_results)
            
            # Step 5: Test multiple users with same ISIN
            multiple_user_results = self.test_multiple_users_same_isin()
            all_results.extend(multiple_user_results)
            
            # Step 6: Print final summary
            self.print_test_summary(all_results)
            
            return all_results
            
        except Exception as e:
            print(f"\n❌ Test execution failed: {str(e)}")
            print(traceback.format_exc())
            return []

    def print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n" + "="*80)
        print("COMPREHENSIVE TEST SUMMARY")
        print("="*80)
        
        if not results:
            print("❌ No test results to display")
            return
        
        passed_tests = 0
        total_tests = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
            if result:
                passed_tests += 1
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print(f"OVERALL RESULTS:")
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print("="*80)
        
        # Print test data summary
        print(f"\nTest Data Summary:")
        print(f"Users Created: {len(test_users)}")
        print(f"Watchlists Created: {len(test_watchlists)}")
        print(f"Announcements Sent: {len(test_announcements)}")
        
        if test_users:
            print(f"\nUser Details:")
            for user in test_users:
                print(f"  User {user['user_number']}: {user['email']} (ID: {user['user_id']})")
                for wl in user['watchlists']:
                    print(f"    - {wl['name']}: {len(wl['isins'])} ISINs, Category: {wl['category']}")
        
        if test_announcements:
            print(f"\nAnnouncements Sent:")
            for ann in test_announcements:
                print(f"  Corp ID: {ann['corp_id']}, ISIN: {ann['isin']}, Category: {ann['category']}")

def main():
    """Main test execution function"""
    tester = AnnouncementTester()
    
    try:
        results = tester.run_comprehensive_test()
        
        # Exit with appropriate status code
        if results:
            passed_count = sum(1 for _, result in results if result)
            if passed_count == len(results):
                print("\n🎉 All tests passed successfully!")
                sys.exit(0)
            else:
                failed_count = len(results) - passed_count
                print(f"\n⚠️  {failed_count} out of {len(results)} tests failed!")
                sys.exit(1)
        else:
            print("\n❌ No tests were executed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test execution failed with error: {e}")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
