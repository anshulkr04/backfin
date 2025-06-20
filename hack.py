from supabase import create_client, Client

apikey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlob3ZwdXpyZ2lyeXJrZWtnbHFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkxMDE4OTcsImV4cCI6MjA2NDY3Nzg5N30.l1QTfSI6ri41defli1k-rHZDZYfJ0JvEm-VqV7Vwrjc"

supabase_url = "https://yhovpuzrgiryrkekglqj.supabase.co"

supabase: Client = create_client(supabase_url, apikey)

# Fixed data with integer for pns_rating
application_data = {
    "email": "john.doe@example.com",
    "name": "John Doe", 
    "skills": "Python, JavaScript, React, Data Analysis",
    "time_commitment": "20 hours per week",
    "experience": "3 years in software development",
    "pns_rating": 8,  # Changed to integer
    "trading_experience": "2 years day trading, familiar with options",
    "preferred_role": "Backend Developer",
    "project_interest": "Building trading algorithms and data visualization tools"
}

try:
    response = supabase.table("applications").insert(application_data).execute()
    print("Insert successful:")
    print(response)
    
    # Now try to read the data back
    print("\nReading data back:")
    a = supabase.table("applications").select("*").execute()
    print(a)
    
except Exception as e:
    print("Insert failed:")
    print("Error:", str(e))