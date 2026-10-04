"""
Streetlight Complaint Analyzer
With Filters: Week / Month / Custom Date / Status / Ward
"""

import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from io import BytesIO
import plotly.express as px
import urllib.parse

st.set_page_config(
    page_title="Streetlight Complaint Analyzer",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💡 Streetlight Complaint Analyzer")
st.caption("Filters: Week • Month • Custom Date • Status • Ward")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def is_empty(val):
    if val is None:
        return True
    try:
        if isinstance(val, (pd.Series, pd.DataFrame)):
            return False
        if pd.isna(val):
            return True
    except Exception:
        pass
    s = str(val).strip().lower()
    return s in ("", "nan", "none", "nat")


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        if "mobile" in cl:
            col_map[c] = "Citizen Mobile"
        elif "remark" in cl:
            col_map[c] = "Citizen Remarks"
        elif "location" in cl or "address" in cl:
            col_map[c] = "Location Address"
        elif cl == "status" or ("status" in cl and "sla" not in cl):
            col_map[c] = "Status"
        elif "registration" in cl and ("date" in cl or "time" in cl):
            col_map[c] = "Registration Date Time"
        elif "action" in cl and ("date" in cl or "time" in cl):
            col_map[c] = "Action DateTime"
        elif "ward" in cl:
            col_map[c] = "Ward"
        elif "zone" in cl:
            col_map[c] = "Zone"
        elif "citizen name" in cl or cl == "name":
            col_map[c] = "Citizen Name"
        elif "problem" in cl and "category" not in cl:
            col_map[c] = "Problem"
        elif "problem category" in cl or "problem_category" in cl:
            col_map[c] = "Problem Category"
        elif "complaint no" in cl or "complaint_no" in cl:
            col_map[c] = "Complaint No"

    df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    return df


def get_col(df, name, default=""):
    if name not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    s = df[name]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s


def extract_pincode(addr):
    if is_empty(addr):
        return "Unknown"
    m = re.search(r"\b(38\d{4})\b", str(addr))
    return m.group(1) if m else "Unknown"


def extract_ward(addr, existing_ward=None):
    if existing_ward is not None and not is_empty(existing_ward):
        return str(existing_ward).strip()
    if is_empty(addr):
        return "Unknown"
    text = str(addr).lower()
    wards = {
        "paldi": "Paldi", "navrangpura": "Navrangpura", "vasna": "Vasna",
        "chandkheda": "Chandkheda Motera", "motera": "Chandkheda Motera",
        "nava vadaj": "Nava Vadaj", "navavadaj": "Nava Vadaj",
        "ranip": "Ranip", "naranpura": "Naranpura",
        "sp stadium": "SP Stadium", "usmanpura": "SP Stadium",
        "ellisbridge": "Paldi", "ambawadi": "Paldi",
        "bodakdev": "Bodakdev", "satellite": "Satellite",
        "vadaj": "Nava Vadaj", "ghatlodia": "Ghatlodia",
        "thaltej": "Thaltej", "bopal": "Bopal",
    }
    for k, v in wards.items():
        if k in text:
            return v
    return "Unknown"


def parse_datetime(s):
    if is_empty(s):
        return None
    s = str(s).strip()
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)", s, re.I)
    if m:
        day, mon, year, hour, minute, ampm = m.groups()
        hour = int(hour)
        if ampm.upper() == "PM" and hour < 12:
            hour += 12
        elif ampm.upper() == "AM" and hour == 12:
            hour = 0
        try:
            return datetime.strptime(f"{day} {mon} {year} {hour:02d}:{minute}", "%d %b %Y %H:%M")
        except Exception:
            pass
    for fmt in [
        "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M", "%d %b %Y %H:%M", "%d-%b-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M", "%d-%m-%Y %H:%M:%S"
    ]:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def calc_duration_hours(reg, act):
    if reg is None or act is None:
        return None
    try:
        delta = act - reg
        if delta.total_seconds() < 0:
            return None
        return round(delta.total_seconds() / 3600, 2)
    except Exception:
        return None


def google_maps_link(address):
    if is_empty(address):
        return ""
    q = urllib.parse.quote(str(address))
    return f"https://www.google.com/maps/search/?api=1&query={q}"


