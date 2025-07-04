import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

def get_ohlc_data(request_data={}):
    url = "https://api.dhan.co/v2/marketfeed/ohlc"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID
    }

    response = requests.post(url, headers=headers, json=request_data)

    if response.status_code == 200:
        return response.json()
    else:
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)
        return f"Error: {response.status_code}"

if __name__ == "__main__":
    # Sample request structure as per docs
    data = {
        "NSE_EQ": [11536],  # Replace with actual instrument token(s)
        # "NSE_FNO": [49081, 49082]  # Optional: Uncomment and update if needed
    }

    ohlc_data = get_ohlc_data(data)
    print(ohlc_data)
