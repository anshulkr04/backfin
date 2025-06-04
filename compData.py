import requests
import json

def bse_company_data(scrip_id):
    if not scrip_id:
        print("Error: Scrip ID is empty or None")
        return None

    pe_url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode={scrip_id}&seriesid="

    with requests.Session() as session:
        # Get cookies by visiting the homepage first
        homepage_url = "https://www.bseindia.com"
        session.get(homepage_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        })

        # Set headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
            "Connection": "keep-alive",
        }

        try:
            response = session.get(pe_url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            pe = data.get('PE')
            eps = data.get('EPS')

            hl_url = f"https://api.bseindia.com/BseIndiaAPI/api/HighLow/w?Type=EQ&flag=C&scripcode={scrip_id}"

            response = session.get(hl_url, headers=headers, timeout=10)
            response.raise_for_status()
            hl_data = response.json()
            fiftyTwoHighAdj = hl_data.get('Fifty2WkHigh_adj')
            fiftyTwoLowAdj = hl_data.get('Fifty2WkLow_adj')
            return {
                'PE': pe,
                'Fifty2WkHigh_adj': fiftyTwoHighAdj,
                'Fifty2WkLow_adj': fiftyTwoLowAdj,
                'EPS': eps,
            }


        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except json.JSONDecodeError:
            print("Error decoding JSON response")
            return None


scrip_code = "500325"
result = bse_company_data(scrip_code)
print(result)


