from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url: str = os.getenv("SUPABASE_URL2")
supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(supabase_url, supabase_key)

response = supabase.table("stocklistdata").select("*").execute()

print(response.data)