def detect_repeats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n = len(df)
    df["is_repeat"] = False
    df["repeat_score"] = 0
    df["repeat_reason"] = ""

    if "Citizen Mobile" not in df.columns:
        return df

    mobiles = df["Citizen Mobile"].astype(str)
    mobile_counts = mobiles.value_counts()
    repeat_mobiles = set(mobile_counts[mobile_counts > 1].index.tolist())

    keywords = re.compile(
        r"(2\s*time|again|still\s+not|not\s+done|second\s+time|phir\s+se|bar\s+bar|repeat)",
        re.I
    )

    scores, reasons_list, is_rep = [], [], []
    remarks_col = get_col(df, "Citizen Remarks", "")

    for i in range(n):
        score = 0
        reasons = []
        mobile = str(mobiles.iloc[i])
        remarks = str(remarks_col.iloc[i] or "")

        if mobile in repeat_mobiles and mobile not in ("", "nan", "None", "none"):
            score += 50
            reasons.append("Same mobile appears more than once")

        if keywords.search(remarks):
            score += 30
            reasons.append("Remarks contain re-complaint keywords")

        scores.append(min(score, 100))
        reasons_list.append("; ".join(reasons))
        is_rep.append(score >= 70)

    df["repeat_score"] = scores
    df["repeat_reason"] = reasons_list
    df["is_repeat"] = is_rep
    return df


def health_score(open_cnt, total_cnt, repeat_cnt):
    score = 100 - (open_cnt * 8) - (total_cnt * 5) - (repeat_cnt * 10)
    return max(0, min(100, int(score)))


def health_status(score):
    if score < 40:
        return "RED"
    if score < 70:
        return "AMBER"
    return "GREEN"


# ------------------------------------------------------------
# Sidebar – Upload + Filters
# ------------------------------------------------------------
st.sidebar.header("📂 Upload File")
uploaded = st.sidebar.file_uploader(
    "Drop CSV or Excel file here",
    type=["csv", "xlsx", "xls"]
)

if uploaded is None:
    st.info("👈 Please upload a CSV or Excel file to begin analysis.")
    st.markdown("""
    ### Features:
    - **Filters**: Week / Month / Custom Date / Status / Ward
    - Hotspots + Google Maps
    - Duration > 96 hours
    - Repeating complaints
    - Analysis by Problem & Citizen Name
    """)
    st.stop()

# Load file
try:
    if uploaded.name.lower().endswith(".csv"):
        df_raw = pd.read_csv(uploaded, low_memory=False)
    else:
        df_raw = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

if df_raw.empty:
    st.error("The uploaded file is empty.")
    st.stop()

st.sidebar.success(f"Loaded **{len(df_raw):,}** rows")

df = clean_columns(df_raw)

# Enrich
loc = get_col(df, "Location Address", "")
ward_existing = get_col(df, "Ward", "")
df["Ward"] = [extract_ward(loc.iloc[i], ward_existing.iloc[i]) for i in range(len(df))]
df["Pincode"] = [extract_pincode(loc.iloc[i]) for i in range(len(df))]

reg_raw = get_col(df, "Registration Date Time", "")
act_raw = get_col(df, "Action DateTime", "")
df["Reg_DT"] = [parse_datetime(reg_raw.iloc[i]) for i in range(len(df))]
df["Act_DT"] = [parse_datetime(act_raw.iloc[i]) for i in range(len(df))]
df["Duration Hours"] = [calc_duration_hours(df["Reg_DT"].iloc[i], df["Act_DT"].iloc[i]) for i in range(len(df))]
df["Google Maps"] = [google_maps_link(loc.iloc[i]) for i in range(len(df))]
df = detect_repeats(df)
df["Over_96hrs"] = df["Duration Hours"].apply(lambda x: True if x is not None and x > 96 else False)

# Make a date-only column for filtering
df["Reg_Date"] = pd.to_datetime(df["Reg_DT"], errors="coerce").dt.date

# ------------------------------------------------------------
# FILTERS (Sidebar)
# ------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filters")

# 1. Date filter type
date_filter_type = st.sidebar.radio(
    "Date Filter",
    ["All Time", "This Week", "This Month", "Last 7 Days", "Last 30 Days", "Custom Date Range"],
    index=0
)

today = datetime.now().date()

if date_filter_type == "This Week":
    start_date = today - timedelta(days=today.weekday())
    end_date = today
elif date_filter_type == "This Month":
    start_date = today.replace(day=1)
    end_date = today
elif date_filter_type == "Last 7 Days":
    start_date = today - timedelta(days=7)
    end_date = today
elif date_filter_type == "Last 30 Days":
    start_date = today - timedelta(days=30)
    end_date = today
elif date_filter_type == "Custom Date Range":
    col_a, col_b = st.sidebar.columns(2)
    start_date = col_a.date_input("From", value=today - timedelta(days=30))
    end_date = col_b.date_input("To", value=today)
else:
    start_date = None
    end_date = None

