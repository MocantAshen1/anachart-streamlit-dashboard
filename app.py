import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import date

st.set_page_config(
    page_title="AnaChart Analyst Signal Evaluation Dashboard",
    layout="wide"
)

DATA_DIR = Path("data")


@st.cache_data
def load_data():
    events = pd.read_csv(DATA_DIR / "anachart_event_table_for_tableau.csv")
    daily = pd.read_csv(DATA_DIR / "sector_daily_summary_for_tableau.csv")
    etf = pd.read_csv(DATA_DIR / "sector_etf_prices_for_tableau.csv")

    for df in [events, daily, etf]:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 文本缺失值清洗
    text_fill_cols = {
        "events": ["ticker", "Sector", "broker", "analyst_name", "rating_prior", "rating_post", "rating_action"],
        "daily": ["Sector", "ETF"],
        "etf": ["Sector", "ETF"]
    }

    for col in text_fill_cols["events"]:
        if col in events.columns:
            events[col] = events[col].fillna("Unknown").astype(str)

    for col in text_fill_cols["daily"]:
        if col in daily.columns:
            daily[col] = daily[col].fillna("Unknown").astype(str)

    for col in text_fill_cols["etf"]:
        if col in etf.columns:
            etf[col] = etf[col].fillna("Unknown").astype(str)

    # 数值列尽量转数值
    numeric_cols_events = ["price_target_prior", "price_target_post", "target_revision_pct"]
    numeric_cols_daily = [
        "total_actions", "changed_actions", "no_change_actions",
        "avg_target_revision_pct", "median_target_revision_pct",
        "unique_brokers", "unique_tickers", "change_rate"
    ]
    numeric_cols_etf = ["Close"]

    for col in numeric_cols_events:
        if col in events.columns:
            events[col] = pd.to_numeric(events[col], errors="coerce")

    for col in numeric_cols_daily:
        if col in daily.columns:
            daily[col] = pd.to_numeric(daily[col], errors="coerce")

    for col in numeric_cols_etf:
        if col in etf.columns:
            etf[col] = pd.to_numeric(etf[col], errors="coerce")

    return events, daily, etf


events, daily, etf = load_data()

st.title("AnaChart Analyst Signal Evaluation Dashboard")
st.caption("Prototype for sponsor-facing signal interpretation")


# =========================
# Sidebar filters
# =========================
st.sidebar.header("Filters")

sector_options = ["All"] + sorted(daily["Sector"].dropna().astype(str).unique().tolist())
selected_sector = st.sidebar.selectbox("Sector", sector_options)

min_date = daily["date"].min().date()
max_date = daily["date"].max().date()

default_start = max(min_date, date(2014, 1, 1))
default_end = max_date

date_range = st.sidebar.date_input(
    "Date range",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date
)

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end


# =========================
# Filtered data
# =========================
daily_view = daily.copy()
etf_view = etf.copy()
events_view = events.copy()

if selected_sector != "All":
    daily_view = daily_view[daily_view["Sector"] == selected_sector]
    etf_view = etf_view[etf_view["Sector"] == selected_sector]
    events_view = events_view[events_view["Sector"] == selected_sector]

daily_view = daily_view[
    (daily_view["date"].dt.date >= start_date) &
    (daily_view["date"].dt.date <= end_date)
]

etf_view = etf_view[
    (etf_view["date"].dt.date >= start_date) &
    (etf_view["date"].dt.date <= end_date)
]

events_view = events_view[
    (events_view["date"].dt.date >= start_date) &
    (events_view["date"].dt.date <= end_date)
]

# 月度字段，提升可读性
if not daily_view.empty:
    daily_view["month"] = daily_view["date"].dt.to_period("M").dt.to_timestamp()

if not etf_view.empty:
    etf_view["month"] = etf_view["date"].dt.to_period("M").dt.to_timestamp()

if not events_view.empty:
    events_view["month"] = events_view["date"].dt.to_period("M").dt.to_timestamp()


