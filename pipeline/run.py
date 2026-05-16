"""
/pipeline/run.py -- Main Pipeline Orchestrator
Author: Sathvika2105
Module: AI-5 Email Automation Pipeline
Responsibility: Orchestrate the entire email automation workflow

Workflow:
  1. Load all leads from Google Sheets
  2. Check for new replies to previous emails
  3. Determine which leads are due for follow-up emails
  4. Send emails to applicable leads
  5. Update Google Sheets with send status
  6. Generate analytics report
  
Run:
  python pipeline/run.py
"""

import os
import sys
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import pipeline modules
from pipeline import send_email, sequence, sheets, check_replies, unsubscribe
from analytics import report

# ──────────────────────────────────────────────
# Load environment variables
# ──────────────────────────────────────────────
load_dotenv()

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
DELAY_BETWEEN_EMAILS = 30  # seconds, to avoid rate limiting
MAX_EMAILS_PER_RUN = 50    # safety limit


# ──────────────────────────────────────────────
# Main Pipeline Functions
# ──────────────────────────────────────────────

def step_1_check_replies():
    """
    Step 1: Check for new replies to previously sent emails
    - Connects to Gmail inbox
    - Marks replies in Google Sheets
    - Sends WhatsApp notifications
    """
    log.info("=" * 70)
    log.info("STEP 1: Checking for new email replies...")
    log.info("=" * 70)
    
    try:
        check_replies.check_for_replies()
        log.info("✅ Reply check completed successfully\n")
        return True
    except Exception as e:
        log.error(f"❌ Error during reply check: {e}\n")
        return False


def step_2_load_leads():
    """
    Step 2: Load all leads from Google Sheets
    Returns a list of lead dictionaries
    """
    log.info("=" * 70)
    log.info("STEP 2: Loading leads from Google Sheets...")
    log.info("=" * 70)
    
    try:
        leads = sheets.get_all_leads()
        log.info(f"✅ Loaded {len(leads)} leads from Google Sheets\n")
        return leads
    except Exception as e:
        log.error(f"❌ Error loading leads: {e}\n")
        return []


def step_3_identify_due_emails(leads):
    """
    Step 3: Determine which leads are due for emails today
    Uses the sequence module to apply business logic:
    - Email 1 on Day 0 (new leads)
    - Email 2 on Day 5 (follow-up)
    - Email 3 on Day 10 (final follow-up)
    - No email if replied
    """
    log.info("=" * 70)
    log.info("STEP 3: Identifying leads due for emails today...")
    log.info("=" * 70)
    
    try:
        due_leads = sequence.get_sequence_due_today(leads)
        log.info(f"✅ Found {len(due_leads)} leads due for emails today\n")
        
        if due_leads:
            log.info("Leads due for emails:")
            for lead in due_leads:
                log.info(f"  - {lead['name']} ({lead['email']}) - Email #{lead['email_number']}")
            log.info()
        
        return due_leads
    except Exception as e:
        log.error(f"❌ Error identifying due emails: {e}\n")
        return []


def step_4_send_emails(due_leads):
    """
    Step 4: Send emails to leads who are due
    - Gets email content from sequence module
    - Sends email via send_email module
    - Updates Google Sheets with send status
    - Handles opt-out requests
    """
    log.info("=" * 70)
    log.info("STEP 4: Sending emails to due leads...")
    log.info("=" * 70)
    
    sent_count = 0
    failed_count = 0
    
    if not due_leads:
        log.info("No leads to email today\n")
        return sent_count, failed_count
    
    # Limit emails per run for safety
    leads_to_send = due_leads[:MAX_EMAILS_PER_RUN]
    
    for idx, lead in enumerate(leads_to_send, 1):
        try:
            # Get email content for this lead
            email_content = sequence.get_email_content(lead)
            subject = email_content['subject']
            body = email_content['body']
            
            lead_id = lead['lead_id']
            email_addr = lead['email']
            email_number = lead['email_number']
            
            log.info(f"\n[{idx}/{len(leads_to_send)}] Sending Email #{email_number}")
            log.info(f"  To: {lead['name']} <{email_addr}>")
            log.info(f"  Subject: {subject}")
            
            # Send the email
            result = send_email.send_email(email_addr, subject, body)
            
            if result['success']:
                log.info(f"  ✅ Email sent successfully")
                
                # Update Google Sheets
                try:
                    sheets.mark_email_sent(lead_id, email_number)
                    log.info(f"  ✅ Sheets updated with send status")
                    sent_count += 1
                except Exception as e:
                    log.warning(f"  ⚠️  Email sent but failed to update Sheets: {e}")
                    sent_count += 1
            else:
                log.error(f"  ❌ Failed to send email: {result['message']}")
                failed_count += 1
            
            # Delay between emails to avoid rate limiting
            if idx < len(leads_to_send):
                time.sleep(DELAY_BETWEEN_EMAILS)
                
        except Exception as e:
            log.error(f"  ❌ Error processing lead {lead.get('lead_id')}: {e}")
            failed_count += 1
    
    log.info(f"\n✅ Email sending complete: {sent_count} sent, {failed_count} failed\n")
    return sent_count, failed_count


