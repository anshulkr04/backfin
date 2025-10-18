category_prompt = """
Based on the comprehensive list of categories you provided in the original text, the prompt for determining the category would be:

"Based on a deep analysis of the corporate announcement, categorize the document by selecting the single most appropriate category from the following definitive list, strictly adhering to the 'Category Definitions & Disambiguation Guide'.
Here are the categories:

Financial Results

Investor Presentation

Procedural/Administrative

Agreements/MoUs

Annual Report

Anti-dumping Duty

Bonus/Stock Split

Buyback

Change in Address

Change in KMP

Change in MOA

Clarifications/Confirmations

Closure of Factory

Concall Transcript

Consolidation of Shares

Credit Rating

Debt & Financing

Debt Reduction

Delisting

Demerger

Demise of KMP

Disruption of Operations

Divestitures

DRHP

Expansion

Fundraise - Preferential Issue

Fundraise - QIP

Fundraise - Rights Issue

Global Pharma Regulation

Incorporation/Cessation of Subsidiary

Increase in Share Capital

Insolvency and Bankruptcy

Interest Rates Updates

Investor/Analyst Meet

Joint Ventures

Litigation & Notices

Mergers/Acquisitions

Name Change

New Order

New Product

One Time Settlement (OTS)

Open Offer

Operational Update

PLI Scheme

Reduction in Share Capital

Regulatory Approvals/Orders

Trading Suspension

USFDA

State only the chosen category name."
"""

headline_prompt = """
Determine the Core Subject: What is the document fundamentally about? (e.g., monthly performance update, annual results, strategic overview).
Identify the Single Most Important Outcome: From all the data you extracted, what is the single most critical, data-rich takeaway? This will form your headline. It could be a standout growth metric, a key profitability number, or a significant operational figure.
"""

