from google import genai
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
import sys
from google.genai import types

load_dotenv()

# Fix the import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import prompts (fix the import path)
try:
    from src.ai.prompts import *
except ImportError:
    # Fallback prompts if import fails
    category_prompt = "Categorize the announcement"
    headline_prompt = "Create a headline"
    all_prompt = "Summarize the announcement"
    financial_data_prompt = "Extract financial data"

GOOGLE_GENAI_API_KEY = os.getenv("GEMINI_API_KEY")

class StrucOutput(BaseModel):
    """Schema for structured output from the model."""
    category: str = Field(..., description=category_prompt if 'category_prompt' in globals() else "Categorize the financial announcement")
    headline: str = Field(..., description=headline_prompt if 'headline_prompt' in globals() else "Create a compelling headline")
    summary: str = Field(..., description=all_prompt if 'all_prompt' in globals() else "Provide a comprehensive summary")
    findata: str = Field(..., description=financial_data_prompt if 'financial_data_prompt' in globals() else "Extract key financial data")
    individual_investor_list: list[str] = Field(default_factory=list, description="List of individual investors mentioned in the announcement")
    company_investor_list: list[str] = Field(default_factory=list, description="List of company investors mentioned in the announcement")
    sentiment: str = Field(..., description="Sentiment analysis: Positive, Negative, or Neutral")


def get_structured_output(announcement_text: str) -> StrucOutput:
    """Get structured output from Gemini AI for financial announcement analysis"""
    
    prompt = f"""
    You are an expert on financial analysis and stock market. 
    
    Analyze the following financial announcement and provide structured output:
    
    Announcement: {announcement_text}
    
    Provide detailed analysis covering category, headline, summary, financial data, 
    investors, and sentiment as per the schema.
    """

    try:
        # Initialize client with API key
        client = genai.Client(api_key=GOOGLE_GENAI_API_KEY)
        
        # Generate content with structured output
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",  # Use available model
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StrucOutput,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True
                )
            )
        )
        
        return response
            
    except Exception as e:
        print(f"Error getting structured output: {e}")
        # Return a fallback response
        return StrucOutput(
            category="Error",
            headline="Failed to process announcement",
            summary="Error occurred during AI processing",
            findata="No financial data available",
            individual_investor_list=[],
            company_investor_list=[],
            sentiment="Neutral"
        )

# Test function
def test_with_sample_announcement():
    """Test the function with a sample announcement"""
    sample_text = """
    RELIANCE INDUSTRIES LIMITED has announced its Q3 FY2024 results. 
    The company reported a net profit of Rs 18,951 crores, up 12% YoY. 
    Revenue increased to Rs 2,35,122 crores. The board declared an interim dividend of Rs 9 per share.
    Major investor Mukesh Ambani increased his stake, while BlackRock reduced its holding.
    """
    
    print("Testing with sample announcement...")
    result = get_structured_output(sample_text)
    print("Result:", result)
    return result

if __name__ == "__main__":
    # Check if API key is available
    if not GOOGLE_GENAI_API_KEY:
        print("❌ GEMINI_API_KEY not found in environment variables")
        print("Please set your Gemini API key in the .env file")
    else:
        print("✅ API Key found, running test...")
        test_with_sample_announcement()
