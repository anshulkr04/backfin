"""
Investor Upload and Management Module

This module handles the processing and uploading of investor data to Supabase,
including alias management and verification processes.

Required Environment Variables:
- SUPABASE_URL2: Your Supabase project URL
- SUPABASE_KEY2: Your Supabase API key
- GEMINI_API_KEY: API key for Google Gemini AI (for alias generation)

Dependencies:
- pip install supabase python-dotenv google-generativeai pydantic

Functions:
- uploadInvestor: Main function to upload investors and institutions
- getAliases: Generate aliases using Gemini AI
- verify_Investor: Verify and add investors to smart_investors table
- addAlias: Add alias for an existing investor
- createInvestor: Create new investor with aliases
"""

from supabase import create_client
from dotenv import load_dotenv
import os
import uuid
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("investor_upload.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("InvestorManager")

class StructOutput(BaseModel):
    """Schema for structured output"""
    list_aliases: list[str] = Field(..., description="List of aliases or names used to invest")

# Load environment variables
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL2")
supabase_key = os.getenv("SUPABASE_KEY2")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Validate environment variables
if not supabase_url or not supabase_key:
    logger.error("Missing Supabase credentials - SUPABASE_URL2 and SUPABASE_KEY2 required")
    raise ValueError("Missing required Supabase environment variables")

if not gemini_api_key:
    logger.warning("Missing GEMINI_API_KEY - alias generation will not work")

# Initialize Supabase client
try:
    supabase = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

def uploadInvestor(list_of_investors, list_of_institutions, corp_id,saved_price):
    """
    Upload investors and institutions to the database with proper validation and logging
    
    Args:
        list_of_investors (list): List of individual investor names
        list_of_institutions (list): List of institution names
        corp_id (str): Corporation ID to link investments to
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting uploadInvestor with {len(list_of_investors)} investors and {len(list_of_institutions)} institutions")
        logger.info(f"Corporation ID: {corp_id}")

        if not corp_id:
            logger.error("No corporation ID provided")
            return False

        investorList = []

        # Process individual investors
        for investor in list_of_investors:
            if not investor or not investor.strip():
                logger.warning("Skipping empty investor name")
                continue
                
            investor = investor.strip()
            logger.debug(f"Processing individual investor: {investor}")
            
            try:
                # Check if investor exists in smart_investors table
                investorResponse = supabase.table("smart_investors").select("*").eq("investor_name", investor).execute()
                
                if investorResponse.data:
                    data = investorResponse.data[0]
                    investor_id = data.get("investor_id")
                    investor_name = data.get("investor_name")
                    alias_id = data.get("alias_id")
                    
                    logger.info(f"Found existing investor record: {investor_name} (ID: {investor_id})")

                    investorList.append({
                        "corp_id": corp_id,
                        "investor_id": investor_id,
                        "investor_name": investor_name,
                        "aliasBool": "False",
                        "aliasName": "",
                        "alias_id": alias_id,
                        "verified": True,
                        "type": "individual",
                        "saved_price": saved_price
                    })
                else:
                    # Check if it's an alias
                    aliasResponse = supabase.table("investor_aliases").select("*").eq("alias_name", investor).execute()
                    
                    if aliasResponse.data:
                        data = aliasResponse.data[0]
                        investor_id = data.get("investor_id")
                        investor_name = data.get("investor_name")
                        alias_id = data.get("alias_id")

                        logger.info(f"Found existing alias for {investor}: ID={investor_id}, Name={investor_name}")

                        investorList.append({
                            "corp_id": corp_id,
                            "investor_id": investor_id,
                            "investor_name": investor_name,
                            "aliasBool": "True",
                            "aliasName": investor,
                            "alias_id": alias_id,
                            "verified": True,
                            "type": "individual",
                            "saved_price":saved_price
                        })
                    else:
                        # Create new unverified investor
                        logger.info(f"No existing records found for {investor}, creating new entry")
                        
                        new_investor_id = str(uuid.uuid4())
                        supData = {
                            "investor_id": new_investor_id,
                            "investor_name": investor,
                            "corp_id": corp_id,
                            "saved_price": saved_price
                        }
                    
                        unverifiedInvestor = supabase.table("unverified_investors").insert(supData).execute()
                        
                        if unverifiedInvestor.data:
                            logger.info(f"Added {investor} to unverified_investors with ID: {new_investor_id}")
                        else:
                            logger.error(f"Failed to add {investor} to unverified_investors")
                            continue
                        
                        investorList.append({
                            "investor_id": new_investor_id,
                            "investor_name": investor,
                            "corp_id": corp_id,
                            "aliasBool": "False",
                            "aliasName": "",
                            "alias_id": None,
                            "verified": False,
                            "type": "individual",
                            "saved_price": saved_price
                        })
                        
            except Exception as e:
                logger.error(f"Error processing individual investor {investor}: {e}")
                continue

        # Process institutions
        for institution in list_of_institutions:
            if not institution or not institution.strip():
                logger.warning("Skipping empty institution name")
                continue
                
            institution = institution.strip()
            logger.debug(f"Processing institution: {institution}")
            
            try:
                # Check if institution exists in smart_investors table
                inst = supabase.table("smart_investors").select("*").eq("investor_name", institution).execute()
                
                if inst.data:
                    data = inst.data[0]
                    investor_id = data.get("investor_id")
                    investor_name = data.get("investor_name")
                    alias_id = data.get("alias_id")
                    
                    logger.info(f"Found existing institution record: {investor_name} (ID: {investor_id})")
                    
                    investorList.append({
                        "corp_id": corp_id,
                        "investor_id": investor_id,
                        "investor_name": investor_name,
                        "aliasBool": "False",
                        "aliasName": "",
                        "alias_id": alias_id,
                        "verified": True,
                        "type": "institution",
                        "saved_price": saved_price
                    })
                else:
                    # Check if it's an alias
                    aliasInst = supabase.table("investor_aliases").select("*").eq("alias_name", institution).execute()
                    
                    if aliasInst.data:
                        data = aliasInst.data[0]
                        investor_id = data.get("investor_id")
                        investor_name = data.get("investor_name")
                        alias_id = data.get("alias_id")

                        logger.info(f"Found existing alias for {institution}: ID={investor_id}, Name={investor_name}")

                        investorList.append({
                            "corp_id": corp_id,
                            "investor_id": investor_id,
                            "investor_name": investor_name,
                            "aliasBool": "True",
                            "aliasName": institution,
                            "alias_id": alias_id,
                            "verified": True,
                            "type": "institution",
                            "saved_price": saved_price
                        })
                    else:
                        # Create new unverified institution
                        logger.info(f"No existing records found for institution {institution}, creating new entry")
                        
                        new_investor_id = str(uuid.uuid4())
                        data = {
                            "investor_id": new_investor_id,
                            "investor_name": institution,
                            "corp_id": corp_id,
                            "saved_price": saved_price
                        }
                        
                        unverifiedInvestor = supabase.table("unverified_investors").insert(data).execute()
                        
                        if unverifiedInvestor.data:
                            logger.info(f"Added {institution} to unverified_investors with ID: {new_investor_id}")
                        else:
                            logger.error(f"Failed to add {institution} to unverified_investors")
                            continue
                        
                        investorList.append({
                            "investor_id": new_investor_id,
                            "investor_name": institution,
                            "corp_id": corp_id,
                            "aliasBool": "False",
                            "aliasName": "",
                            "alias_id": None,
                            "verified": False,
                            "type": "institution",
                            "saved_price": saved_price
                        })
                        
            except Exception as e:
                logger.error(f"Error processing institution {institution}: {e}")
                continue
        
        # Upload all investor records
        if not investorList:
            logger.warning("No valid investors to upload")
            return False
            
        logger.info(f"Preparing to upload {len(investorList)} investor records to investorCorp table")
        
        try:
            dataUpload = supabase.table("investorCorp").insert(investorList).execute()
            
            if dataUpload.data:
                logger.info(f"Success: {len(dataUpload.data)} investor links successfully uploaded")
                return True
            else:
                logger.error("Failed to upload investor links - no data returned")
                logger.debug(f"Upload response: {dataUpload}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading investor records: {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error in uploadInvestor: {e}")
        return False

def getAliases(investor_name):
    """
    Generate aliases for an investor using Gemini AI
    
    Args:
        investor_name (str): Name of the investor to generate aliases for
        
    Returns:
        list: List of aliases or empty list if error occurs
    """
    if not gemini_api_key:
        logger.error("Cannot generate aliases: GEMINI_API_KEY not configured")
        return []
        
    if not investor_name or not investor_name.strip():
        logger.error("Cannot generate aliases: empty investor name provided")
        return []

    try:
        logger.info(f"Generating aliases for investor: {investor_name}")
        
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

        logger.debug("Sending request to Gemini for alias generation")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=generate_alias_prompt(investor_name),
            config=config,
        )

        if not hasattr(response, 'text') or not response.text:
            logger.error("Empty response from Gemini API")
            return []

        resp = response.text
        logger.debug("Received initial response from Gemini, processing structured output")

        aliases = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[resp],
            config=struct_config
        )

        if not hasattr(aliases, 'text') or not aliases.text:
            logger.error("Empty structured response from Gemini API")
            return []

        try:
            parsed_output = json.loads(aliases.text)  
            alias_list = parsed_output[0]["list_aliases"]
            
            # Filter out the original investor name from aliases
            alias_list = [alias for alias in alias_list if investor_name not in alias]
            
            logger.info(f"Generated {len(alias_list)} aliases for {investor_name}")
            logger.debug(f"Aliases: {alias_list}")
            
            return alias_list
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Error parsing Gemini response: {e}")
            logger.debug(f"Raw response: {aliases.text}")
            return []

    except Exception as e:
        logger.error(f"Error generating aliases for {investor_name}: {e}")
        return []

def verify_Investor(investor_id, alias_name, investor_name, invType):
    """
    Verify an investor and add them to smart_investors table
    
    Args:
        investor_id (str): Unique investor ID
        alias_name (str): Alias name if applicable
        investor_name (str): Primary investor name
        invType (str): Type of investor (individual/institution)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not investor_id or not investor_name or not invType:
        logger.error("Missing required parameters for investor verification")
        return False
        
    try:
        logger.info(f"Verifying investor: {investor_name} (ID: {investor_id}, Type: {invType})")
        
        # Update alias if provided
        if alias_name and alias_name.strip():
            try:
                alias_data = supabase.table("investor_aliases").update({
                    "alias_name": alias_name.strip(),
                    "verified": True,
                    "investor_name": investor_name
                }).eq("investor_id", investor_id).execute()
                
                if alias_data.data:
                    logger.info(f"Alias '{alias_name}' updated successfully for investor {investor_name}")
                else:
                    logger.warning(f"No alias record found to update for investor_id: {investor_id}")
                    
            except Exception as e:
                logger.error(f"Error updating alias: {e}")
        
        # Verify investor in aliases table
        try:
            invdata = supabase.table("investor_aliases").update({
                "verified": True,
                "investor_name": investor_name
            }).eq("investor_id", investor_id).execute()
            
            logger.debug("Investor verified in aliases table")
            
        except Exception as e:
            logger.warning(f"Error updating investor verification in aliases table: {e}")

        # Add to smart_investors table
        data = {
            "investor_id": investor_id,
            "type": invType,
            "investor_name": investor_name
        }

        try:
            invData = supabase.table("smart_investors").insert(data).execute()
            
            if invData.data:
                logger.info(f"Investor {investor_name} added to smart_investors successfully")
                return True
            else:
                logger.error(f"Failed to add investor {investor_name} to smart_investors")
                logger.debug(f"Insert response: {invData}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding investor to smart_investors: {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error in verify_Investor: {e}")
        return False

def addAlias(investor_id, alias_name):
    """
    Add an alias for an existing investor
    
    Args:
        investor_id (str): Existing investor ID
        alias_name (str): Alias name to add
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not investor_id or not alias_name:
        logger.error("Missing required parameters for adding alias")
        return False
        
    try:
        alias_name = alias_name.strip()
        logger.info(f"Adding alias '{alias_name}' for investor ID: {investor_id}")
        
        # Check if alias already exists
        existing_alias = supabase.table("investor_aliases").select("*").eq("alias_name", alias_name).execute()
        
        if existing_alias.data:
            logger.warning(f"Alias '{alias_name}' already exists")
            return False
        
        data = {
            "investor_id": investor_id,
            "alias_name": alias_name,
            "alias_id": str(uuid.uuid4()),
        }
        
        result = supabase.table("investor_aliases").insert(data).execute()
        
        if result.data:
            logger.info(f"Alias '{alias_name}' added successfully")
            return True
        else:
            logger.error(f"Failed to add alias '{alias_name}'")
            logger.debug(f"Insert response: {result}")
            return False

    except Exception as e:
        logger.error(f"Error adding alias: {e}")
        return False

def createInvestor(investor_name, aliasArray, invType):
    """
    Create a new investor with aliases
    
    Args:
        investor_name (str): Primary investor name
        aliasArray (list): List of aliases
        invType (str): Type of investor (individual/institution)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not investor_name or not invType:
        logger.error("Missing required parameters for creating investor")
        return False
        
    try:
        investor_name = investor_name.strip()
        logger.info(f"Creating new investor: {investor_name} (Type: {invType})")
        
        # Check if investor already exists
        existing_investor = supabase.table("smart_investors").select("*").eq("investor_name", investor_name).execute()
        
        if existing_investor.data:
            logger.warning(f"Investor '{investor_name}' already exists")
            return False

        investor_id = str(uuid.uuid4())
        data = {
            "investor_id": investor_id,
            "investor_name": investor_name,
            "type": invType
        }
        
        response = supabase.table("smart_investors").insert(data).execute()
        
        if not response.data:
            logger.error(f"Failed to create investor '{investor_name}'")
            logger.debug(f"Insert response: {response}")
            return False
            
        logger.info(f"Investor '{investor_name}' created successfully with ID: {investor_id}")

        # Add aliases if provided
        if aliasArray and len(aliasArray) > 0:
            logger.info(f"Adding {len(aliasArray)} aliases for {investor_name}")
            
            alias_success_count = 0
            for alias in aliasArray:
                if alias and alias.strip():
                    if addAlias(investor_id, alias.strip()):
                        alias_success_count += 1
                    else:
                        logger.warning(f"Failed to add alias '{alias}' for {investor_name}")
                        
            logger.info(f"Successfully added {alias_success_count}/{len(aliasArray)} aliases")
        else:
            logger.info("No aliases to add")
            
        return True

    except Exception as e:
        logger.error(f"Error creating investor: {e}")
        return False

# Test function for debugging
def test_module():
    """Test function to verify module functionality"""
    logger.info("Testing investor upload module...")
    
    # Test with sample data
    test_investors = ["Test Individual Investor"]
    test_institutions = ["Test Institution"]
    test_corp_id = str(uuid.uuid4())
    
    result = uploadInvestor(test_investors, test_institutions, test_corp_id)
    logger.info(f"Test upload result: {result}")
    
    return result

if __name__ == "__main__":
    # Run tests if executed directly
    test_module()