# =========================
# Tabs
# =========================
tab1, tab2, tab3 = st.tabs(["Overview", "Signal Explorer", "How to Use"])


# =========================
# TAB 1: OVERVIEW
# =========================
with tab1:
    st.subheader("Overview")

    changed_rate_pct = 0
    if len(events_view) > 0 and "rating_action" in events_view.columns:
        changed_rate_pct = (events_view["rating_action"].eq("Changed").mean()) * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Filtered Events", f"{len(events_view):,}")
    k2.metric("Active Tickers", f"{events_view['ticker'].nunique():,}")
    k3.metric("Active Analysts", f"{events_view['analyst_name'].nunique():,}")
    k4.metric("Changed Event Share", f"{changed_rate_pct:.1f}%")

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("ETF Price Trend (Monthly)")
        if not etf_view.empty:
            plot_etf = (
                etf_view.groupby(["month", "ETF"], as_index=False)["Close"]
                .last()
                .sort_values("month")
            )
            fig_etf = px.line(
                plot_etf,
                x="month",
                y="Close",
                color="ETF",
                title="ETF Close by Month"
            )
            st.plotly_chart(fig_etf, use_container_width=True)
        else:
            st.info("No ETF records for the selected filters.")

    with c2:
        st.subheader("Total Analyst Actions (Monthly)")
        if not daily_view.empty:
            plot_actions = (
                daily_view.groupby("month", as_index=False)["total_actions"]
                .sum()
                .sort_values("month")
            )
            fig_actions = px.bar(
                plot_actions,
                x="month",
                y="total_actions",
                title="Total Actions by Month"
            )
            st.plotly_chart(fig_actions, use_container_width=True)
        else:
            st.info("No daily summary records for the selected filters.")

    st.divider()

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Average Target Revision % (Monthly)")
        if not daily_view.empty:
            plot_rev = (
                daily_view.groupby("month", as_index=False)["avg_target_revision_pct"]
                .mean()
                .sort_values("month")
            )
            fig_rev = px.line(
                plot_rev,
                x="month",
                y="avg_target_revision_pct",
                title="Average Target Revision % by Month"
            )
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("No revision records for the selected filters.")

    with c4:
        st.subheader("Recent Summary Preview")
        preview_cols = [
            "date", "Sector", "ETF", "total_actions",
            "changed_actions", "change_rate", "avg_target_revision_pct"
        ]
        preview_cols = [c for c in preview_cols if c in daily_view.columns]

        if not daily_view.empty and preview_cols:
            st.dataframe(
                daily_view[preview_cols]
                .sort_values("date", ascending=False)
                .head(20),
                use_container_width=True,
                height=420
            )
        else:
            st.info("No summary table records to display.")