def step_5_generate_analytics():
    """
    Step 5: Generate analytics report
    - Calculates metrics from Google Sheets data
    - Displays report in console and logs
    """
    log.info("=" * 70)
    log.info("STEP 5: Generating analytics report...")
    log.info("=" * 70)
    
    try:
        # Get all leads to generate analytics
        leads = sheets.get_all_leads()
        
        # Convert to format expected by analytics module
        analytics_data = []
        for lead in leads:
            analytics_data.append({
                "lead_id": lead.get("lead_id"),
                "name": lead.get("name"),
                "email": lead.get("email"),
                "company": lead.get("company"),
                "email_sent_at": lead.get("email_sent_at"),
                "sequence_step": lead.get("sequence_step"),
                "replied": lead.get("replied"),
                "tier": 1,  # Default tier
                "subject_line": "Follow-up email"
            })
        
        # Generate metrics
        metrics = report.generate_metrics(analytics_data)
        
        # Print report
        log.info("\n")
        report.print_report(metrics)
        log.info("\n✅ Analytics report generated\n")
        
        return metrics
    except Exception as e:
        log.warning(f"⚠️  Could not generate analytics: {e}\n")
        return None


def step_6_summary(sent_count, failed_count):
    """
    Step 6: Print pipeline summary
    """
    log.info("=" * 70)
    log.info("PIPELINE EXECUTION SUMMARY")
    log.info("=" * 70)
    log.info(f"Emails Sent:    {sent_count}")
    log.info(f"Emails Failed:  {failed_count}")
    log.info(f"Total Sent:     {sent_count + failed_count}")
    log.info(f"Timestamp:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70 + "\n")


# ──────────────────────────────────────────────
# Main Pipeline Orchestrator
# ──────────────────────────────────────────────

def run_pipeline():
    """
    Execute the complete email automation pipeline
    """
    log.info("\n")
    log.info("╔" + "=" * 68 + "╗")
    log.info("║" + " " * 15 + "KALNET AI-5 EMAIL AUTOMATION PIPELINE" + " " * 17 + "║")
    log.info("║" + " " * 20 + f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 25 + "║")
    log.info("╚" + "=" * 68 + "╝\n")
    
    # Initialize counters
    sent_count = 0
    failed_count = 0
    
    try:
        # Step 1: Check for replies
        step_1_check_replies()
        
        # Step 2: Load all leads
        leads = step_2_load_leads()
        
        if not leads:
            log.warning("No leads found in Google Sheets. Exiting pipeline.")
            return
        
        # Step 3: Identify which leads are due for emails
        due_leads = step_3_identify_due_emails(leads)
        
        # Step 4: Send emails to due leads
        if due_leads:
            sent_count, failed_count = step_4_send_emails(due_leads)
        else:
            log.info("=" * 70)
            log.info("STEP 4: No leads to email today")
            log.info("=" * 70 + "\n")
        
        # Step 5: Generate analytics
        step_5_generate_analytics()
        
        # Step 6: Print summary
        step_6_summary(sent_count, failed_count)
        
        log.info("✅ PIPELINE EXECUTION COMPLETED SUCCESSFULLY\n")
        
    except Exception as e:
        log.error(f"❌ PIPELINE FAILED: {e}")
        log.error("Pipeline execution stopped due to error\n")
        raise


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run the complete pipeline
    
    Usage:
      python pipeline/run.py
    
    Or schedule via cron (runs daily):
      0 9 * * * cd /path/to/Kalnet-AI-5 && python pipeline/run.py >> logs/cron.log 2>&1
    
    Or schedule via cron (runs every hour):
      0 * * * * cd /path/to/Kalnet-AI-5 && python pipeline/run.py >> logs/cron.log 2>&1
    """
    
    try:
        run_pipeline()
    except KeyboardInterrupt:
        log.info("\n\n⚠️  Pipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        log.error(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
