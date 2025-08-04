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


def getInvestorLinks(list_of_investors,list_of_institutions, corp_id):

    investorList = []

    for investor in list_of_investors:
        response = supabase.table("investor_aliases").select("*").or_(f"investor_name.eq.\"{investor}\",alias_name.eq.\"{investor}\"").execute()

        if not response.data :
            supData = {
                "investor_id": str(uuid.uuid4()),
                "investor_name": investor,
                "corp_id": corp_id,
            }
            resp  = supabase.table("unverified_investors").select("*").eq("investor_name", investor).execute()
            if resp.data:
                return
            
            unverfiedInvestor = supabase.table("unverified_investors").insert(supData).execute()
            data = {
                "investor_id": supData["investor_id"],
                "investor_name": investor,
                "corp_id": corp_id,
                "verified": False,
                "type": "individual"
            }
            investorList.append(data)
            continue

        data = response.data[0]
        investor_id = data.get("investor_id")
        investor_name = data.get("investor_name")
        alias_id = data.get("alias_id")
        alias = "False"
        alias_name = ""
        for row in response.data:
            if row["alias_name"] == investor:
                alias = "True"
                alias_name = investor
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
    
    for institution in list_of_institutions:
        inst = supabase.table("investor_aliases").select("*").or_(f"investor_name.eq.\"{institution}\",alias_name.eq.\"{institution}\"").execute()

        if not inst.data :
            data = {
                "investor_id": str(uuid.uuid4()),
                "investor_name": institution,
                "corp_id": corp_id
            }
            unverfiedInvestor = supabase.table("unverified_investors").insert(data).execute()
            data = {
                "investor_id": str(uuid.uuid4()),
                "investor_name": institution,
                "corp_id": corp_id,
                "verified": False,
                "type": "institution"
            }
            investorList.append(data)
            continue
        instData = inst.data[0]
        investor_id = instData.get("investor_id")
        investor_name = instData.get("investor_name")
        alias_id = instData.get("alias_id")
        alias = "False"
        alias_name = ""
        for row in inst.data:
            if row["alias_name"] == institution:
                alias = "True"
                alias_name = institution
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
    dataUpload = supabase.table("investorCorp").insert(investorList).execute()
    if dataUpload.data:
        print("Investor links successfully uploaded.")
    else:
        print("Failed to upload investor links.")
        print(dataUpload.error)

    return True

# inv_list = ['Manish Adukia', 'Aditya Soman', 'Swapnil Potdukhe', 'Sachin Salgaonkar', 'Aditya Suresh', 'Gaurav Rateria', 'Vijit Jain', 'Ankur Rudra', 'Gaurav Malhotra', 'Abhisek Banerjee', 'Big Bull']
# inst_list = ['HDFC Bank', 'ICICI Bank', 'Axis Bank', 'State Bank of India']

# corp_id = str(uuid.uuid4())
# getInvestorLinks(inv_list, inst_list, corp_id)

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