# =========================
# TAB 2: SIGNAL EXPLORER
# =========================
with tab2:
    st.subheader("Signal Explorer")

    f1, f2, f3, f4 = st.columns(4)

    ticker_options = ["All"] + sorted(events_view["ticker"].dropna().astype(str).unique().tolist())
    analyst_options = ["All"] + sorted(events_view["analyst_name"].dropna().astype(str).unique().tolist())
    broker_options = ["All"] + sorted(events_view["broker"].dropna().astype(str).unique().tolist())
    action_options = ["All"] + sorted(events_view["rating_action"].dropna().astype(str).unique().tolist())

    selected_ticker = f1.selectbox("Ticker", ticker_options)
    selected_analyst = f2.selectbox("Analyst", analyst_options)
    selected_broker = f3.selectbox("Broker", broker_options)
    selected_action = f4.selectbox("Rating Action", action_options)

    explorer_view = events_view.copy()

    if selected_ticker != "All":
        explorer_view = explorer_view[explorer_view["ticker"] == selected_ticker]
    if selected_analyst != "All":
        explorer_view = explorer_view[explorer_view["analyst_name"] == selected_analyst]
    if selected_broker != "All":
        explorer_view = explorer_view[explorer_view["broker"] == selected_broker]
    if selected_action != "All":
        explorer_view = explorer_view[explorer_view["rating_action"] == selected_action]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Filtered Events", f"{len(explorer_view):,}")
    m2.metric("Unique Tickers", f"{explorer_view['ticker'].nunique():,}")
    m3.metric("Unique Analysts", f"{explorer_view['analyst_name'].nunique():,}")
    m4.metric("Unique Brokers", f"{explorer_view['broker'].nunique():,}")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Rating Action Distribution")
        if not explorer_view.empty:
            action_dist = (
                explorer_view["rating_action"]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
            )
            action_dist.columns = ["rating_action", "count"]

            fig_action = px.bar(
                action_dist,
                x="rating_action",
                y="count",
                title="Rating Action Distribution"
            )
            st.plotly_chart(fig_action, use_container_width=True)
        else:
            st.info("No records match the current filters.")

    with right:
        st.subheader("Top Analysts by Event Count")
        if not explorer_view.empty:
            top_analysts = (
                explorer_view.groupby("analyst_name", as_index=False)
                .size()
                .sort_values("size", ascending=False)
                .head(10)
            )

            fig_top_analysts = px.bar(
                top_analysts.sort_values("size", ascending=True),
                x="size",
                y="analyst_name",
                orientation="h",
                title="Top 10 Analysts by Event Count"
            )
            st.plotly_chart(fig_top_analysts, use_container_width=True)
        else:
            st.info("No records match the current filters.")

    st.divider()

    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Target Revision % Over Time")
        if not explorer_view.empty:
            fig_target = px.scatter(
                explorer_view.sort_values("date"),
                x="date",
                y="target_revision_pct",
                color="rating_action",
                hover_data=["ticker", "analyst_name", "broker"],
                title="Target Revision % by Event"
            )
            st.plotly_chart(fig_target, use_container_width=True)
        else:
            st.info("No records match the current filters.")

    with right2:
        st.subheader("Top Tickers by Event Count")
        if not explorer_view.empty:
            top_tickers = (
                explorer_view.groupby("ticker", as_index=False)
                .size()
                .sort_values("size", ascending=False)
                .head(10)
            )

            fig_top_tickers = px.bar(
                top_tickers.sort_values("size", ascending=True),
                x="size",
                y="ticker",
                orientation="h",
                title="Top 10 Tickers by Event Count"
            )
            st.plotly_chart(fig_top_tickers, use_container_width=True)
        else:
            st.info("No records match the current filters.")

    st.divider()

    st.subheader("Event Detail Table")
    display_cols = [
        "date", "ticker", "Sector", "broker", "analyst_name",
        "rating_prior", "rating_post", "rating_action",
        "price_target_prior", "price_target_post", "target_revision_pct"
    ]
    display_cols = [c for c in display_cols if c in explorer_view.columns]

    if not explorer_view.empty and display_cols:
        st.dataframe(
            explorer_view[display_cols]
            .sort_values("date", ascending=False),
            use_container_width=True,
            height=500
        )
    else:
        st.info("No detail records to display.")


# =========================
# TAB 3: HOW TO USE
# =========================
with tab3:
    st.subheader("How to Use This Tool")

    st.markdown("""
This prototype is designed to help AnaChart and its users interpret analyst signals in context rather than rely on raw rankings alone.

**Overview**
Use this tab to understand the broader sector environment. The ETF trend, analyst activity volume, and average target revision metrics help identify periods of stronger signal activity.

**Signal Explorer**
Use this tab to drill down into specific events. Filters let the user isolate a ticker, analyst, broker, or rating-action type and review detailed price-target revisions and rating changes.

**Interpretation guidance**
This tool is intended for signal evaluation and contextual interpretation. It does not provide investment advice and does not claim that a single metric fully captures analyst quality.

**Current data limitations**
Some fields contain missing values in the source data, and the current prototype emphasizes explainability and usability over full analyst-accuracy scoring.
""")