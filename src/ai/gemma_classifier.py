"""
Gemma 3 27B Classification Utility

This module provides utilities for classifying corporate announcements using
Google's Gemma 3 27B model and comparing results with the existing Gemini classification.

Usage:
    from src.ai.gemma_classifier import GemmaClassifier, run_parallel_classification
    
    # Initialize classifier
    classifier = GemmaClassifier(api_key="YOUR_API_KEY")
    
    # Classify a PDF
    result = classifier.classify_pdf(pdf_path)
    
    # Run parallel classification and store comparison
    run_parallel_classification(pdf_url, gemini_category, gemini_summary, supabase)
"""

import os
import json
import logging
import tempfile
import uuid
import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import requests
from dotenv import load_dotenv
load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# The exact classification prompt as provided by the user
GEMMA_CLASSIFICATION_PROMPT = """Role: You are a specialist classification engine for Indian stock exchange corporate announcements. Your sole task is to identify the single most material financial signal.
Objective: Classify the announcement into exactly one category from the lists below.

Phase 0: Input Handling Rules
The "Attachment" Rule: Classify based on the substance of the attachment/enclosure, not the exchange cover letter. The cover letter is merely a filing wrapper. If there is no attachment, classify the cover letter itself.
The "Multi-Topic" Rule: If a single filing contains multiple actionable items (e.g., "Board approved Results + Dividend + QIP"), apply the Global Priority Waterfall below and pick the single highest-priority category.
Global Priority Waterfall (Highest → Lowest)
When multiple categories could apply, the first match wins:
Mergers/Acquisitions / Demerger / Delisting / Open Offer
Fundraise (QIP / Rights / Preferential) / Buyback
Divestitures / Joint Ventures
Expansion / New Order / New Product
Financial Results (formal statutory only)
Debt & Financing / Debt Reduction / Credit Rating
Bonus/Stock Split
Change in KMP / Demise of KMP
Operational Disruption / Litigation & Notices / Regulatory Actions
Agreements/MoUs / Operational Update
Investor Presentation / Concall Transcript / Concall Audio
All Procedural categories

Phase 1: Disambiguation Rules (Apply Before Classifying)
The "Agenda" Rule (Board Meeting / EGM / Postal Ballot Notices)
Do not auto-classify notices as Procedural. Check the Agenda items:
Agenda includes Fundraising, Buyback, Bonus, Split, M&A, Delisting → Classify under that Specific Action Category (e.g., Fundraise - QIP, Buyback).
Agenda = Financial Results ONLY → Procedural - Governance.
Agenda = Routine/General Business → Procedural - Governance.
The "Agreement" Rule (Economic Outcome Test)
Ignore the title ("MoU", "Contract", "Agreement"). Classify based on the economic substance:
Subject of Agreement
Classify As
Borrowing money / Pledging assets
Debt & Financing
Selling goods or services (commercial)
New Order
Buying/Selling/Merging companies
Mergers/Acquisitions
Selling non-core assets (land, subsidiary)
Divestitures
Strategic partnership / Tech transfer / Licensing
Agreements/MoUs

The "Presentation" Rule
Slide deck / Investor brochure with Strategy or Earnings content → Investor Presentation.
Generic corporate profile, marketing brochure, or ESG report → Procedural - General.
The "Subsidiary" Rule
If a material action (fundraise, M&A, expansion, etc.) occurs at a subsidiary and the parent is filing an intimation — classify under the action category, not as Incorporation/Cessation.
The "Amendment" Rule
An amendment, revision, or update to an ongoing corporate action (e.g., revised QIP terms, amended open offer price) retains the original action's category.
The "Perspective" Rule (Expansion vs. New Order)
Company is the buyer of capex / building a plant → Expansion.
Company is the seller/contractor winning a commercial contract → New Order.
The "Convertible Instrument" Rule
FCCBs, OCDs, or convertible warrants being issued for fundraising → Classify under the relevant Fundraise category.
Non-convertible debt instruments (NCDs, CPs, Bonds) → Debt & Financing.

Phase 2: High Materiality Categories (The Signal)
Category
Definition
Agreements/MoUs
(Use Narrowly.) Strategic partnerships, Technology Transfer, Joint Development, or Licensing deals with external parties. Excludes: Sales Contracts (→ New Order), Loans (→ Debt), M&A SPAs (→ M&A).
Annual Report
The full statutory Annual Report document only. No other document (ESG report, sustainability report) qualifies.
Bonus/Stock Split
Approval of bonus shares, share subdivision (split), or consolidation.
Buyback
Share repurchase program approvals or updates.
Change in KMP
Appointment or Resignation of CEO, Managing Director, or CFO only. Whole-Time Directors do not qualify unless they hold a concurrent CEO/MD/CFO title.
Clarifications/Confirmations
Official responses to market rumors or stock exchange queries.
Concall Audio/Video Recording
Submission of links to audio/video recordings of earnings calls or analyst briefings. If a filing contains both a transcript and an audio link, classify as Concall Transcript (higher value).
Concall Transcript
Verbatim written transcripts of earnings calls. Takes priority over Audio/Video if both are in the same filing.
Credit Rating
Upgrades, Downgrades, or new ratings assigned. Excludes: Reaffirmations (→ Procedural - Ratings).
Debt & Financing
New debt issuance (NCDs, CPs, Bonds), loan agreements, or major refinancing.
Debt Reduction
Specific, material actions to pay down outstanding debt (prepayment, redemption).
Delisting
Proposals or approvals to remove shares from stock exchanges.
Demerger
Separating business units into independent legal entities.
Demise of KMP
Death of a Key Management Person (CEO/MD/CFO).
Divestitures
Sale of subsidiaries, business segments, or significant non-core assets.
Expansion
Brownfield/Greenfield projects, new plants, significant CAPEX announcements, or Alteration of MOA Object Clause to enter new business lines.
Financial Results
(EXTREMELY STRICT) Only the formal statutory filing containing full financial statements (P&L, Balance Sheet). A press release summarizing results without the full statutory statements is Operational Update, not this.
Fundraise - Preferential Issue
Capital raising through issuance of shares/warrants to specific investors (including warrant conversion).
Fundraise - QIP
Raising capital from Qualified Institutional Buyers.
Fundraise - Rights Issue
Capital raising by offering shares to existing shareholders.
Incorporation/Cessation of Subsidiary
Formation of new legal entities or closure of existing subsidiaries. Only use when the filing's sole purpose is the incorporation/cessation itself, not when it's incidental to a larger action.
Insolvency and Bankruptcy
Updates on IBC proceedings, NCLT orders, or CIRP.
Investor Presentation
Official slide decks or investor brochures containing strategy or financial content.
Investor/Analyst Meet
Filings containing a List of Attendees or Schedules of past/confirmed private institutional meetings. Excludes: General earnings calls.
Joint Ventures
Formation of a new separate legal entity with a partner.
Litigation & Notices
Material legal cases, arbitration awards, or significant tax/regulatory notices.
Mergers/Acquisitions
Structural transactions where the company acquires an external entity or merges with another. Excludes: SAST filings, open market share purchases, and internal group restructuring.
New Order
Winning/receiving specific commercial contracts or service agreements.
New Product
Launch of a new product line or service.
One Time Settlement (OTS)
Settlement of dues with banks or financial institutions.
Open Offer
Takeover code events where an acquirer offers to buy shares from the public.
Operational Disruption
Factory closures, trading suspensions, fires, strikes, or cyber-attacks.
Operational Update
Key performance metrics released outside formal results. Includes: press releases regarding financial performance (without full statutory statements), monthly business updates (sales numbers, AUM updates, order book updates).
Regulatory Actions
Actions/intervention by government or regulatory bodies affecting operations. Includes: USFDA updates (Form 483, Warning Letters), license suspensions, environmental clearances, PLI scheme approvals, anti-dumping duties.


Phase 3: Procedural Categories (The Noise)
Category
Definition
Procedural - Compliance
Trading window closures, Investor Grievance reports, Reg 74(5) certificates.
Procedural - Concall Schedule
Intimations of upcoming conference calls with date, time, and dial-in details.
Procedural - Corporate Details
Change of Address, Name Change, Website updates, Increase in Authorized Capital.
Procedural - Debt Administration
Routine confirmation of interest/principal payments on existing debt.
Procedural - Dividend
All announcements regarding dividend declaration, record dates, or payment.
Procedural - Encumbrance
Creation, modification, or release of promoter share pledges.
Procedural - ESOP
Allotment of shares to employees or ESOP scheme modifications.
Procedural - General
Loss of Share Certificates, Newspaper Publications, generic MOA/AOA adoption (regulatory alignment), or residual administrative noise.
Procedural - Governance
Board Meeting/EGM/Postal Ballot Notices (for Results or Routine business only), Scrutinizer reports, general resolutions.
Procedural - Investor Relations
Vague intimations of investor meetings without specific attendee lists.
Procedural - Leadership
Appointment/Resignation of Independent Directors, Company Secretary, or Auditors.
Procedural - Ratings
Reaffirmation of existing credit ratings or withdrawal of ratings.
Procedural - SAST
SAST (Substantial Acquisition of Shares and Takeovers) disclosures.


Output Format
Return your response in the following JSON format ONLY. No preamble, no explanation.
{
  "category": "Exact Category Name From Lists Above",
  "confidence": "high | medium | low"
}

high: Clear, unambiguous classification.
medium: Reasonable classification but another category was plausible.
low: Significant ambiguity; this is the best guess."""


