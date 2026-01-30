import streamlit as st

# ================= PAGE CONFIG =================

# MUST be first Streamlit command
st.set_page_config(
    page_title="Commitment vs Achievement",
    layout="wide"
)

from datetime import date, datetime, time as dt_time
from zoneinfo import ZoneInfo
import pandas as pd
from sheets import get_client, read_sheet, append_row
from gspread.exceptions import APIError
import time



# ================= CSS =================
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #f0f4ff, #d9e4ff);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* ---------- MAIN CARD ---------- */
.card {
    background: rgba(255,255,255,0.95);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    margin-bottom: 18px;
    word-wrap: break-word;
}

/* ---------- BUTTON ---------- */
.stButton>button {
    width: 100%;
    background: linear-gradient(90deg, #1976d2, #63a4ff);
    color: white;
    font-weight: 600;
    border-radius: 12px;
    padding: 12px;
}

/* ---------- KPI DASHBOARD CARDS ---------- */
.kpi-card {
    background: white;
    border-radius: 14px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    margin-bottom: 12px;
}

.kpi-title {
    font-size: 15px;
    font-weight: 600;
    color: #555;
}

.kpi-value {
    font-size: 26px;
    font-weight: 700;
    margin: 6px 0;
    color: #1a237e;
}

.kpi-sub {
    font-size: 13px;
    color: #777;
}

/* ---------- SECTION HEADINGS ---------- */
.section-title {
    font-size: 20px;
    font-weight: 700;
    margin: 14px 0 10px;
    color: #1a237e;
}

/* ---------- MOBILE / TABLET RESPONSIVE ---------- */
@media only screen and (max-width: 768px) {

    .card {
        padding: 12px;
        margin-bottom: 12px;
    }

    .stButton>button {
        font-size: 14px;
        padding: 10px;
    }

    /* Force Streamlit columns to stack */
    .css-1d391kg {
        flex-direction: column !important;
    }

    .kpi-value {
        font-size: 22px;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📊 Commitment vs Achievement")
st.caption("From commitment to measurable achievement")


# ================= CACHED SHEET CONNECTION =================
@st.cache_resource
def get_sheet():
    gc = get_client()
    retry = 0
    while retry < 3:
        try:
            sh = gc.open("Sales_Commitment_Tracker")
            return sh
        except APIError as e:
            if e.response.status_code == 429:
                retry += 1
                time.sleep(5)  # wait 5 seconds before retry
            else:
                raise e
    raise Exception("Exceeded Google Sheets API rate limit. Try again later.")

sh = get_sheet()

# ================= CACHED DATA LOAD =================
@st.cache_data(ttl=300)  # cache data for 5 minutes
def load_sheet(sheet_name):
    df = read_sheet(sh, sheet_name)
    df.columns = df.columns.str.lower()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

users = load_sheet("user_master")
commitments = load_sheet("daily_commitments")
achievements = load_sheet("daily_achievement")
lead_team_map = load_sheet("lead_team_map")



users.columns = users.columns.str.lower()
commitments.columns = commitments.columns.str.lower()
achievements.columns = achievements.columns.str.lower()
lead_team_map.columns = lead_team_map.columns.str.lower()

# ---------- COLUMN / DATA SAFETY ----------
def clean_commitment_achievement(df):
    # Fill missing numeric fields
    numeric_cols = ["expected_premium","commitment_nop","actual_premium"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Fill missing string/text fields
    text_cols = ["empcode","empname","team","channel","association","client_name",
                 "product","sub_product","deal_id","deals_commitment","deals_created_product",
                 "deal_assigned_to","case_type","product_type","meeting_type","client_mobile","followups"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("")

    # Ensure date columns are proper datetime
    date_cols = ["date","closure_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


commitments = clean_commitment_achievement(commitments)
achievements = clean_commitment_achievement(achievements)
users = clean_commitment_achievement(users)
lead_team_map = clean_commitment_achievement(lead_team_map)



for df in [commitments, achievements]:
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

# ================= SESSION =================
st.session_state.setdefault("verified", False)

# ================= TIME LOGIC =================
ist = ZoneInfo("Asia/Kolkata")
now = datetime.now(ist)
cutoff = datetime.combine(
    date.today(),
    dt_time(11, 30).replace(tzinfo=ist)  # <- use datetime.time here
)    
form_allowed = now < cutoff

# ================= LAYOUT =================
left, right = st.columns([1.5, 1])

# ================= LOGIN =================
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    emp_code = st.text_input("Employee Code").strip()

    if st.button("Verify Employee Code"):
        user = users[users["empcode"].astype(str) == emp_code]
        if user.empty:
            st.error("Invalid Employee Code")
        else:
            st.session_state.verified = True
            st.session_state.emp_code = emp_code
            st.session_state.emp_name = user.iloc[0]["empname"]
            st.session_state.team = user.iloc[0]["team"]
            st.session_state.role = user.iloc[0]["role"]
            st.session_state.channel = user.iloc[0]["channel"]
            st.success(f"Welcome {st.session_state.emp_name}")
    st.markdown("</div>", unsafe_allow_html=True)


def show_meeting_table_mtd(df, title="📋 Meeting List (MTD)"):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)

    # ---- Current Month Range ----
    today = date.today()
    mtd_start = today.replace(day=1)

    # ---- Filter MTD ----
    if df.empty or "date" not in df.columns:
        st.warning("No meeting data available.")
        return

    mtd_df = df[(df["date"].dt.date >= mtd_start) & (df["date"].dt.date <= today)].copy()

    # ---- Ensure meeting_count numeric ----
    if "meeting_count" in mtd_df.columns:
        mtd_df["meeting_count"] = pd.to_numeric(mtd_df["meeting_count"], errors="coerce").fillna(0)

    # ---- Only take rows where meeting_count > 0 ----
    if "meeting_count" in mtd_df.columns:
        mtd_df = mtd_df[mtd_df["meeting_count"] > 0]

    # ---- Total Meetings (MTD) ----
    total_meetings = int(mtd_df["meeting_count"].sum()) if "meeting_count" in mtd_df.columns else len(mtd_df)

    st.success(f"✅ Total Meetings in Current Month (MTD): {total_meetings}")

    # ---- Build table with required columns ----
    col_map = {
        "empname": "empname",
        "team": "team",
        "client_name": "client_name",
        "product": "product",
        "sub_product": "sub_product",
        "expected_premium": "expected_premium",
        "followups": "followup_count",
        "closure_date": "expected_closure_date",
        "case_type": "case_type",
        "meeting_type": "meeting_type",
        "client_mobile": "client_mobile",
        "timestamp": "timestamp"
    }

    # Create table safely
    table_cols = []
    for k, v in col_map.items():
        if k in mtd_df.columns:
            table_cols.append(k)

    meeting_table = mtd_df[table_cols].copy()

    # Rename columns exactly as required
    meeting_table = meeting_table.rename(columns=col_map)

    # Format dates
    if "expected_closure_date" in meeting_table.columns:
        meeting_table["expected_closure_date"] = pd.to_datetime(
            meeting_table["expected_closure_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")

    # Premium formatting
    if "expected_premium" in meeting_table.columns:
        meeting_table["expected_premium"] = pd.to_numeric(
            meeting_table["expected_premium"], errors="coerce"
        ).fillna(0).astype(int)

    # Show table
    st.dataframe(meeting_table, use_container_width=True)




# ================= DASHBOARD =================
if st.session_state.verified:
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        today = date.today()
        yesterday = today - pd.Timedelta(days=1)
        week_start = today - pd.Timedelta(days=today.weekday())
        mtd_start = today.replace(day=1)

        # ================= METRIC CONFIG =================
        def get_metric_config(channel):
            if channel == "Association":
                return {"metric": "NOP", "commit_col": "nop", "ach_col": "actual_nop", "symbol": ""}
            else:
                return {"metric": "PREMIUM", "commit_col": "expected_premium", "ach_col": "actual_premium", "symbol": "₹"}

        def calc_metric(df, start, end, col):
            if df.empty or col not in df.columns or "date" not in df.columns:
                return 0
            return pd.to_numeric(
                df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)][col],
                errors="coerce"
            ).fillna(0).sum()

        def calc_meeting(df, start, end):
            if df.empty or "meeting_count" not in df.columns:
                return 0
            return pd.to_numeric(
                df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]["meeting_count"],
                errors="coerce"
            ).fillna(0).sum()

        # ================= KPI CARD =================
        def kpi_card(title, value, sub):
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">{title}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

        # ================= DASHBOARD =================
        def show_dashboard(commit_df, ach_df, title, channel):
            cfg = get_metric_config(channel)
            symbol = cfg["symbol"]
            metric = cfg["metric"]

            y_c = calc_metric(commit_df, yesterday, yesterday, cfg["commit_col"])
            y_a = calc_metric(ach_df, yesterday, yesterday, cfg["ach_col"])

            w_c = calc_metric(commit_df, week_start, today, cfg["commit_col"])
            w_a = calc_metric(ach_df, week_start, today, cfg["ach_col"])

            m_c = calc_metric(commit_df, mtd_start, today, cfg["commit_col"])
            m_a = calc_metric(ach_df, mtd_start, today, cfg["ach_col"])

            t_c = calc_metric(commit_df, today, today, cfg["commit_col"])

            st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                kpi_card("🟢 Today", f"{symbol}{int(t_c):,}", f"Commitment ({metric})")

            with c2:
                kpi_card(
                    "📅 Yesterday",
                    f"{symbol}{int(y_c):,}",
                    f"Achieved: {symbol}{int(y_a):,} | {round((y_a / y_c) * 100, 0) if y_c else 0}%"
                )

            with c3:
                kpi_card(
                    "📆 Weekly",
                    f"{symbol}{int(w_c):,}",
                    f"Achieved: {symbol}{int(w_a):,} | {round((w_a / w_c) * 100, 0) if w_c else 0}%"
                )

            with c4:
                kpi_card(
                    "📊 MTD",
                    f"{symbol}{int(m_c):,}",
                    f"Achieved: {symbol}{int(m_a):,} | {round((m_a / m_c) * 100, 0) if m_c else 0}%"
                )

        # ================= MEETING DASHBOARD =================
        def show_meeting_section(df):
            st.markdown("<div class='section-title'>🤝 Meeting Count</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                kpi_card("🟢 Today", calc_meeting(df, today, today), "Meetings")
            with c2:
                kpi_card("📅 Yesterday", calc_meeting(df, yesterday, yesterday), "Meetings")
            with c3:
                kpi_card("📆 Weekly", calc_meeting(df, week_start, today), "Meetings")
            with c4:
                kpi_card("📊 MTD", calc_meeting(df, mtd_start, today), "Meetings")

        # ================= ROLE BASED =================
        role = st.session_state.role
        emp_code = st.session_state.emp_code

        # ---------- USER ----------
        if role == "User":
            c = commitments[commitments["empcode"].astype(str) == emp_code]
            a = achievements[achievements["empcode"].astype(str) == emp_code]

            show_dashboard(c, a, "👤 My Performance", st.session_state.channel)

            if st.session_state.channel in ["Affiliate", "Corporate"]:
                show_meeting_section(c)

        # ---------- TEAM LEAD ----------
        elif role == "Team Lead":
            self_c = commitments[commitments["empcode"].astype(str) == emp_code]
            self_a = achievements[achievements["empcode"].astype(str) == emp_code]

            show_dashboard(self_c, self_a, "👤 My Performance", st.session_state.channel)

            if st.session_state.channel in ["Affiliate", "Corporate"]:
                show_meeting_section(self_c)

            teams = lead_team_map[
                lead_team_map["lead_empcode"].astype(str) == emp_code
            ]["team"].unique()

            for t in teams:
                tu = users[users["team"] == t]
                codes = tu["empcode"].astype(str)
                ch = tu["channel"].mode()[0]

                tc = commitments[commitments["empcode"].astype(str).isin(codes)]
                ta = achievements[achievements["empcode"].astype(str).isin(codes)]

                show_dashboard(tc, ta, f"👥 Team – {t}", ch)

                if ch in ["Affiliate", "Corporate"]:
                    show_meeting_section(tc)

                umap = dict(zip(tu["empcode"].astype(str), tu["empname"]))

                su = st.selectbox(
                    f"Select User ({t})",
                    list(umap.keys()),
                    format_func=lambda x: f"{x} - {umap[x]}",
                    key=f"{t}_u"
                )

                uc = commitments[commitments["empcode"].astype(str) == su]
                ua = achievements[achievements["empcode"].astype(str) == su]

                show_dashboard(uc, ua, f"👤 {umap[su]}", ch)

                if ch in ["Affiliate", "Corporate"]:
                    show_meeting_section(uc)

        # ---------- MANAGEMENT ----------
        else:
            st.markdown("<div class='section-title'>🏢 Management Dashboard</div>", unsafe_allow_html=True)

            channels = users["channel"].dropna().unique().tolist()
            sel = st.selectbox("Select Channel", ["All Channels"] + channels)

            if sel == "All Channels":
                c_df = commitments.copy()
                a_df = achievements.copy()
            else:
                c_df = commitments[commitments["channel"] == sel]
                a_df = achievements[achievements["channel"] == sel]

            if sel == "All Channels":
                show_dashboard(
                    c_df[c_df["channel"] == "Association"],
                    a_df[a_df["channel"] == "Association"],
                    "📦 NOP Dashboard",
                    "Association"
                )

                show_dashboard(
                    c_df[c_df["channel"] != "Association"],
                    a_df[a_df["channel"] != "Association"],
                    "💰 Premium Dashboard",
                    "Cross Sell"
                )

                show_meeting_section(
                    c_df[c_df["channel"].isin(["Affiliate", "Corporate"])]
                )

            elif sel == "Association":
                show_dashboard(c_df, a_df, "📦 NOP Dashboard", "Association")

            elif sel == "Cross Sell":
                show_dashboard(c_df, a_df, "💰 Premium Dashboard", "Cross Sell")

            elif sel in ["Affiliate", "Corporate"]:
                show_dashboard(c_df, a_df, "💰 Premium Dashboard", sel)
                show_meeting_section(c_df)
                
                # ✅ NEW: Meeting List Table (MTD) for Management
                show_meeting_table_mtd(c_df, f"📋 {sel} Meeting List (MTD)")

            # ---------- USER DRILL ----------
            if sel != "All Channels":
                um = users[users["channel"] == sel]
                umap = dict(zip(um["empcode"].astype(str), um["empname"]))

                if umap:
                    su = st.selectbox(
                        "Select User",
                        list(umap.keys()),
                        format_func=lambda x: f"{x} - {umap[x]}",
                        key="mg_user"
                    )

                    uc = commitments[commitments["empcode"].astype(str) == su]
                    ua = achievements[achievements["empcode"].astype(str) == su]

                    if sel == "Association":
                        show_dashboard(uc, ua, f"👤 {umap[su]} – NOP", "Association")
                    else:
                        show_dashboard(uc, ua, f"👤 {umap[su]} – Premium", sel)

                        if sel in ["Affiliate", "Corporate"]:
                            show_meeting_section(uc)

        st.markdown("</div>", unsafe_allow_html=True)


# ================= COMMITMENT FORM =================
if st.session_state.verified and st.session_state.role != "Management":
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        if not form_allowed:
            st.error("⛔ Commitment entry closed (11:30 AM crossed)")

        st.subheader("📋 Daily Commitment Entry")

        emp_code = st.session_state.emp_code
        channel = st.session_state.channel
        st.info(f"Channel : {channel}")

        # ================= SAFE SELECTBOX =================
        def safe_selectbox(label, options, key, default):
            if key not in st.session_state:
                st.session_state[key] = default

            return st.selectbox(label, options, key=key)

        # ================= DEFAULTS =================
        association = client_name = deal_id = sub_product = ""
        case_type = meeting_type = client_mobile = ""
        expected_premium = commitment_nop = meeting_count = 0
        deals_commitment = deals_created_product = deal_assigned_to = ""
        followups = ""
        closure_date = date.today()

        # ================= ASSOCIATION =================
        if channel == "Association":

            association = safe_selectbox(
                "Association",
                ["IMA", "IAP", "RMA", "MSBIRIA", "ISCP", "NON-IMA"],
                f"{emp_code}_association",
                "IMA"
            )

            product = safe_selectbox(
                "Product",
                ["PI", "HI", "Umbrella", "Other Products"],
                f"{emp_code}_product",
                "PI"
            )

            client_name = st.text_input("Client Name", key=f"{emp_code}_client_name")
            deal_id = st.text_input("Deal ID", key=f"{emp_code}_deal_id")

            commitment_nop = st.number_input(
                "Commitment NOP", min_value=0, step=1,
                key=f"{emp_code}_commitment_nop"
            )

            deals_commitment = st.text_input(
                "Deals Commitment", key=f"{emp_code}_deals_commitment"
            )

            deals_created_product = safe_selectbox(
                "Deals Created Product",
                ["Health", "Life", "Fire", "Motor", "Misc"],
                f"{emp_code}_deals_created_product",
                "Health"
            )

            deal_assigned_to = safe_selectbox(
                "Deal Assigned To",
                ["Satish", "Divya", "Ravi Raj", "Rasika", "Manisha"],
                f"{emp_code}_deal_assigned_to",
                "Satish"
            )

            followups = safe_selectbox(
                "Follow-up Count",
                ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th or more"],
                f"{emp_code}_followups",
                "1st"
            )

            closure_date = st.date_input(
                "Expected Closure Date",
                key=f"{emp_code}_closure_date"
            )

        # ================= CROSS SELL =================
        elif channel == "Cross Sell":

            product = safe_selectbox(
                "Product",
                ["Health", "Life", "Motor", "Fire", "Misc"],
                f"{emp_code}_product",
                "Health"
            )

            if product == "Health":
                sub_product = safe_selectbox("Sub Product", ["Port", "New"],
                                             f"{emp_code}_sub_product", "Port")
            elif product == "Life":
                sub_product = safe_selectbox("Sub Product",
                                             ["Term", "Investment", "Traditional"],
                                             f"{emp_code}_sub_product", "Term")
            elif product == "Motor":
                sub_product = safe_selectbox("Sub Product",
                                             ["Car", "Bike", "Commercial Vehicle"],
                                             f"{emp_code}_sub_product", "Car")
            else:
                sub_product = safe_selectbox("Sub Product", ["New"],
                                             f"{emp_code}_sub_product", "New")

            client_name = st.text_input("Client Name", key=f"{emp_code}_client_name")
            deal_id = st.text_input("Deal ID", key=f"{emp_code}_deal_id")

            expected_premium = st.number_input(
                "Expected Premium", min_value=0,
                key=f"{emp_code}_expected_premium"
            )

            followups = safe_selectbox(
                "Follow-up Count",
                ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th or more"],
                f"{emp_code}_followups",
                "1st"
            )

            closure_date = st.date_input(
                "Expected Closure Date",
                key=f"{emp_code}_closure_date"
            )

        # ================= AFFILIATE =================
        elif channel == "Affiliate":

            product = safe_selectbox(
                "Product",
                ["Health", "Life", "Motor", "Fire", "Misc"],
                f"{emp_code}_product",
                "Health"
            )

            if product == "Health":
                sub_product = safe_selectbox("Sub Product", ["Port", "New"],
                                             f"{emp_code}_sub_product", "Port")
            elif product == "Life":
                sub_product = safe_selectbox("Sub Product",
                                             ["Term", "Investment", "Traditional"],
                                             f"{emp_code}_sub_product", "Term")
            elif product == "Motor":
                sub_product = safe_selectbox("Sub Product",
                                             ["Car", "Bike", "Commercial Vehicle"],
                                             f"{emp_code}_sub_product", "Car")
            else:
                sub_product = safe_selectbox("Sub Product", ["New"],
                                             f"{emp_code}_sub_product", "New")

            meeting_count = st.number_input(
                "Meeting Count", min_value=0, step=1,
                key=f"{emp_code}_meeting_count"
            )

            expected_premium = st.number_input(
                "Expected Premium", min_value=0,
                key=f"{emp_code}_expected_premium"
            )

            meeting_type = safe_selectbox(
                "Meeting Type",
                ["Visit Partner", "Partner Client", "Self Business"],
                f"{emp_code}_meeting_type",
                "Visit Partner"
            )

            followups = safe_selectbox(
                "Follow-up Count",
                ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th or more"],
                f"{emp_code}_followups",
                "1st"
            )

            closure_date = st.date_input(
                "Expected Closure Date",
                key=f"{emp_code}_closure_date"
            )

        # ================= CORPORATE =================
        elif channel == "Corporate":

            client_name = st.text_input("Client Name", key=f"{emp_code}_client_name")
            client_mobile = st.text_input("Client Mobile", key=f"{emp_code}_client_mobile")

            case_type = safe_selectbox(
                "Case Type",
                ["New", "Renewal"],
                f"{emp_code}_case_type",
                "New"
            )

            product = safe_selectbox(
                "Product",
                ["EB", "NON EB", "Retail"],
                f"{emp_code}_product",
                "EB"
            )

            if product == "EB":
                sub_product = safe_selectbox(
                    "Sub Product", ["GMC", "GPA", "GTL"],
                    f"{emp_code}_sub_product", "GMC"
                )
            elif product == "NON EB":
                sub_product = safe_selectbox(
                    "Sub Product",
                    ["DNO", "Liability", "WC", "Fire", "Marine"],
                    f"{emp_code}_sub_product", "DNO"
                )
            else:
                sub_product = safe_selectbox(
                    "Sub Product",
                    ["Motor", "Fire", "Health"],
                    f"{emp_code}_sub_product", "Motor"
                )

            meeting_count = st.number_input(
                "Meeting Count", min_value=0, step=1,
                key=f"{emp_code}_meeting_count"
            )

            meeting_type = safe_selectbox(
                "Meeting Type",
                ["With Kedar", "With Prathmesh", "Individual"],
                f"{emp_code}_meeting_type",
                "With Kedar"
            )

            deal_id = ""

            expected_premium = st.number_input(
                "Expected Premium", min_value=0,
                key=f"{emp_code}_expected_premium"
            )

            followups = safe_selectbox(
                "Follow-up Count",
                ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th or more"],
                f"{emp_code}_followups",
                "1st"
            )

            closure_date = st.date_input(
                "Expected Closure Date",
                key=f"{emp_code}_closure_date"
            )

         # ✅ SHOW SUCCESS MESSAGE AFTER SUBMIT (INLINE)
        if st.session_state.get("form_submitted"):
            st.success(
                f"✅ Commitment submitted successfully at {st.session_state.submitted_time}"
            )

        # ================= SUBMIT =================
        with st.form("submit_form"):
            submit = st.form_submit_button("🚀 Submit Commitment", disabled=not form_allowed)

            if submit:
                submit_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

                append_row(
                    sh,
                    "daily_commitments",
                    [
                        date.today().strftime("%Y-%m-%d"),
                        st.session_state.emp_code,
                        st.session_state.emp_name,
                        st.session_state.team,
                        channel,
                        association,
                        client_name,
                        product,
                        sub_product,
                        expected_premium,
                        commitment_nop,
                        meeting_count,
                        followups,
                        closure_date.strftime("%Y-%m-%d"),
                        deal_id,
                        deals_commitment,
                        deals_created_product,
                        deal_assigned_to,
                        case_type,
                        "",
                        meeting_type,
                        client_mobile,
                        submit_time
                    ]
                )

                    # ✅ inline message  WITH TIMESTAMP
                st.session_state.form_submitted = True
                st.session_state.submitted_time = datetime.now(
                    ZoneInfo("Asia/Kolkata")
                ).strftime("%d %b %Y, %I:%M %p")



                # CLEAR ONLY AFTER SUBMIT
                for k in list(st.session_state.keys()):
                    if k.startswith(emp_code):
                        del st.session_state[k]

                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