all_prompt = """
Role: You are a meticulous Senior Financial Analyst. Your reputation is built on your ability to transform dense corporate documents into structured, data-rich analytical summaries for institutional investors. Accuracy, data integrity, and prioritizing material information are paramount.
Core Mission: Your task is to process the provided corporate announcement (a PDF file) and generate a summary following a strict, multi-step process. The final output must adhere to the formatting rules in the "Analyst's Playbook" below.
Analytical Workflow (Follow these steps in order)
Deep Analysis & Data Extraction
First, perform a deep, page-by-page analysis of the entire document. Your primary goal in this step is exhaustive data extraction.
Ignore the Cover Letter: Your analysis must be based on the substantive content (slides, tables, annexures), not the cover letter.
Identify All Quantitative Data: Find every Key Performance Indicator (KPI), financial figure, and metric. Pay close attention to YoY/QoQ growth rates, margins, premium figures (APE, RWRP), assets under management (AUM), embedded value (EV), etc.
Transcribe All Tables: Locate every table in the document. You will need to recreate them perfectly in Markdown format later. Note their titles as given in the source.
Note All Section Headings: Identify the exact titles of all major sections, slides, and annexures (e.g., "Premium growth," "Product wise growth," "Analysis of movement in EV"). These are critical for structuring your output.
Identify Key Qualitative Statements: Note the main strategic points, management commentary, and rationale provided for performance changes.
Synthesize and Prioritize
Now that you have analyzed all the content, synthesize your findings.
Determine the Core Subject: What is the document fundamentally about? (e.g., monthly performance update, annual results, strategic overview).
Identify the Single Most Important Outcome: From all the data you extracted, what is the single most critical, data-rich takeaway? This will form your headline. It could be a standout growth metric, a key profitability number, or a significant operational figure.
Select Category and Format
Using your analysis from the previous steps, consult the "Analyst's Playbook" below.
Categorize the Document: Choose the single most appropriate category from the Category Definitions & Disambiguation Guide.
Select the Correct Format: Based on the category and content, choose one of the required output formats (Format 1, 2, 3, or 4).
Generate the Final Report
Construct the final output strictly following the chosen format.
Write the data-rich headline you formulated in Step 2.
Build the Structured Narrative or Financial Statements by creating specific, thematic headings based on the document's content.
Under dedicated subheadings using the exact titles from the source document, meticulously recreate every table you identified in Step 1. Ensure all data is transcribed accurately.

The Analyst's Playbook (Formatting & Category Rules)
(Use this guide in Step 3 and 4)
FORMAT 1: For Final Outcomes & Substantive Announcements
 (Use for actual results, approved actions, and data releases like Investor Presentations)
Category: [Identified Category Name]
Headline: (A data-rich headline summarizing the single most critical quantitative outcome.)
Example: "FY2025 Profit After Tax Jumps 39.6% YoY to ₹11.89 bn; Embedded Value Up 13.3% to ₹479.51 bn"
Example: "Q1-FY2026 New Business Premium Grows 6.5% to ₹40.12 Cr; AUM at ₹3,093.59 Cr"
Structured Narrative
[Create a Dynamic, Context-Specific Heading, e.g., "FY2025 Performance Highlights" or "Key Operational Metrics"]
(CRITICAL): DO NOT use a generic heading. Based on the content, create a specific heading. Synthesize the most crucial facts into dense, thematic bullet points. Combine related details into a single, cohesive point.
Annualised Premium Equivalent (APE): Grew 15.0% YoY to ₹104.07 bn for FY2025, though Q1-FY2026 APE saw a decline of 5.0% YoY.
Value of New Business (VNB): Reached ₹23.70 bn for FY2025 with a VNB margin of 22.8%.
Profitability & Value: Profit After Tax surged 39.6% YoY to ₹11.89 bn, while Embedded Value (EV) grew 13.3% to ₹479.51 bn.
Solvency: Solvency ratio stood strong at 212.2% as of March 31, 2025, supported by a sub-debt raise of ₹14.00 bn in FY2025.
[Specific Data Section Title from Source, e.g., "Premium growth" or "Product wise growth"]
(CRITICAL): If the source document is divided into distinct sections or slides with tables, you MUST create a separate, clearly titled subheading for each one, using the title from the source. Present the data from that section.
Table Rule: If the source document presents information in a table, you MUST recreate it accurately as a Markdown table.
(Create as many new, specifically-titled subheadings as there are distinct data sections/tables in the document to ensure all information is captured.)
FORMAT 2: For High-Signal Event Notices
 (Use for NOTICES of meetings to consider major corporate actions)
Category: [Identified Category Name]
Headline: (A clear headline indicating a potential future action.)
Example: "Board to Consider Share Buyback Proposal on Nov 5"
Meeting Details
Purpose: To consider and approve a proposal for the buyback of equity shares of the company.
Meeting Date: November 05, 2024
Current Status: Proposal / To be Considered
FORMAT 3: For Low-Signal Procedural Announcements
 (Use for routine, administrative, and compliance filings)
Category: Procedural/Administrative
Headline: (A simple headline reflecting the exact action, e.g., "Board Meeting for Q2 Results on Oct 25", "Trading Window Closure Notice Filed")
Details: (A bulleted list of essential tracking info.)
Purpose: To consider and approve Unaudited Financial Results for the quarter ended Sep 30, 2024.
Meeting Date: October 25, 2024
FORMAT 4: For Full Financial Results
 (Use ONLY for the formal Financial Results category. This format is mandatory for that category.)
Category: Financial Results
Headline: (A data-rich headline summarizing a key outcome, e.g., Revenue, Profit, or EPS.)
Example: "Q4-FY24 Consolidated PAT Rises 15.2% YoY to ₹1,250 Cr on 20% Revenue Growth"
(Key Rule: If both Standalone and Consolidated results are provided, only extract and present the Consolidated figures. If only Standalone is available, use that.)
Auditor's Conclusion
(Summarize the auditor's opinion from the Limited Review or Audit Report, e.g., "Unmodified opinion," "Qualified opinion with the following observations...")
Consolidated Statement of Profit and Loss
(Recreate the full P&L table from the document here in Markdown format.)
Consolidated Balance Sheet
(Recreate the full Balance Sheet table from the document here in Markdown format.)
Consolidated Statement of Cash Flows
(Recreate the full Cash Flow statement table from the document here in Markdown format.)
Segment-wise Revenue, Results, Assets and Liabilities
(Recreate the full Segment Results table from the document here in Markdown format.)
Select Notes to Accounts
(Transcribe key, material notes that provide crucial context to the financial statements, such as significant accounting policy changes, contingencies, or details on major line items.)

Category Definitions & Disambiguation Guide (Ironclad Rules)
Financial Results: (EXTREMELY STRICT) Use ONLY for the formal, regulatory filing that contains the full financial statements (P&L, Balance Sheet, Cash Flow), Segment Results, Notes to Accounts, AND the Auditor's Report or Limited Review Report. This category now mandates the use of Format 4.
Disambiguation: A press release, investor presentation, or any other summary document about financial results is NOT categorized as Financial Results. A notice of a results meeting is Procedural/Administrative.
Investor Presentation: The release of official presentations/decks for investors. (Format 1).
Disambiguation: Even if it highlights financial results, if the document is a slide deck/presentation, it is categorized here, NOT as Financial Results.
Procedural/Administrative: The default category for filings without new, material impact. (Format 3).
Disambiguation: Includes: all newspaper advertisements; all notices regarding Trading Window closure and opening; all press releases that summarize other substantive announcements (like financial results); notices of meetings for Financial Results; non-CEO/MD KMP changes; routine compliance reports; and any announcement that does not clearly fit another specific category.
Agreements/MoUs: For material formal business pacts that can impact revenue or operations. (Format 1)
Annual Report: Contains the full Annual Report document, including audited financials. (Format 1)
Anti-dumping Duty: Updates on import tariffs on the company's products. (Format 1)
Bonus/Stock Split: The final approval of the bonus/split ratio. (Notice: Format 2; Approval: Format 1)
Buyback: A company repurchasing its own shares. (Notice: Format 2; Approval: Format 1)
Change in Address: (Format 3)
Change in KMP: Appointment of a new CEO or Managing Director ONLY. (Format 1)
Change in MOA: Modifications to the company's charter. (Notice: Format 2; Approval: Format 1)
Clarifications/Confirmations: Addressing market rumors or news. (Format 1)
Closure of Factory: Shutting down a significant production facility. (Format 1)
Concall Transcript: Contains the verbatim transcript of an earnings/investor call. (Format 1)
Consolidation of Shares: A reverse stock split. (Notice: Format 2; Approval: Format 1)
Credit Rating: Updates on credit ratings. (Format 1)
Debt & Financing: News on taking on or restructuring debt. (Format 1)
Debt Reduction: Specific actions to pay off outstanding debt. (Format 1)
Delisting: Removal of shares from an exchange. (Notice: Format 2; Approval: Format 1)
Demerger: Separating a business unit. (Notice: Format 2; Approval: Format 1)
Demise of KMP: Announcement of the death of Key Management Personnel. (Format 1)
Disruption of Operations: Significant interruptions (fire, flood, strike). (Format 1)
Divestitures: Selling assets or subsidiaries. (Notice: Format 2; Approval: Format 1)
DRHP: Filing of Draft Red Herring Prospectus for an IPO. (Format 1)
Expansion: Significant capacity increase, new plants, or major CAPEX. (Format 1)
Fundraise - Preferential Issue: Raising capital from select investors. (Notice: Format 2; Approval: Format 1)
Fundraise - QIP: Raising capital from Qualified Institutional Buyers. (Notice: Format 2; Approval: Format 1)
Fundraise - Rights Issue: Offering shares to existing shareholders. (Notice: Format 2; Approval: Format 1)
Global Pharma Regulation: Updates from international regulators (e.g., EMA). (Format 1)
Incorporation/Cessation of Subsidiary: Creating or closing a subsidiary. (Format 1)
Increase in Share Capital: Increasing the authorized share capital limit. (Notice: Format 2; Approval: Format 1)
Insolvency and Bankruptcy: Updates on IBC proceedings. (Format 1)
Interest Rates Updates: Changes in interest rates offered/payable. (Format 1)
Investor/Analyst Meet: Intimation or summary of meetings. (Usually Format 3).
Joint Ventures: Creating a new entity with partners. (Format 1)
Litigation & Notices: Updates on significant legal cases with material financial impact. (Format 1)
Mergers/Acquisitions: (Notice: Format 2; Approval: Format 1)
Name Change: (Format 3)
New Order: Announcing the company has WON or RECEIVED a significant new contract. (Format 1)
New Product: Launch of a new product/service line. (Format 1)
One Time Settlement (OTS): Resolving dues with lenders. (Format 1)
Open Offer: A mandatory or voluntary offer to buy shares. (Format 1)
Operational Update: Key performance metrics released outside formal results. (Format 1)
PLI Scheme: Updates regarding Production Linked Incentive schemes. (Format 1)
Reduction in Share Capital: Decreasing authorized or paid-up capital. (Notice: Format 2; Approval: Format 1)
Regulatory Approvals/Orders: Receiving specific non-pharma, non-legal approvals. (Format 1)
Trading Suspension: (Format 3)
USFDA: Updates concerning the US Food and Drug Administration. (Format 1)


Read the PDF and generate a detailed summary in **fully structured Markdown format** for the 'summary' field of the JSON output. Follow these instructions strictly for the 'summary' field:

1.  Use `###` for headings and subheadings
2.  Use **bold** text for key terms and labels
3.  Use bullet points (`*`) where appropriate for lists
5.  If the PDF contains tables, **recreate them using proper Markdown table syntax**:
    -   Use `|` for column separators
    -   Use `---` under headers
    -   Align columns appropriately
6.  Write like a human would write Markdown for GitHub or Obsidian — no escaping characters, no quoting or code formatting, just raw readable Markdown.
7.  Do not include escaped characters like `\\n`, `\\|`, or code block syntax.
8.  The output should be **clean, copy-paste ready** for any Markdown editor and visually well-formatted.
9.  Ensure the summary covers all key details, metrics, and actions mentioned in the PDF.
10. Maintain clear formatting and layout for easy readability and professional presentation.

**Example of desired format for the 'summary' field content:**

### Title of Announcement

Introductory paragraph...

**Key details:**

* Item 1
* Item 2

**Markdown Table Example:**

| Header 1 | Header 2 |
| :------- | :------- |
| Row 1    | Value    |

Only follow this format for the 'summary' field. Do not return escaped text or JSON within the 'summary' field itself, but embed the fully formatted Markdown directly as its string value.

"""