class GemmaClassifier:
    """
    Classifier using Google's Gemma 3 27B model for corporate announcement classification.
    """
    
    def __init__(self, api_key: Optional[str] = None, rate_limit_delay: float = 2.0):
        """
        Initialize the Gemma classifier.
        
        Args:
            api_key: Google AI API key. If not provided, will use GEMMA_API_KEY env var.
            rate_limit_delay: Delay between API calls to avoid rate limiting.
        """
        self.api_key = api_key or os.getenv('GEMMA_API_KEY') or os.getenv('GEMINI_API_KEY')
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.client = None
        
        if not GENAI_AVAILABLE:
            logger.error("google-genai library not available")
            return
            
        if not self.api_key:
            logger.error("No API key provided for Gemma classifier")
            return
            
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("✅ Gemma 3 27B classifier initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemma classifier: {e}")
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def classify_text(self, text: str) -> Dict[str, Any]:
        """
        Classify announcement text using Gemma 3 27B.
        
        Args:
            text: The announcement text to classify.
            
        Returns:
            Dict with 'category' and 'confidence' keys.
        """
        if not self.client:
            logger.error("Gemma client not initialized")
            return {"category": "Error", "confidence": "low", "error": "Client not initialized"}
        
        try:
            self._rate_limit()
            
            full_prompt = f"{GEMMA_CLASSIFICATION_PROMPT}\n\nAnnouncement to classify:\n{text}"
            
            response = self.client.models.generate_content(
                model="gemma-3-27b-it",
                contents=full_prompt,
            )
            
            if not hasattr(response, 'text'):
                logger.error("Gemma response missing text attribute")
                return {"category": "Error", "confidence": "low", "error": "Invalid response format"}
            
            # Parse the JSON response
            response_text = response.text.strip()
            
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split('\n')
                # Remove first and last line (code block markers)
                response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            
            result = json.loads(response_text)
            
            logger.info(f"✅ Gemma classification: {result.get('category')} (confidence: {result.get('confidence')})")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemma JSON response: {e}")
            return {"category": "Error", "confidence": "low", "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Error in Gemma classification: {e}")
            return {"category": "Error", "confidence": "low", "error": str(e)}
    
    def classify_pdf(self, filepath: str) -> Dict[str, Any]:
        """
        Classify a PDF file using Gemma 3 27B.
        
        Args:
            filepath: Path to the PDF file.
            
        Returns:
            Dict with 'category' and 'confidence' keys.
        """
        if not self.client:
            logger.error("Gemma client not initialized")
            return {"category": "Error", "confidence": "low", "error": "Client not initialized"}
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return {"category": "Error", "confidence": "low", "error": "File not found"}
        
        uploaded_file = None
        try:
            self._rate_limit()
            
            # Upload the file to Gemini/Gemma API
            logger.info(f"📤 Uploading PDF to Gemma: {filepath}")
            uploaded_file = self.client.files.upload(file=filepath)
            
            # Generate classification
            logger.info("🤖 Generating Gemma classification...")
            response = self.client.models.generate_content(
                model="gemma-3-27b-it",
                contents=[GEMMA_CLASSIFICATION_PROMPT, uploaded_file],
            )
            
            if not hasattr(response, 'text'):
                logger.error("Gemma response missing text attribute")
                return {"category": "Error", "confidence": "low", "error": "Invalid response format"}
            
            # Parse the JSON response
            response_text = response.text.strip()
            
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            
            result = json.loads(response_text)
            
            logger.info(f"✅ Gemma PDF classification: {result.get('category')} (confidence: {result.get('confidence')})")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemma JSON response: {e}")
            return {"category": "Error", "confidence": "low", "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Error in Gemma PDF classification: {e}")
            return {"category": "Error", "confidence": "low", "error": str(e)}
        finally:
            # Cleanup uploaded file
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except Exception as e:
                    logger.warning(f"Failed to delete uploaded file: {e}")
    
    def classify_pdf_from_url(self, pdf_url: str) -> Dict[str, Any]:
        """
        Download and classify a PDF from URL using Gemma 3 27B.
        
        Args:
            pdf_url: URL of the PDF file.
            
        Returns:
            Dict with 'category' and 'confidence' keys.
        """
        if not pdf_url:
            return {"category": "Error", "confidence": "low", "error": "No URL provided"}
        
        # Download the PDF to a temp file
        filepath = None
        try:
            filename = pdf_url.split("/")[-1]
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, f"gemma_{uuid.uuid4()}_{filename}")
            
            logger.info(f"📥 Downloading PDF for Gemma classification: {pdf_url}")
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bseindia.com/",
                "Origin": "https://www.bseindia.com"
            }
            response = requests.get(pdf_url, timeout=30, headers=headers)
            response.raise_for_status()
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            logger.info(f"✅ Downloaded PDF to: {filepath} (size: {len(response.content)} bytes)")
            
            # Classify the PDF
            return self.classify_pdf(filepath)
            
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF: {e}")
            return {"category": "Error", "confidence": "low", "error": f"Download failed: {e}"}
        except Exception as e:
            logger.error(f"Error in Gemma PDF URL classification: {e}")
            return {"category": "Error", "confidence": "low", "error": str(e)}
        finally:
            # Cleanup temp file
            if filepath and os.path.exists(filepath):
                try:
                    os.unlink(filepath)
                except Exception:
                    pass


