from supabase import create_client
from dotenv import load_dotenv
import os
import uuid
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json

class StructOutput(BaseModel):
    """Schema for structured output"""
    list_aliases: list[str] = Field(..., description="List of aliases or names used to invest")

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL2")
supabase_key = os.getenv("SUPABASE_KEY2")

gemini_api_key = os.getenv("GEMINI_API_KEY")

supabase = create_client(supabase_url, supabase_key)

def uploadInvestor(list_of_investors, list_of_institutions, corp_id):
    print(f"Starting uploadInvestor with {len(list_of_investors)} investors and {len(list_of_institutions)} institutions")
    print(f"Corporation ID: {corp_id}")

    investorList = []

    for investor in list_of_investors:
        print(f"Processing individual investor: {investor}")
        
        investorResponse = supabase.table("smart_investors").select("*").eq("investor_name", investor).execute()
        
        if investorResponse.data:
            data = investorResponse.data[0]
            investor_id = data.get("investor_id")
            investor_name = data.get("investor_name")
            alias_id = data.get("alias_id")
            alias = "False"
            alias_name = ""

            investorList.append({
                "corp_id": corp_id,
                "investor_id": investor_id,
                "investor_name": investor_name,
                "aliasBool": alias,
                "aliasName": alias_name,
                "alias_id": alias_id,
                "verified": True,
                "type": "individual"
            })
        else:
            aliasResponse = supabase.table("investor_aliases").select("*").eq("alias_name", investor).execute()
            
            if aliasResponse.data:
                data = aliasResponse.data[0]
                investor_id = data.get("investor_id")
                investor_name = data.get("investor_name")
                alias_id = data.get("alias_id")
                alias = "True"
                alias_name = investor

                print(f"Found existing alias for {investor}: ID={investor_id}, Name={investor_name}")

                investorList.append({
                    "corp_id": corp_id,
                    "investor_id": investor_id,
                    "investor_name": investor_name,
                    "aliasBool": alias,
                    "aliasName": alias_name,
                    "alias_id": alias_id,
                    "verified": True,
                    "type": "individual"
                })
            else:
                print(f"No existing records found for {investor}, creating new entry")
                
                new_investor_id = str(uuid.uuid4())
                supData = {
                    "investor_id": new_investor_id,
                    "investor_name": investor,
                    "corp_id": corp_id,
                }
            
                unverifiedInvestor = supabase.table("unverified_investors").insert(supData).execute()
                print(f"Added {investor} to unverified_investors with ID: {new_investor_id}")
                
                investorList.append({
                    "investor_id": new_investor_id,
                    "investor_name": investor,
                    "corp_id": corp_id,
                    "aliasBool": "False",
                    "aliasName": "",
                    "alias_id": None,
                    "verified": False,
                    "type": "individual"
                })

    for institution in list_of_institutions:
        print(f"Processing institution: {institution}")
        
        inst = supabase.table("smart_investors").select("*").eq("investor_name", institution).execute()
        
        if inst.data:
            data = inst.data[0]
            investor_id = data.get("investor_id")
            investor_name = data.get("investor_name")
            alias_id = data.get("alias_id")
            alias = "False"
            alias_name = ""
            
            print(f"Found existing institution record: ID={investor_id}, Name={investor_name}")
            
            investorList.append({
                "corp_id": corp_id,
                "investor_id": investor_id,
                "investor_name": investor_name,
                "aliasBool": alias,
                "aliasName": alias_name,
                "alias_id": alias_id,
                "verified": True,
                "type": "institution"
            })
        else:
            aliasInst = supabase.table("investor_aliases").select("*").eq("alias_name", institution).execute()
            
            if aliasInst.data:
                data = aliasInst.data[0]
                investor_id = data.get("investor_id")
                investor_name = data.get("investor_name")
                alias_id = data.get("alias_id")
                alias = "True"
                alias_name = institution

                print(f"Found existing alias for {institution}: ID={investor_id}, Name={investor_name}")

                investorList.append({
                    "corp_id": corp_id,
                    "investor_id": investor_id,
                    "investor_name": investor_name,
                    "aliasBool": alias,
                    "aliasName": alias_name,
                    "alias_id": alias_id,
                    "verified": True,
                    "type": "institution"
                })
            else:
                print(f"No existing records found for institution {institution}, creating new entry")
                
                new_investor_id = str(uuid.uuid4())
                data = {
                    "investor_id": new_investor_id,
                    "investor_name": institution,
                    "corp_id": corp_id
                }
                
                unverifiedInvestor = supabase.table("unverified_investors").insert(data).execute()
                print(f"Added {institution} to unverified_investors with ID: {new_investor_id}")
                
                investorList.append({
                    "investor_id": new_investor_id,
                    "investor_name": institution,
                    "corp_id": corp_id,
                    "aliasBool": "False",
                    "aliasName": "",
                    "alias_id": None,
                    "verified": False,
                    "type": "institution"
                })
    
    # Upload all investor records
    print(f"Preparing to upload {len(investorList)} investor records to investorCorp table")
    dataUpload = supabase.table("investorCorp").insert(investorList).execute()
    
    if dataUpload.data:
        print(f"Success: {len(dataUpload.data)} investor links successfully uploaded")
    else:
        print("Failed to upload investor links")
        print(f"Error details: {dataUpload}")

    return True

