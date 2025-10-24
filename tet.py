from google import genai
from dotenv import load_dotenv
import os

from workers.ephemeral_ai_worker import with_timeout
load_dotenv()
from pydantic import BaseModel, Field
from src.ai.prompts import category_prompt, headline_prompt, all_prompt, financial_data_prompt
import time



client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

uploaded_files = client.files.upload(file="./back.pdf")

tokens = client.models.count_tokens(model="gemini-2.5-flash-lite" , contents=uploaded_files)
print("Uploaded file tokens:", tokens)

prompt = "analyze the following financial document and provide a summary of key points, including any significant changes in financial metrics, trends, and noteworthy events mentioned in the document." 

response = client.models.generate_content(model="gemini-2.5-flash-lite",
                                          contents=[uploaded_files,prompt])

print("Response:", response.text)