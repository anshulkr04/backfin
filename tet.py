def check_for_negative_keywords(summary):
    """Check for negative keywords in the announcements"""
    if not isinstance(summary, str):
        return True  # Treat non-string values as containing negative keywords
        
    negative_keywords = [
        "Trading Window", "Compliance Report", "Advertisement(s)", "Advertisement", "Public Announcement",
        "Share Certificate(s)", "Share Certificate", "Depositories and Participants", "Depository and Participant",
        "Depository and Participant", "Depository and Participants", "74(5)", "XBRL", "Newspaper Publication",
        "Published in the Newspapers", "Clippings", "Book Closure", "Change in Company Secretary/Compliance Officer",
        "Record Date","Code of Conduct","Cessation","Deviation","Declared Interim Dividend","IEPF","Investor Education","Registrar & Share Transfer Agent",
        "Registrar and Share Transfer Agent","Scrutinizers report","Utilisation of Funds","Postal Ballot","Defaults on Payment of Interest",
        "Newspaper Publication","Sustainability Report","Sustainability Reporting","Trading Plan","Letter of Confirmation","Forfeiture/Cancellation","Price movement",
        "Spurt","Grievance Redressal","Monitoring Agency","Regulation 57",
    ]

    special_keywords = [
        "Board", "Outcome", "General Updates",
    ]

    for keyword in special_keywords:
        if keyword.lower() in summary.lower():
            print(f"Found special keyword '{keyword}' in summary.")
            return False
            
    for keyword in negative_keywords:
        if keyword.lower() in summary.lower():
            print(f"Found negative keyword '{keyword}' in summary.")
            return True
            
    return False

sum1 = "Announcement under Regulation 30 (LODR)-Newspaper Publication"

sum2 = "News Paper Publication of Unaudited Financial Result for the Second Quarter and Half Year ended on 30rh September, 2025.News Paper Publication of Unaudited Financial Result for the Second Quarter and Half Year ended on 30rh September, 2025."

print(check_for_negative_keywords(sum1))  # Expected: True
print(check_for_negative_keywords(sum2))  # Expected: FalseS