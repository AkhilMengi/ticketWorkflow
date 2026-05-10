"""
🧠 LangSmith-Style Agent Observability Dashboard
Run:
    streamlit run dashboard.py
"""

import time
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Agent Observability",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS (LANGSMITH STYLE)
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>

/* =========================================================
BACKGROUND
========================================================= */

.stApp {
    background:
        radial-gradient(circle at top left, #172554 0%, transparent 25%),
        radial-gradient(circle at bottom right, #312e81 0%, transparent 30%),
        linear-gradient(180deg, #020617 0%, #0f172a 50%, #111827 100%);
    color: #f8fafc;
}

/* =========================================================
REMOVE STREAMLIT DEFAULTS
========================================================= */

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* =========================================================
SIDEBAR
========================================================= */

section[data-testid="stSidebar"] {
    background: rgba(2, 6, 23, 0.95);
    border-right: 1px solid rgba(255,255,255,0.06);
}

/* =========================================================
TITLE
========================================================= */

.main-title {
    font-size: 3rem;
    font-weight: 800;
    background: linear-gradient(90deg, #60a5fa, #818cf8, #22d3ee);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.subtitle {
    color: #94a3b8;
    font-size: 1rem;
    margin-top: -8px;
    margin-bottom: 28px;
}

/* =========================================================
CARDS
========================================================= */

.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 22px;
    backdrop-filter: blur(12px);
    transition: 0.25s ease;
}

.metric-card:hover {
    border: 1px solid rgba(96,165,250,0.45);
    transform: translateY(-3px);
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: white;
}

.metric-label {
    color: #94a3b8;
    margin-top: 8px;
    font-size: 0.9rem;
}

/* =========================================================
SECTION TITLES
========================================================= */

.section-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: white;
    margin-top: 12px;
    margin-bottom: 18px;
}

/* =========================================================
TRACE PANEL
========================================================= */

.trace-panel {
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 24px;
}

/* =========================================================
BADGES
========================================================= */

.success-badge {
    background: rgba(16,185,129,0.12);
    color: #10b981;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

.fail-badge {
    background: rgba(239,68,68,0.12);
    color: #ef4444;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

/* =========================================================
DATAFRAME
========================================================= */

[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
}

/* =========================================================
BUTTONS
========================================================= */

.stButton>button {
    background: linear-gradient(90deg, #2563eb, #7c3aed);
    color: white;
    border: none;
    border-radius: 12px;
    font-weight: 600;
    transition: 0.25s ease;
}

.stButton>button:hover {
    transform: translateY(-2px);
}

/* =========================================================
JSON
========================================================= */

.stJson {
    border-radius: 14px !important;
    overflow: hidden;
}

</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# API CONFIG
# ─────────────────────────────────────────────────────────────

API_BASE_URL = "http://localhost:8000/api/v1"

# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-title">🧠 Agent Observability</div>
<div class="subtitle">
Monitor autonomous agent reasoning, decisions, and execution traces in real time.
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# TOP BAR
# ─────────────────────────────────────────────────────────────

top1, top2, top3 = st.columns([7, 1, 1])

with top3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

st.sidebar.markdown("# ⚙️ Controls")

account_filter = st.sidebar.text_input(
    "Filter by Account ID",
    placeholder="e.g. ACC-001"
)

refresh_interval = st.sidebar.slider(
    "Auto Refresh Interval",
    min_value=5,
    max_value=60,
    value=10
)

st.sidebar.markdown("---")

st.sidebar.info("""
### Dashboard Features

✅ Live traces  
✅ Confidence analytics  
✅ Execution inspection  
✅ Success metrics  
✅ AI observability  
✅ LangSmith-style UX  
""")

# ─────────────────────────────────────────────────────────────
# API FUNCTIONS
# ─────────────────────────────────────────────────────────────

def fetch_traces(account_id=None):

    try:

        if account_id:
            response = requests.get(
                f"{API_BASE_URL}/traces",
                params={"account_id": account_id},
                timeout=5
            )
        else:
            response = requests.get(
                f"{API_BASE_URL}/traces",
                timeout=5
            )

        if response.status_code == 200:
            return response.json()

        st.error(f"API Error: {response.status_code}")
        return None

    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None


def fetch_metrics():

    try:

        response = requests.get(
            f"{API_BASE_URL}/traces/metrics",
            timeout=5
        )

        if response.status_code == 200:
            return response.json()

        return None

    except Exception as e:
        st.error(f"Metrics Error: {str(e)}")
        return None


# ─────────────────────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────────────────────

traces_data = fetch_traces(
    account_filter if account_filter else None
)

metrics_data = fetch_metrics()

if traces_data is None or metrics_data is None:
    st.warning(
        "⚠️ Unable to connect to backend API."
    )
    st.stop()

metrics = metrics_data.get("metrics", {})
traces = traces_data.get("traces", [])

# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────

st.markdown(
    '<div class="section-title">📊 Key Metrics</div>',
    unsafe_allow_html=True
)

metric_cols = st.columns(6)

metric_items = [
    ("Executions", metrics.get("total_executions", 0)),
    ("Confidence", f"{metrics.get('avg_confidence', 0)}/10"),
    ("Success Rate", f"{metrics.get('success_rate', 0)}%"),
    ("Success", metrics.get("success_count", 0)),
    ("Failures", metrics.get("failure_count", 0)),
    ("Avg Duration", f"{metrics.get('avg_duration', 0)}s"),
]

for col, (label, value) in zip(metric_cols, metric_items):

    with col:

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(
    '<div class="section-title">📈 Analytics</div>',
    unsafe_allow_html=True
)

chart1, chart2 = st.columns(2)

with chart1:

    status_counts = {
        "Success": metrics.get("success_count", 0),
        "Failed": metrics.get("failure_count", 0),
    }

    fig = px.pie(
        values=list(status_counts.values()),
        names=list(status_counts.keys()),
        hole=0.7,
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=350,
        margin=dict(t=0, b=0, l=0, r=0)
    )

    st.plotly_chart(fig, use_container_width=True)

with chart2:

    confidence_scores = [
        t.get("confidence_score", 0)
        for t in traces
    ]

    fig2 = px.histogram(
        confidence_scores,
        nbins=10,
    )

    fig2.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=350,
        margin=dict(t=0, b=0, l=0, r=0)
    )

    st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────────────────────────
# RECENT EXECUTIONS TABLE
# ─────────────────────────────────────────────────────────────

st.markdown(
    '<div class="section-title">📋 Recent Executions</div>',
    unsafe_allow_html=True
)

if not traces:

    st.info("No traces available.")

else:

    table_data = []

    for trace in traces:

        status = (
            "🟢 Success"
            if trace.get("status") == "success"
            else "🔴 Failed"
        )

        actions = trace.get("recommended_actions", [])

        table_data.append({
            "Account": trace.get("account_id"),
            "Issue": trace.get("issue_description"),
            "Confidence": f"{trace.get('confidence_score')}/10",
            "Status": status,
            "Duration": f"{trace.get('duration_seconds')}s",
            "Actions": ", ".join(actions[:2]) if actions else "None",
            "Timestamp": trace.get("timestamp", "")[:19],
        })

    df = pd.DataFrame(table_data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=420,
    )

# ─────────────────────────────────────────────────────────────
# TRACE INSPECTOR
# ─────────────────────────────────────────────────────────────

st.markdown(
    '<div class="section-title">🔎 Trace Inspector</div>',
    unsafe_allow_html=True
)

if traces:

    trace_options = [
        f"{t['timestamp'][:19]} | {t['account_id']} | {t['issue_description'][:40]}"
        for t in traces
    ]

    selected_idx = st.selectbox(
        "Select Trace",
        range(len(traces)),
        format_func=lambda x: trace_options[x],
    )

    selected_trace = traces[selected_idx]

    st.markdown(
        '<div class="trace-panel">',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 📥 Input")

        st.json({
            "account_id":
                selected_trace.get("account_id"),

            "issue_description":
                selected_trace.get("issue_description"),
        })

    with col2:

        st.markdown("### 🧠 Analysis")

        st.json({
            "confidence_score":
                selected_trace.get("confidence_score"),

            "issue_analysis":
                selected_trace.get("issue_analysis"),
        })

    st.markdown("### 🎯 Decisions")

    action_col1, action_col2 = st.columns(2)

    with action_col1:

        st.markdown("#### Recommended Actions")

        actions = selected_trace.get(
            "recommended_actions", []
        )

        if actions:
            for action in actions:
                st.success(action)
        else:
            st.warning("No recommendations")

    with action_col2:

        st.markdown("#### Executed Actions")

        executed = selected_trace.get(
            "actions_executed", []
        )

        if executed:
            for action in executed:
                st.success(action)
        else:
            st.warning("No executions")

    st.markdown("### 📋 Results")

    result_col1, result_col2 = st.columns(2)

    with result_col1:

        if selected_trace.get("sf_case_result"):
            st.markdown("#### Salesforce")
            st.json(
                selected_trace.get("sf_case_result")
            )
        else:
            st.info("No Salesforce action")

    with result_col2:

        if selected_trace.get("billing_result"):
            st.markdown("#### Billing")
            st.json(
                selected_trace.get("billing_result")
            )
        else:
            st.info("No billing operation")

    st.markdown("### 📝 Summary")

    st.info(
        selected_trace.get(
            "final_summary",
            "No summary available"
        )
    )

    perf1, perf2, perf3 = st.columns(3)

    with perf1:
        st.metric(
            "Duration",
            f"{selected_trace.get('duration_seconds')}s"
        )

    with perf2:
        st.metric(
            "Confidence",
            f"{selected_trace.get('confidence_score')}/10"
        )

    with perf3:
        st.metric(
            "Status",
            selected_trace.get("status")
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────
# AUTO REFRESH
# ─────────────────────────────────────────────────────────────

time.sleep(refresh_interval)
st.rerun()