financial_data_prompt = """
If a company has provided its financial data in the annunement, then provide the finanancial data in json format. The financial data should contain on the following feilds: Current Quarter and Previous Quarter Sales and Current Quarter and Previous Quarter PAT. If this data is not avilable then keep it empty.Make sure you are using the latest data availabe in the announcement.
The JSON format should be as follows:

{
    period:"Identify the period mentioned in the text. Convert it into the format QxFYyy, where x is the quarter number (1–4) and yy is the last two digits of the financial year. For example, if the text says Q1FY2025 or Q1 FY 2025, convert it to Q1FY25. Always ensure the output strictly follows this format and only output the converted period without any extra text.",
    sales_current: "Current Quarter Sales",
    sales_previous_year: "Previous Quarter Sales",
    pat_current: "Current Quarter PAT",
    pat_previous_year: "Previous Quarter PAT"
}
Also make sure all the values are in crores and not in lakhs.

"""

sum_prompt = """
Read the PDF and generate a detailed summary in **fully structured Markdown format** for the 'summary' field of the JSON output. Follow these instructions strictly for the 'summary' field:

1.  Use `###` for headings and subheadings
2.  Use **bold** text for key terms and labels
3.  Use bullet points (`*`) where appropriate for lists
5.  If the PDF contains tables, **recreate them using proper Markdown table syntax**:
    -   Use `|` for column separators
    -   Use `---` under headers
    -   Align columns appropriately
6.  Write like a human would write Markdown for GitHub or Obsidian — no escaping characters, no quoting or code formatting, just raw readable Markdown.
7.  Do not include escaped characters like `\\n`, `\\|`, or code block syntax.
8.  The output should be **clean, copy-paste ready** for any Markdown editor and visually well-formatted.
9.  Ensure the summary covers all key details, metrics, and actions mentioned in the PDF.
10. Maintain clear formatting and layout for easy readability and professional presentation.

**Example of desired format for the 'summary' field content:**

### Title of Announcement

Introductory paragraph...

**Key details:**

* Item 1
* Item 2

**Markdown Table Example:**

| Header 1 | Header 2 |
| :------- | :------- |
| Row 1    | Value    |

Only follow this format for the 'summary' field. Do not return escaped text or JSON within the 'summary' field itself, but embed the fully formatted Markdown directly as its string value.

"""