def store_classification_comparison(
    supabase,
    corp_id: Optional[str],
    pdf_url: str,
    pdf_hash: Optional[str],
    gemini_category: str,
    gemini_confidence: Optional[str],
    gemma_category: str,
    gemma_confidence: Optional[str],
    summary: Optional[str],
    isin: Optional[str] = None,
    symbol: Optional[str] = None,
    company_name: Optional[str] = None
) -> bool:
    """
    Store the classification comparison results in Supabase.
    
    Args:
        supabase: Supabase client instance.
        corp_id: UUID of the corporate filing.
        pdf_url: URL of the PDF file.
        pdf_hash: Hash of the PDF file.
        gemini_category: Category from Gemini model.
        gemini_confidence: Confidence from Gemini (if available).
        gemma_category: Category from Gemma 3 27B model.
        gemma_confidence: Confidence from Gemma 3 27B.
        summary: AI-generated summary.
        isin: Company ISIN code.
        symbol: Stock symbol.
        company_name: Company name.
        
    Returns:
        True if storage successful, False otherwise.
    """
    if not supabase:
        logger.error("Supabase client not provided")
        return False
    
    try:
        from datetime import datetime
        
        data = {
            "pdf_url": pdf_url,
            "pdf_hash": pdf_hash,
            "gemini_category": gemini_category,
            "gemini_confidence": gemini_confidence,
            "gemini_processed_at": datetime.utcnow().isoformat(),
            "gemma_category": gemma_category,
            "gemma_confidence": gemma_confidence,
            "gemma_processed_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "isin": isin,
            "symbol": symbol,
            "company_name": company_name
        }
        
        # Only add corp_id if it's a valid UUID
        if corp_id:
            data["corp_id"] = corp_id
        
        response = supabase.table('classification_comparison').insert(data).execute()
        
        if response.data:
            match_status = "✅ MATCH" if gemini_category.lower().strip() == gemma_category.lower().strip() else "❌ MISMATCH"
            logger.info(f"📊 Classification comparison stored: {match_status}")
            logger.info(f"   Gemini: {gemini_category} | Gemma: {gemma_category}")
            return True
        else:
            logger.error("Failed to store classification comparison - no data returned")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error storing classification comparison: {e}")
        return False


