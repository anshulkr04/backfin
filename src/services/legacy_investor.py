from invanl import createInvestor


investors = [
  {
    "Investor_Name": "Radhakishan Shivkishan Damani",
    "Aliases": [
      "Radhakishan Damani",
      "R.K. Damani",
      "Bright Star Investments Private Limited",
      "Derive Trading and Resorts Private Limited",
      "Derive Investments",
      "Damani Estate and Finance",
      "Gulmohar Trust",
      "Karnikar Trust",
      "Bottle Palm Trust",
      "Royal Palm Trust",
      "Mountain Glory Trust"
    ]
  },
  {
    "Investor_Name": "Rakesh Jhunjhunwala Estate",
    "Aliases": [
      "Rakesh Jhunjhunwala",
      "Rakesh Radheyshyam Jhunjhunwala",
      "Rekha Jhunjhunwala",
      "Rekha Rakesh Jhunjhunwala",
      "Rare Enterprises",
      "Estate of Late Rakesh Jhunjhunwala",
      "Aryaman Jhunjhunwala Trust",
      "Aryavir Jhunjhunwala Trust",
      "Nistha Jhunjhunwala Trust"
    ]
  },
  {
    "Investor_Name": "Mukul Mahavir Prasad Agrawal",
    "Aliases": [
      "Mukul Mahavir Agrawal",
      "Mukul Agrawal",
      "Mukul Mahavir Prasad Agrawal",
      "Param Capital Research Pvt. Ltd",
      "Permanent Technologies Pvt. Ltd"
    ]
  },
  {
    "Investor_Name": "Shiv Nadar",
    "Aliases": [
      "Shiv Nadar",
      "HCL Corporation",
      "Vama Sundari Investments Delhi"
    ]
  },
  {
    "Investor_Name": "Ashish Rameshchandra Kacholia",
    "Aliases": [
      "Ashish Kacholia",
      "Ashish Rameshchandra Kacholia",
      "ASHISH RAMESHCHANDRA KACHOLIA",
      "Lucky Securities Inc.",
      "Lucky Investment Managers Private Limited",
      "Bengal Finance and Investment Pvt Ltd"
    ]
  },
  {
    "Investor_Name": "Madhusudan Kela",
    "Aliases": [
      "Madhu Kela",
      "Madhusudan Kela",
      "MK Ventures",
      "Invexa Capital",
      "MKVentures Capital Ltd"
    ]
  },
  {
    "Investor_Name": "Anil Kumar Goel",
    "Aliases": [
      "Anil Kumar Goel",
      "Anil Kumar Goel & Associates",
      "Anil Kumar Goel and Associates"
    ]
  },
  {
    "Investor_Name": "Nemish S Shah",
    "Aliases": [
      "Nemish S Shah",
      "Nemish Shah",
      "ENAM Holdings",
      "ENAM Securities"
    ]
  },
  {
    "Investor_Name": "Vijay Kishanlal Kedia",
    "Aliases": [
      "Vijay Kedia",
      "Vijay Kishanlal Kedia",
      "Dr. Vijay Kedia",
      "Dr. Vijay Kishanlal Kedia",
      "Kedia Securities Private Limited",
      "Vijay and Manju Kedia Foundation"
    ]
  },
  {
    "Investor_Name": "Sanjay Dangi",
    "Aliases": [
      "Sanjay Dangi",
      "Authum Investment & Infrastructure Limited",
      "Pacific Corporate Services",
      "Dangi Group"
    ]
  },
  {
    "Investor_Name": "Sunil Singhania",
    "Aliases": [
      "Sunil Singhania",
      "Abakkus Asset Manager LLP"
    ]
  },
  {
    "Investor_Name": "Kenneth Andrade",
    "Aliases": [
      "Kenneth Andrade",
      "Old Bridge Capital Management Private Limited",
      "Old Bridge Mutual Fund"
    ]
  },
  {
    "Investor_Name": "Prashant Khemka",
    "Aliases": [
      "Prashant Khemka",
      "White Oak Capital Management"
    ]
  },
  {
    "Investor_Name": "Saurabh Mukherjea",
    "Aliases": [
      "Saurabh Mukherjea",
      "Marcellus Investment Managers"
    ]
  },
  {
    "Investor_Name": "Samir Arora",
    "Aliases": [
      "Samir Arora",
      "Helios Capital Management Pte Ltd",
      "Helios Capital Asset Management"
    ]
  },
  {
    "Investor_Name": "Akash Prakash",
    "Aliases": [
      "Akash Prakash",
      "Amansa Capital Pte Ltd",
      "Amansa Holdings Private Limited"
    ]
  },
  {
    "Investor_Name": "Porinju V Veliyath",
    "Aliases": [
      "Porinju V Veliyath",
      "Porinju Veliyath",
      "Equity Intelligence India Private Limited"
    ]
  },
  {
    "Investor_Name": "Shyam Sekhar",
    "Aliases": [
      "Shyam Sekhar",
      "iThought Financial Consulting LLP"
    ]
  },
  {
    "Investor_Name": "Rajeev Thakkar",
    "Aliases": [
      "Rajeev Thakkar",
      "PPFAS Mutual Fund",
      "PPFAS Asset Management"
    ]
  },
  {
    "Investor_Name": "Manish Bhandari",
    "Aliases": [
      "Manish Bhandari",
      "Vallum Capital Advisors Private Limited"
    ]
  },
  {
    "Investor_Name": "Dolly Khanna",
    "Aliases": [
      "Dolly Khanna",
      "Dolly Rajiv Khanna",
      "Mrs. Dolly Khanna"
    ]
  },
  {
    "Investor_Name": "Vikas Khemani",
    "Aliases": [
      "Vikas Khemani",
      "Carnelian Asset Advisors",
      "Carnelian Capital"
    ]
  },
  {
    "Investor_Name": "Bharat Shah",
    "Aliases": [
      "Bharat Shah",
      "ASK Investment Managers",
      "ASK Group"
    ]
  },
  {
    "Investor_Name": "Ramesh Damani",
    "Aliases": [
      "Ramesh Damani",
      "Damani Finance Pvt. Ltd"
    ]
  },
  {
    "Investor_Name": "Shankar Sharma",
    "Aliases": [
      "Shankar Sharma",
      "GQuant Investech",
      "First Global"
    ]
  },
  {
    "Investor_Name": "Ajay Piramal",
    "Aliases": [
      "Ajay Piramal",
      "Piramal Enterprises Limited",
      "Piramal Finance Limited",
      "India Resurgence Fund"
    ]
  },
  {
    "Investor_Name": "Nirmal Jain",
    "Aliases": [
      "Nirmal Jain",
      "IIFL Holdings Limited",
      "IIFL Finance",
      "360 ONE",
      "5paisa.com"
    ]
  },
  {
    "Investor_Name": "Arun Bharat Ram",
    "Aliases": [
      "Arun Bharat Ram",
      "SRF Limited",
      "Kama Holdings Limited"
    ]
  },
  {
    "Investor_Name": "Sameer Gehlaut",
    "Aliases": [
      "Sameer Gehlaut",
      "Indiabulls Financial Services",
      "Dhani Services Ltd"
    ]
  },
  {
    "Investor_Name": "Anand Jain",
    "Aliases": [
      "Anand Jain",
      "Jai Corp Limited",
      "Urban Infrastructure Venture Capital"
    ]
  },
  {
    "Investor_Name": "Kalpraj Dharamshi",
    "Aliases": [
      "Kalpraj Dharamshi",
      "Dharamshi Securities Pvt. Ltd.",
      "Minosha India Ltd"
    ]
  },
  {
    "Investor_Name": "Satyanarayan Kabra",
    "Aliases": [
      "Satyanarayan Kabra",
      "Kabra Family"
    ]
  },
  {
    "Investor_Name": "Deepak Shenoy",
    "Aliases": [
      "Deepak Shenoy",
      "Capitalmind Wealth PMS",
      "Capitalmind Mutual Fund"
    ]
  },
  {
    "Investor_Name": "Amit Goela",
    "Aliases": [
      "Amit Goela",
      "Rare Enterprises",
      "Rare Shares & Stock Pvt. Ltd"
    ]
  },
  {
    "Investor_Name": "Manish Gunwani",
    "Aliases": [
      "Manish Gunwani",
      "Bandhan AMC Limited"
    ]
  },
  {
    "Investor_Name": "Anish Tawakley",
    "Aliases": [
      "Anish Tawakley",
      "ICICI Prudential Asset Management"
    ]
  },
  {
    "Investor_Name": "Mohnish Pabrai",
    "Aliases": [
      "Mohnish Pabrai",
      "Pabrai Investment Funds",
      "Dhandho Funds",
      "Pabrai Wagons Fund"
    ]
  },
  {
    "Investor_Name": "Pulak Prasad",
    "Aliases": [
      "Pulak Prasad",
      "Nalanda Capital Pte Ltd",
      "Nalanda India Fund Limited"
    ]
  },
  {
    "Investor_Name": "Madhav Bhatkuly",
    "Aliases": [
      "Madhav Bhatkuly",
      "New Horizon Financial Research",
      "New Horizon Opportunities Master Fund"
    ]
  },
  {
    "Investor_Name": "LIC",
    "Aliases": [
      "LIC",
      "LIC of India",
      "L I C of India",
      "Life Insurance Corporation of India"
    ]
  },
  {
    "Investor_Name": "Raamdeo Agrawal",
    "Aliases": [
      "Raamdeo Agrawal",
      "Motilal Oswal Financial Services"
    ]
  },
  {
    "Investor_Name": "Basant Maheshwari",
    "Aliases": [
      "Basant Maheshwari",
      "Basant Maheshwari Wealth Advisers LLP"
    ]
  },
  {
    "Investor_Name": "Manoj Bahety",
    "Aliases": [
      "Manoj Bahety",
      "Carnelian Asset Advisors"
    ]
  },
  {
    "Investor_Name": "Pradeep Gupta",
    "Aliases": [
      "Pradeep Gupta",
      "Anand Rathi Financial Services Limited"
    ]
  }
]


for inv in investors:
    investor_name = inv["Investor_Name"]
    aliases = inv["Aliases"]
    
    # Create the investor with aliases
    createInvestor(investor_name, aliases, "individual")
    print(f"Created investor: {investor_name} with aliases: {aliases}")