# 2. Status filter
status_options = ["All"] + sorted(df["Status"].dropna().astype(str).unique().tolist()) if "Status" in df.columns else ["All"]
selected_status = st.sidebar.multiselect("Status", status_options, default=["All"])

# 3. Ward filter
ward_options = ["All"] + sorted(df["Ward"].dropna().astype(str).unique().tolist())
selected_wards = st.sidebar.multiselect("Ward", ward_options, default=["All"])

# Apply filters
df_filtered = df.copy()

# Date filter
if start_date is not None and end_date is not None:
    df_filtered = df_filtered[
        (df_filtered["Reg_Date"].notna()) &
        (df_filtered["Reg_Date"] >= start_date) &
        (df_filtered["Reg_Date"] <= end_date)
    ]

# Status filter
if selected_status and "All" not in selected_status and "Status" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Status"].astype(str).isin(selected_status)]

# Ward filter
if selected_wards and "All" not in selected_wards:
    df_filtered = df_filtered[df_filtered["Ward"].astype(str).isin(selected_wards)]

st.sidebar.markdown("---")
st.sidebar.info(f"**Showing {len(df_filtered):,}** of {len(df):,} rows")

# Use filtered data for all analysis
df = df_filtered

if len(df) == 0:
    st.warning("No data matches the selected filters. Please change filters.")
    st.stop()

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
total = len(df)
status_col = get_col(df, "Status", "")
closed = int((status_col.astype(str).str.lower() == "closed").sum())
open_ = total - closed
repeats = int(df["is_repeat"].sum())
over_96 = int(df["Over_96hrs"].sum())
dur = pd.Series(df["Duration Hours"])
avg_hrs = float(dur.dropna().mean()) if dur.notna().any() else None

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total", f"{total:,}")
c2.metric("Closed", f"{closed:,}")
c3.metric("Open", f"{open_:,}")
c4.metric("Repeats", f"{repeats:,}")
c5.metric("Duration > 96 hrs", f"{over_96:,}")
c6.metric("Avg Resolution (hrs)", f"{avg_hrs:.1f}" if avg_hrs is not None else "–")

st.markdown("---")

# ------------------------------------------------------------
# Tabs
# ------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📍 Hotspots + Maps",
    "⚠️ Duration > 96 hrs",
    "🔄 Repeating Complaints",
    "🔧 By Problem",
    "👤 By Citizen Name",
    "📊 Status & Trends",
    "📋 Full Data"
])