def run_parallel_classification(
    pdf_url: str,
    gemini_category: str,
    gemini_summary: Optional[str],
    supabase,
    corp_id: Optional[str] = None,
    pdf_hash: Optional[str] = None,
    isin: Optional[str] = None,
    symbol: Optional[str] = None,
    company_name: Optional[str] = None,
    gemma_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run Gemma classification in parallel with existing Gemini results and store comparison.
    
    This function is designed to be called after Gemini classification is complete,
    running Gemma classification and storing both results for comparison.
    
    Args:
        pdf_url: URL of the PDF file.
        gemini_category: Category already assigned by Gemini.
        gemini_summary: Summary already generated by Gemini.
        supabase: Supabase client instance.
        corp_id: UUID of the corporate filing.
        pdf_hash: Hash of the PDF file.
        isin: Company ISIN code.
        symbol: Stock symbol.
        company_name: Company name.
        gemma_api_key: Optional API key for Gemma (uses env var if not provided).
        
    Returns:
        Dict with comparison results.
    """
    result = {
        "gemini_category": gemini_category,
        "gemma_category": None,
        "gemma_confidence": None,
        "categories_match": None,
        "comparison_stored": False,
        "error": None
    }
    
    try:
        # Initialize Gemma classifier
        classifier = GemmaClassifier(api_key=gemma_api_key)
        
        if not classifier.client:
            result["error"] = "Gemma classifier not initialized"
            logger.error(result["error"])
            return result
        
        # Run Gemma classification
        gemma_result = classifier.classify_pdf_from_url(pdf_url)
        
        result["gemma_category"] = gemma_result.get("category", "Error")
        result["gemma_confidence"] = gemma_result.get("confidence", "low")
        
        if "error" in gemma_result:
            result["error"] = gemma_result["error"]
        
        # Check if categories match
        if result["gemma_category"] and result["gemma_category"] != "Error":
            result["categories_match"] = (
                gemini_category.lower().strip() == result["gemma_category"].lower().strip()
            )
        
        # Store comparison in Supabase
        stored = store_classification_comparison(
            supabase=supabase,
            corp_id=corp_id,
            pdf_url=pdf_url,
            pdf_hash=pdf_hash,
            gemini_category=gemini_category,
            gemini_confidence=None,  # Gemini doesn't provide confidence in current setup
            gemma_category=result["gemma_category"],
            gemma_confidence=result["gemma_confidence"],
            summary=gemini_summary,
            isin=isin,
            symbol=symbol,
            company_name=company_name
        )
        
        result["comparison_stored"] = stored
        
        return result
        
    except Exception as e:
        logger.error(f"Error in parallel classification: {e}")
        result["error"] = str(e)
        return result


async def run_parallel_classification_async(
    pdf_url: str,
    gemini_category: str,
    gemini_summary: Optional[str],
    supabase,
    corp_id: Optional[str] = None,
    pdf_hash: Optional[str] = None,
    isin: Optional[str] = None,
    symbol: Optional[str] = None,
    company_name: Optional[str] = None,
    gemma_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async version of run_parallel_classification for use in async contexts.
    
    Runs the Gemma classification in a thread pool to avoid blocking.
    """
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(
            executor,
            run_parallel_classification,
            pdf_url,
            gemini_category,
            gemini_summary,
            supabase,
            corp_id,
            pdf_hash,
            isin,
            symbol,
            company_name,
            gemma_api_key
        )
    
    return result


# Utility function for batch comparison processing
def process_batch_comparison(
    supabase,
    limit: int = 100,
    gemma_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a batch of existing announcements that don't have Gemma classification yet.
    
    This can be used to backfill Gemma classifications for historical announcements.
    
    Args:
        supabase: Supabase client instance.
        limit: Maximum number of announcements to process.
        gemma_api_key: Optional API key for Gemma.
        
    Returns:
        Dict with batch processing statistics.
    """
    stats = {
        "processed": 0,
        "success": 0,
        "errors": 0,
        "matches": 0,
        "mismatches": 0
    }
    
    try:
        # Get announcements that haven't been compared yet
        existing_comparisons = supabase.table('classification_comparison')\
            .select('corp_id')\
            .execute()
        
        compared_corp_ids = set(row['corp_id'] for row in (existing_comparisons.data or []))
        
        # Get announcements with PDF URLs that haven't been compared
        announcements = supabase.table('corporatefilings')\
            .select('corp_id, category, ai_summary, fileurl, isin, symbol, companyname, pdf_hash')\
            .not_.is_('fileurl', 'null')\
            .limit(limit)\
            .execute()
        
        if not announcements.data:
            logger.info("No announcements to process")
            return stats
        
        classifier = GemmaClassifier(api_key=gemma_api_key)
        
        for ann in announcements.data:
            if ann['corp_id'] in compared_corp_ids:
                continue
            
            stats["processed"] += 1
            
            try:
                result = run_parallel_classification(
                    pdf_url=ann.get('fileurl'),
                    gemini_category=ann.get('category', 'Unknown'),
                    gemini_summary=ann.get('ai_summary'),
                    supabase=supabase,
                    corp_id=ann.get('corp_id'),
                    pdf_hash=ann.get('pdf_hash'),
                    isin=ann.get('isin'),
                    symbol=ann.get('symbol'),
                    company_name=ann.get('companyname'),
                    gemma_api_key=gemma_api_key
                )
                
                if result.get("comparison_stored"):
                    stats["success"] += 1
                    if result.get("categories_match"):
                        stats["matches"] += 1
                    else:
                        stats["mismatches"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing {ann.get('corp_id')}: {e}")
                stats["errors"] += 1
            
            # Small delay between requests
            time.sleep(2)
        
        logger.info(f"📊 Batch comparison complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error in batch comparison: {e}")
        stats["errors"] += 1
        return stats


if __name__ == "__main__":
    # Test the classifier
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Test with a sample text
    classifier = GemmaClassifier()
    
    if classifier.client:
        test_text = """
        The Board of Directors of XYZ Ltd. has approved the issuance of 
        1,00,00,000 equity shares of Rs. 10 each at a premium of Rs. 90 per share 
        on a preferential basis to qualified institutional buyers.
        """
        
        result = classifier.classify_text(test_text)
        print(f"Classification result: {result}")
    else:
        print("Gemma classifier could not be initialized. Check your API key.")
