"""
dashboard/app.py - Kalnet AI-5 Email Automation Dashboard
Streamlit dashboard for monitoring and presenting the email pipeline.
"""

import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipeline import sheets
from analytics import report

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Kalnet AI-5 Dashboard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #1e1e2e;
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #313244;
    }
    div[data-testid="stMetric"] label {
        color: #a6adc8 !important;
        font-size: 0.9rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #cdd6f4 !important;
        font-size: 1.8rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
        color: #a6e3a1 !important;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Load Data
# ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_leads():
    """Load leads from Google Sheets with caching."""
    try:
        leads = sheets.get_all_leads()
        return leads
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return []


def prepare_analytics_data(leads):
    """Convert leads to analytics format."""
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
            "tier": lead.get("tier", ""),
            "subject_line": lead.get("subject_line", "")
        })
    return analytics_data


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/mail.png", width=80)
    st.title("Kalnet AI-5")
    st.caption("Email Automation Pipeline")
    
    st.divider()
    
    if st.button("Refresh Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("### Quick Stats")
    st.markdown("""
    - **Pipeline**: Email automation
    - **Sequence**: 3-step follow-up
    - **Schedule**: Daily at 3:30 AM UTC
    """)
    
    st.divider()
    
    st.markdown("### Navigation")
    page = st.radio(
        "Go to",
        ["Overview", "Leads", "Replies", "Analytics", "Subject Lines", "Pipeline Logs"],
        label_visibility="collapsed"
    )


# ──────────────────────────────────────────────
# Main Content
# ──────────────────────────────────────────────
leads = load_leads()

if not leads:
    st.warning("No data found. Make sure Google Sheets is configured.")
    st.stop()

analytics_data = prepare_analytics_data(leads)
metrics = report.generate_metrics(analytics_data)

# Convert to DataFrame for easier manipulation
df = pd.DataFrame(leads)


# ──────────────────────────────────────────────
# Overview Page
# ──────────────────────────────────────────────
if page == "Overview":
    st.title("📧 Kalnet AI-5 Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    st.divider()
    
    # KPI Cards Row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="Total Leads",
            value=len(leads),
            delta=None
        )
    
    with col2:
        st.metric(
            label="Emails Sent",
            value=metrics['total_sent'],
            delta=None
        )
    
    with col3:
        st.metric(
            label="Replies Received",
            value=metrics['total_replies'],
            delta=None
        )
    
    with col4:
        st.metric(
            label="Reply Rate",
            value=f"{metrics['reply_rate']}%",
            delta=None
        )
    
    with col5:
        opt_out_count = df[df['opt_out'] == True].shape[0] if 'opt_out' in df.columns else 0
        st.metric(
            label="Opt-outs",
            value=opt_out_count,
            delta=None
        )
    
    st.divider()
    
    # Charts Row
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Email Funnel")
        funnel_df = pd.DataFrame({
            'Stage': ['Total Leads', 'Emails Sent', 'Replies', 'Opt-outs'],
            'Count': [
                len(leads),
                metrics['total_sent'],
                metrics['total_replies'],
                opt_out_count
            ]
        })
        st.bar_chart(funnel_df.set_index('Stage'))
    
    with col_right:
        st.subheader("Tier Breakdown")
        if metrics['tier_breakdown']:
            tier_df = pd.DataFrame(
                list(metrics['tier_breakdown'].items()),
                columns=['Tier', 'Count']
            )
            st.bar_chart(tier_df.set_index('Tier'))
        else:
            st.info("No tier data available")
    
    st.divider()
    
    # Recent Activity
    st.subheader("Recent Activity")
    recent_leads = df[df['email_sent_at'] != ''].tail(10)
    if not recent_leads.empty:
        display_cols = ['name', 'email', 'company', 'email_sent_at', 'sequence_step', 'replied']
        available_cols = [c for c in display_cols if c in recent_leads.columns]
        st.dataframe(
            recent_leads[available_cols].rename(columns={
                'name': 'Name',
                'email': 'Email',
                'company': 'Company',
                'email_sent_at': 'Sent At',
                'sequence_step': 'Step',
                'replied': 'Replied'
            }),
            width="stretch",
            hide_index=True
        )
    else:
        st.info("No recent activity")


# ──────────────────────────────────────────────
# Leads Page
# ──────────────────────────────────────────────
elif page == "Leads":
    st.title("👥 Leads Database")
    st.caption(f"Total: {len(leads)} leads")
    
    st.divider()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_replied = st.selectbox("Replied Status", ["All", "Yes", "No"])
    
    with col2:
        filter_opt_out = st.selectbox("Opt-out Status", ["All", "Yes", "No"])
    
    with col3:
        filter_step = st.selectbox("Sequence Step", ["All", "0", "1", "2", "3"])
    
    # Apply filters
    filtered_df = df.copy()
    
    if filter_replied == "Yes":
        filtered_df = filtered_df[filtered_df['replied'] == True]
    elif filter_replied == "No":
        filtered_df = filtered_df[filtered_df['replied'] == False]
    
    if filter_opt_out == "Yes":
        filtered_df = filtered_df[filtered_df['opt_out'] == True]
    elif filter_opt_out == "No":
        filtered_df = filtered_df[filtered_df['opt_out'] == False]
    
    if filter_step != "All":
        filtered_df = filtered_df[filtered_df['sequence_step'] == int(filter_step)]
    
    st.write(f"Showing {len(filtered_df)} leads")
    
    # Display table
    display_cols = ['lead_id', 'name', 'email', 'company', 'email_sent_at', 
                    'sequence_step', 'replied', 'tier', 'subject_line', 'opt_out']
    available_cols = [c for c in display_cols if c in filtered_df.columns]
    
    st.dataframe(
        filtered_df[available_cols],
        width="stretch",
        hide_index=True
    )


# ──────────────────────────────────────────────
# Replies Page
# ──────────────────────────────────────────────
elif page == "Replies":
    st.title("💬 Email Replies")
    
    st.divider()
    
    # Filter replied leads
    replied_df = df[df['replied'] == True].copy()
    
    if replied_df.empty:
        st.info("No replies received yet.")
    else:
        # KPI cards for replies
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Replies", len(replied_df))
        
        with col2:
            opt_out_replies = replied_df[replied_df['opt_out'] == True].shape[0]
            st.metric("Unsubscribed", opt_out_replies)
        
        with col3:
            positive_replies = len(replied_df) - opt_out_replies
            st.metric("Positive Replies", positive_replies)
        
        st.divider()
        
        # Filter options
        col1, col2 = st.columns(2)
        
        with col1:
            filter_type = st.selectbox("Reply Type", ["All", "Positive Replies", "Unsubscribed"])
        
        with col2:
            sort_by = st.selectbox("Sort By", ["Most Recent", "Company Name", "Email"])
        
        # Apply filters
        display_df = replied_df.copy()
        
        if filter_type == "Positive Replies":
            display_df = display_df[display_df['opt_out'] != True]
        elif filter_type == "Unsubscribed":
            display_df = display_df[display_df['opt_out'] == True]
        
        # Sort
        if sort_by == "Most Recent":
            display_df = display_df.sort_values('email_sent_at', ascending=False)
        elif sort_by == "Company Name":
            display_df = display_df.sort_values('company')
        else:
            display_df = display_df.sort_values('email')
        
        st.write(f"**{len(display_df)}** replies found")
        
        # Display replies as cards
        for _, lead in display_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([2, 3, 1])
                
                with col1:
                    st.markdown(f"**{lead.get('name', 'N/A')}**")
                    st.caption(lead.get('email', 'N/A'))
                    st.caption(lead.get('company', 'N/A'))
                
                with col2:
                    snippet = lead.get('reply_snippet', '')
                    if snippet:
                        st.info(f"💬 {snippet}")
                    else:
                        st.info("💬 Reply received (no snippet saved)")
                
                with col3:
                    if lead.get('opt_out') == True:
                        st.error("Unsubscribed")
                    else:
                        st.success("Positive")
                
                st.divider()
    
    # Overview metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Emails Sent", metrics['total_sent'])
    
    with col2:
        st.metric("Total Replies", metrics['total_replies'])
    
    with col3:
        st.metric("Reply Rate", f"{metrics['reply_rate']}%")
    
    st.divider()
    
    # Tier breakdown chart
    st.subheader("Tier Breakdown")
    if metrics['tier_breakdown']:
        tier_df = pd.DataFrame(
            list(metrics['tier_breakdown'].items()),
            columns=['Tier', 'Count']
        )
        st.bar_chart(tier_df.set_index('Tier'))
    else:
        st.info("No tier data available")
    
    st.divider()
    
    # Reply rate over time (if data available)
    st.subheader("Emails by Sequence Step")
    if 'sequence_step' in df.columns:
        step_counts = df[df['email_sent_at'] != '']['sequence_step'].value_counts().sort_index()
        if not step_counts.empty:
            step_df = pd.DataFrame({
                'Step': step_counts.index.astype(str),
                'Count': step_counts.values
            })
            st.bar_chart(step_df.set_index('Step'))
        else:
            st.info("No sent emails data")
    else:
        st.info("Sequence step data not available")


# ──────────────────────────────────────────────
# Subject Lines Page
# ──────────────────────────────────────────────
elif page == "Subject Lines":
    st.title("📝 Subject Line Performance")
    
    st.divider()
    
    if metrics['best_subjects']:
        # Create DataFrame for subject line performance
        subjects_df = pd.DataFrame(metrics['best_subjects'])
        
        # Display as table
        st.subheader("All Subject Lines by Reply Rate")
        st.dataframe(
            subjects_df.rename(columns={
                'subject': 'Subject Line',
                'rate': 'Reply Rate (%)',
                'replies': 'Replies'
            }),
            width="stretch",
            hide_index=True
        )
        
        st.divider()
        
        # Top 3 subject lines
        st.subheader("Top 3 Performing Subjects")
        top3 = subjects_df.head(3)
        
        for idx, row in top3.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{row['subject']}**")
            with col2:
                st.write(f"{row['rate']:.1f}% ({row['replies']} replies)")
    else:
        st.info("No subject line data available yet. Send some emails to see performance.")


# ──────────────────────────────────────────────
# Pipeline Logs Page
# ──────────────────────────────────────────────
elif page == "Pipeline Logs":
    st.title("📋 Pipeline Logs")
    
    st.divider()
    
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    
    # List available logs
    log_files = {
        'pipeline.log': 'Pipeline Execution Log',
        'replies.log': 'Reply Detection Log',
        'replies_summary.log': 'Reply Summary',
        'email.log': 'Email Sending Log'
    }
    
    selected_log = st.selectbox(
        "Select Log File",
        list(log_files.keys()),
        format_func=lambda x: log_files[x]
    )
    
    log_path = os.path.join(log_dir, selected_log)
    
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            log_content = f.read()
        
        # Show last N lines
        lines = log_content.split('\n')
        show_lines = st.slider("Number of lines to show", 10, 500, 50)
        
        st.subheader(f"Last {show_lines} lines of {selected_log}")
        st.code('\n'.join(lines[-show_lines:]), language=None)
    else:
        st.warning(f"Log file not found: {selected_log}")
        st.info("Run the pipeline first to generate logs.")


# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.divider()
st.caption("Kalnet AI-5 Email Automation Pipeline | Built with Streamlit")