def getAliases(investor_name):
    # Configure the client
    client = genai.Client(api_key=gemini_api_key)

    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    config = types.GenerateContentConfig(
        tools=[grounding_tool],
    )

    struct_config = {
        "response_mime_type": "application/json",
        "response_schema": list[StructOutput]
    }

    def generate_alias_prompt(name: str) -> str:
        prompt = (
            f"Give a comprehensive list of all names — including personal name variations, trusts, LLPs, "
            f"private limited companies, and other entities — under which {name} is known to invest or hold shares. "
            f"Include names used in corporate filings, SEBI disclosures, stock market investments, real estate holdings, "
            f"and trust structures. Go beyond commonly known entities — and list entities such as Bright Star Investments, "
            f"Derive Trading, Gulmohar Trust, Damani Estate and Finance, etc., if associated. "
            f"If any of these are connected to their family or known proxies, include those too."
        )
        return prompt


    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=generate_alias_prompt(investor_name),
        config=config,
    )

    resp = response.text

    aliases = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[resp],
        config=struct_config
    )

    parsed_output = json.loads(aliases.text)  
    alias_list = parsed_output[0]["list_aliases"]
    alias_list = [alias for alias in alias_list if f"{investor_name}" not in alias]

    return alias_list

def verify_Investor(investor_id , alias_name, investor_name,invType):
    if alias_name:
        data = supabase.table("investor_aliases").update({
            "alias_name": alias_name,
            "verified": True,
            "investor_name": investor_name
        }).eq("investor_id", investor_id).execute()
        print("Alias updated successfully.")
    
    invdata = supabase.table("investor_aliases").update({
        "verified": True,
        "investor_name": investor_name
    }).eq("investor_id", investor_id).execute()
    print("Investor verified successfully.")

    data = {
        "investor_id": investor_id,
        "type": invType,
        "investor_name": investor_name
    }

    invData = supabase.table("smart_investors").insert(data).execute()
    if invData.data:
        print("Investor added to smart investors successfully.")
    else:
        print("Failed to add investor to smart investors.")

    return True

def addAlias(investor_id, alias_name):
    data = {
        "investor_id": investor_id,
        "alias_name": alias_name,
        "alias_id": str(uuid.uuid4()),
    }
    data = supabase.table("investor_aliases").insert(data).execute()
    if data:
        print("Alias added successfully.")
    else:
        print("Failed to add alias.")

    return True

def createInvestor(investor_name, aliasArray, invType):

    investor_id = str(uuid.uuid4())
    data = {
        "investor_id": investor_id,
        "investor_name": investor_name,
        "type": invType
    }
    response = supabase.table("smart_investors").insert(data).execute()

    if aliasArray:
        for alias in aliasArray:
            addAlias(investor_id, alias)
    return True



