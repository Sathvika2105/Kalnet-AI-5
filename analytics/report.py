from collections import Counter

# MOCK DATA
MOCK_DATA = [
    {"lead_id": "L1", "name": "Admin", "email": "admin@stxaviers.edu", "company": "St Xaviers", "email_sent_at": "2026-04-20", "sequence_step": 1, "replied": True, "tier": 1, "subject_line": "AI tools for your classrooms"},
    {"lead_id": "L2", "name": "Principal", "email": "principal@dps.edu", "company": "DPS", "email_sent_at": "2026-04-20", "sequence_step": 1, "replied": False, "tier": 1, "subject_line": "Quick question regarding your IT stack"},
    {"lead_id": "L3", "name": "Hello", "email": "hello@greenwood.edu", "company": "Greenwood", "email_sent_at": "2026-04-20", "sequence_step": 1, "replied": True, "tier": 2, "subject_line": "AI tools for your classrooms"},
    {"lead_id": "L4", "name": "IT", "email": "it@oakridge.edu", "company": "Oakridge", "email_sent_at": "2026-04-20", "sequence_step": 1, "replied": False, "tier": 1, "subject_line": "Quick question regarding your IT stack"},
    {"lead_id": "L5", "name": "Director", "email": "director@valleyschool.edu", "company": "Valley School", "email_sent_at": "2026-04-20", "sequence_step": 1, "replied": True, "tier": 2, "subject_line": "Improving student outcomes with AI"},
    {"lead_id": "L6", "name": "Contact", "email": "contact@newera.edu", "company": "New Era", "email_sent_at": "", "sequence_step": 0, "replied": False, "tier": 2, "subject_line": ""}, # Not sent yet
]

# CORE ANALYTICS LOGIC
def generate_metrics(data):
    total_sent = 0
    total_replies = 0
    tier_counts = Counter()
    subject_replies = Counter()
    subject_sends = Counter()

    for row in data:
        # checks if 'email_sent_at' contains a date string
        if row.get("email_sent_at"):
            total_sent += 1
            tier_counts[row.get("tier")] += 1
            
            subject = row.get("subject_line")
            if subject:
                subject_sends[subject] += 1

            # checks if 'replied' is exactly True
            if row.get("replied") is True:
                total_replies += 1
                if subject:
                    subject_replies[subject] += 1

    # overall reply rate safely
    reply_rate = (total_replies / total_sent * 100) if total_sent > 0 else 0.0

    # reply rates per subject line for ranking
    best_subjects = []
    for sub, sends in subject_sends.items():
        replies = subject_replies.get(sub, 0)
        rate = (replies / sends * 100)
        best_subjects.append({"subject": sub, "rate": rate, "replies": replies})
    
    # sort subjects by highest reply rate, then total replies
    best_subjects.sort(key=lambda x: (x["rate"], x["replies"]), reverse=True)

    return {
        "total_sent": total_sent,
        "total_replies": total_replies,
        "reply_rate": round(reply_rate, 2),
        "tier_breakdown": dict(tier_counts),
        "best_subjects": best_subjects
    }

# TERMINAL REPORT FORMATTING
def print_report(metrics):
    """Prints a cleanly formatted report to the console."""
    print("KALNET AI-5 OUTREACH: ANALYTICS REPORT")
    
    print(f"\n[ OVERVIEW ]")
    print(f"Total Emails Sent:    {metrics['total_sent']}") 
    print(f"Total Replies:        {metrics['total_replies']}")
    print(f"Overall Reply Rate:   {metrics['reply_rate']}%") 

    print(f"\n[ TIER BREAKDOWN ]") 
    for tier, count in sorted(metrics['tier_breakdown'].items()):
        print(f"Tier {tier}: {count} emails sent")

    print(f"\n[ TOP PERFORMING SUBJECT LINES ]") 
    if not metrics['best_subjects']:
        print("No subject line data available yet.")
    else:
        for i, item in enumerate(metrics['best_subjects'][:3], 1):
            print(f"{i}. \"{item['subject']}\"")
            print(f"   Rate: {item['rate']:.1f}% ({item['replies']} replies)")

if __name__ == "__main__":
    print("Fetching data and calculating metrics...\n")
    report_data = generate_metrics(MOCK_DATA)
    print_report(report_data)