# ---- Tab 1: Hotspots ----
with tab1:
    st.subheader("Most Affected Locations (High Priority Hot Areas)")

    ward_stats = df.groupby("Ward").agg(
        Total=("Citizen Mobile", "count"),
        Open=("Status", lambda x: (x.astype(str).str.lower() == "open").sum()),
        Repeats=("is_repeat", "sum"),
        Over_96hrs=("Over_96hrs", "sum"),
        Avg_Hours=("Duration Hours", "mean")
    ).reset_index()
    ward_stats["Open %"] = (ward_stats["Open"] / ward_stats["Total"] * 100).round(1)
    ward_stats["Health Score"] = ward_stats.apply(
        lambda r: health_score(r["Open"], r["Total"], r["Repeats"]), axis=1
    )
    ward_stats["Health"] = ward_stats["Health Score"].apply(health_status)
    ward_stats = ward_stats.sort_values("Total", ascending=False)

    def color_health(val):
        if val == "RED":
            return "background-color: #FFC7CE"
        if val == "AMBER":
            return "background-color: #FFEB9C"
        return "background-color: #C6EFCE"

    st.dataframe(
        ward_stats.style.map(color_health, subset=["Health"]),
        use_container_width=True,
        height=350
    )

    fig = px.bar(
        ward_stats.head(15), x="Ward", y="Total", color="Health",
        color_discrete_map={"RED": "#E74C3C", "AMBER": "#F39C12", "GREEN": "#27AE60"},
        title="Top Wards by Complaint Volume", text="Total"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🔥 Hot Areas – Top Location Addresses (Open in Google Maps)")
    loc_stats = df.groupby("Location Address").agg(
        Count=("Citizen Mobile", "count"),
        Open=("Status", lambda x: (x.astype(str).str.lower() == "open").sum()),
        Over_96hrs=("Over_96hrs", "sum"),
        Repeats=("is_repeat", "sum")
    ).reset_index()
    loc_stats = loc_stats.sort_values("Count", ascending=False).head(25)

    for _, row in loc_stats.iterrows():
        priority_icon = "🔴" if (row["Open"] >= 3 or row["Over_96hrs"] >= 1 or row["Repeats"] >= 2) else "🟡"
        maps_url = google_maps_link(row["Location Address"])
        st.markdown(
            f"{priority_icon} **{str(row['Location Address'])[:80]}**  \n"
            f"Complaints: {row['Count']} | Open: {row['Open']} | >96hrs: {row['Over_96hrs']} | Repeats: {row['Repeats']}  \n"
            f"[📍 Open in Google Maps]({maps_url})"
        )
        st.markdown("---")

# ---- Tab 2: Duration > 96 hours ----
with tab2:
    st.subheader("⚠️ High Priority – Duration Above 96 Hours (4+ days)")
    over_df = df[df["Over_96hrs"] == True].copy()
    if len(over_df) == 0:
        st.success("No tickets found with duration above 96 hours.")
    else:
        st.error(f"**{len(over_df):,}** tickets took more than 96 hours")
        show_cols = [c for c in [
            "Citizen Mobile", "Citizen Name", "Ward", "Location Address",
            "Problem", "Status", "Duration Hours", "Registration Date Time",
            "Action DateTime", "Google Maps"
        ] if c in over_df.columns]
        st.dataframe(
            over_df[show_cols].sort_values("Duration Hours", ascending=False),
            use_container_width=True, height=450
        )
        st.markdown("#### Open top delayed locations in Google Maps:")
        for _, row in over_df.sort_values("Duration Hours", ascending=False).head(10).iterrows():
            addr = row.get("Location Address", "")
            hrs = row.get("Duration Hours", 0)
            link = row.get("Google Maps", google_maps_link(addr))
            st.markdown(f"- **{hrs:.0f} hrs** – {str(addr)[:70]} → [Map]({link})")

# ---- Tab 3: Repeats ----
with tab3:
    st.subheader("🔄 Repeating / Re-complaint Detection")
    repeat_df = df[(df["is_repeat"]) | (df["repeat_score"] >= 40)].copy()

    if len(repeat_df) == 0:
        st.success("No strong repeating complaints detected.")
    else:
        st.write(f"Found **{len(repeat_df):,}** tickets with repeat signals")

        st.markdown("#### Repeat by Citizen Mobile")
        agg_dict = {
            "Count": ("Citizen Mobile", "count"),
            "Ward": ("Ward", "first"),
            "Max_Score": ("repeat_score", "max"),
            "Locations": ("Location Address", lambda x: " | ".join(x.dropna().astype(str).unique()[:3]))
        }
        if "Citizen Name" in repeat_df.columns:
            agg_dict["Citizen_Name"] = ("Citizen Name", "first")

        mobile_repeat = repeat_df.groupby("Citizen Mobile").agg(**agg_dict).reset_index()
        mobile_repeat = mobile_repeat.sort_values("Count", ascending=False)
        st.dataframe(mobile_repeat, use_container_width=True, height=250)

        show_cols = [c for c in [
            "Citizen Mobile", "Citizen Name", "Ward", "Location Address",
            "Citizen Remarks", "Status", "repeat_score", "repeat_reason",
            "Registration Date Time", "Duration Hours", "Google Maps"
        ] if c in repeat_df.columns]
        st.dataframe(repeat_df[show_cols].sort_values("repeat_score", ascending=False),
                     use_container_width=True, height=400)

        st.markdown("#### 📍 Trace on Google Maps (Citizen + Mobile + Location)")
        for mobile, group in repeat_df.groupby("Citizen Mobile"):
            name = group["Citizen Name"].iloc[0] if "Citizen Name" in group.columns else "Unknown"
            score = group["repeat_score"].max()
            count = len(group)
            st.markdown(f"### 👤 {name} | 📱 {mobile} | Score: {score} | Tickets: {count}")
            for idx, row in group.iterrows():
                addr = row.get("Location Address", "")
                remarks = str(row.get("Citizen Remarks", "") or "")[:80]
                status = row.get("Status", "")
                reg = row.get("Registration Date Time", "")
                maps_url = row.get("Google Maps") or google_maps_link(addr)
                st.markdown(
                    f"- **{status}** | {reg}  \n"
                    f"  📍 {str(addr)[:90]}  \n"
                    f"  💬 {remarks}  \n"
                    f"  [🗺️ Open in Google Maps]({maps_url})"
                )
            st.markdown("---")

# ---- Tab 4: By Problem ----
with tab4:
    st.subheader("Analysis by Problem Type")
    problem_col = None
    for c in ["Problem", "Problem Category"]:
        if c in df.columns:
            problem_col = c
            break

    if problem_col is None:
        st.info("No Problem column found.")
    else:
        prob_stats = df.groupby(problem_col).agg(
            Total=("Citizen Mobile", "count"),
            Open=("Status", lambda x: (x.astype(str).str.lower() == "open").sum()),
            Over_96hrs=("Over_96hrs", "sum"),
            Repeats=("is_repeat", "sum"),
            Avg_Hours=("Duration Hours", "mean")
        ).reset_index().sort_values("Total", ascending=False)
        st.dataframe(prob_stats, use_container_width=True, height=300)

        fig_p = px.bar(prob_stats.head(15), x=problem_col, y="Total",
                       title="Complaints by Problem Type", text="Total")
        st.plotly_chart(fig_p, use_container_width=True)

        st.markdown("---")
        st.subheader("📍 Problem-wise Details + Google Maps")
        problem_list = ["All"] + sorted(df[problem_col].dropna().astype(str).unique().tolist())
        selected_problem = st.selectbox("Select Problem Type", problem_list)

        detail_df = df if selected_problem == "All" else df[df[problem_col].astype(str) == selected_problem]
        st.write(f"**Showing {len(detail_df):,} complaints** for: `{selected_problem}`")

        show_cols = [c for c in [
            "Citizen Mobile", "Citizen Name", "Ward", "Location Address",
            problem_col, "Status", "Duration Hours", "is_repeat",
            "Registration Date Time", "Google Maps"
        ] if c in detail_df.columns]
        st.dataframe(detail_df[show_cols], use_container_width=True, height=400)

        if "Location Address" in detail_df.columns:
            loc_by_prob = detail_df.groupby("Location Address").agg(
                Count=("Citizen Mobile", "count"),
                Open=("Status", lambda x: (x.astype(str).str.lower() == "open").sum()),
                Over_96hrs=("Over_96hrs", "sum")
            ).reset_index().sort_values("Count", ascending=False).head(15)

            st.markdown("#### 🔥 Top Locations for this Problem")
            for _, row in loc_by_prob.iterrows():
                maps_url = google_maps_link(row["Location Address"])
                priority = "🔴 HIGH" if row["Open"] >= 2 or row["Over_96hrs"] >= 1 else "🟡"
                st.markdown(
                    f"{priority} **{str(row['Location Address'])[:90]}**  \n"
                    f"Count: {row['Count']} | Open: {row['Open']} | >96hrs: {row['Over_96hrs']}  \n"
                    f"[📍 Open in Google Maps]({maps_url})"
                )
                st.markdown("---")

# ---- Tab 5: By Citizen Name ----
with tab5:
    st.subheader("Analysis by Citizen Name (Frequent Complainers)")
    if "Citizen Name" not in df.columns:
        st.info("No Citizen Name column found.")
    else:
        name_stats = df.groupby("Citizen Name").agg(
            Total=("Citizen Mobile", "count"),
            Open=("Status", lambda x: (x.astype(str).str.lower() == "open").sum()),
            Repeats=("is_repeat", "sum"),
            Over_96hrs=("Over_96hrs", "sum"),
            Mobile=("Citizen Mobile", "first")
        ).reset_index().sort_values("Total", ascending=False)
        frequent = name_stats[name_stats["Total"] >= 3]
        st.write(f"**Frequent complainers (3+ tickets):** {len(frequent)}")
        st.dataframe(name_stats.head(30), use_container_width=True, height=400)

# ---- Tab 6: Status ----
with tab6:
    st.subheader("Status Breakdown")
    if "Status" in df.columns:
        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig4 = px.pie(status_counts, names="Status", values="Count", title="Open vs Closed", hole=0.4)
        st.plotly_chart(fig4, use_container_width=True)
        st.dataframe(pd.crosstab(df["Ward"], df["Status"]), use_container_width=True)
    else:
        st.info("Status column not found.")

# ---- Tab 7: Full Data ----
with tab7:
    st.subheader("Full Processed Data (Filtered)")
    st.dataframe(df, use_container_width=True, height=500)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Data")
        ward_stats.to_excel(writer, index=False, sheet_name="Hotspot Ranking")
        if len(over_df) > 0:
            over_df.to_excel(writer, index=False, sheet_name="Duration_Over_96hrs")
        if len(repeat_df) > 0:
            repeat_df.to_excel(writer, index=False, sheet_name="Repeat Candidates")
    buffer.seek(0)
    st.download_button(
        "⬇️ Download Filtered Analysis (Excel)",
        data=buffer,
        file_name="Streetlight_Filtered_Analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.caption("Streetlight Analyzer • Filters: Week / Month / Custom Date / Status / Ward")