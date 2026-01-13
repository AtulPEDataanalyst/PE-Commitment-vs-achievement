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
                return {
                    "metric": "NOP",
                    "commit_col": "nop",
                    "ach_col": "actual_nop",
                    "symbol": ""
                }
            else:
                return {
                    "metric": "PREMIUM",
                    "commit_col": "expected_premium",
                    "ach_col": "actual_premium",
                    "symbol": "₹"
                }

        def calc_metric(df, start, end, col):
            if df.empty or col not in df.columns or "date" not in df.columns:
                return 0
            return pd.to_numeric(
                df[
                    (df["date"].dt.date >= start) &
                    (df["date"].dt.date <= end)
                ][col],
                errors="coerce"
            ).fillna(0).sum()

        def calculate_today_metric(df, channel):
            cfg = get_metric_config(channel)
            if df.empty or "date" not in df.columns:
                return 0
            return pd.to_numeric(
                df[df["date"].dt.date == today].get(cfg["commit_col"], 0),
                errors="coerce"
            ).fillna(0).sum()

        # ================= KPI UI =================
        def kpi_card(title, value, sub):
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">{title}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

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

            t_c = calculate_today_metric(commit_df, channel)

            st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                kpi_card("🟢 Today", f"{symbol}{int(t_c):,}", f"Commitment ({metric})")

            with c2:
                kpi_card(
                    "📅 Yesterday",
                    f"{symbol}{int(y_c):,}",
                    f"Achieved: {symbol}{int(y_a):,} | {round((y_a/y_c)*100,0) if y_c else 0}%"
                )

            with c3:
                kpi_card(
                    "📆 Weekly",
                    f"{symbol}{int(w_c):,}",
                    f"Achieved: {symbol}{int(w_a):,} | {round((w_a/w_c)*100,0) if w_c else 0}%"
                )

            with c4:
                kpi_card(
                    "📊 MTD",
                    f"{symbol}{int(m_c):,}",
                    f"Achieved: {symbol}{int(m_a):,} | {round((m_a/m_c)*100,0) if m_c else 0}%"
                )

        # ================= ROLE BASED VIEW =================
        role = st.session_state.role
        emp_code = st.session_state.emp_code

        # ---------- USER ----------
        if role == "User":
            c_df = commitments[commitments["empcode"].astype(str) == emp_code]
            a_df = achievements[achievements["empcode"].astype(str) == emp_code]
            show_dashboard(c_df, a_df, "👤 My Performance", st.session_state.channel)

        # ---------- TEAM LEAD ----------
        elif role == "Team Lead":
            self_c = commitments[commitments["empcode"].astype(str) == emp_code]
            self_a = achievements[achievements["empcode"].astype(str) == emp_code]
            show_dashboard(self_c, self_a, "👤 My Performance", st.session_state.channel)

            teams = lead_team_map[
                lead_team_map["lead_empcode"].astype(str) == emp_code
            ]["team"].unique()

            for t in teams:
                team_users = users[users["team"] == t]
                team_codes = team_users["empcode"].astype(str)

                team_channel = team_users["channel"].mode()[0]

                t_c = commitments[commitments["empcode"].astype(str).isin(team_codes)]
                t_a = achievements[achievements["empcode"].astype(str).isin(team_codes)]

                show_dashboard(t_c, t_a, f"👥 Team – {t}", team_channel)

                # ✅ USER DRILL DOWN
                user_map = dict(zip(team_users["empcode"].astype(str), team_users["empname"]))
                sel_user = st.selectbox(
                    f"Select User ({t})",
                    list(user_map.keys()),
                    format_func=lambda x: f"{x} - {user_map[x]}",
                    key=f"user_{t}"
                )

                uc = commitments[commitments["empcode"].astype(str) == sel_user]
                ua = achievements[achievements["empcode"].astype(str) == sel_user]

                show_dashboard(uc, ua, f"👤 {user_map[sel_user]}", team_channel)

        # ---------- MANAGEMENT ----------
        else:
            st.markdown("<div class='section-title'>🏢 Overall Performance</div>", unsafe_allow_html=True)

            channels = users["channel"].unique().tolist()
            selected_channel = st.selectbox("Select Channel", ["All Channels"] + channels)

            if selected_channel == "All Channels":
                show_dashboard(
                    commitments[commitments["channel"] == "Association"],
                    achievements[achievements["channel"] == "Association"],
                    "📦 NOP Based (Association)",
                    "Association"
                )

                show_dashboard(
                    commitments[commitments["channel"] != "Association"],
                    achievements[achievements["channel"] != "Association"],
                    "💰 Premium Based",
                    "Cross Sell"
                )

            else:
                c_df = commitments[commitments["channel"] == selected_channel]
                a_df = achievements[achievements["channel"] == selected_channel]

                show_dashboard(c_df, a_df, f"🏢 Channel – {selected_channel}", selected_channel)

                # ✅ USER DRILL DOWN
                users_in_channel = users[users["channel"] == selected_channel]
                user_map = dict(zip(
                    users_in_channel["empcode"].astype(str),
                    users_in_channel["empname"]
                ))

                if user_map:
                    sel_user = st.selectbox(
                        f"Select User ({selected_channel})",
                        list(user_map.keys()),
                        format_func=lambda x: f"{x} - {user_map[x]}"
                    )

                    uc = commitments[commitments["empcode"].astype(str) == sel_user]
                    ua = achievements[achievements["empcode"].astype(str) == sel_user]

                    show_dashboard(uc, ua, f"👤 {user_map[sel_user]}", selected_channel)

        st.markdown("</div>", unsafe_allow_html=True)


# ================= COMMITMENT FORM =================
if st.session_state.verified and st.session_state.role != "Management":
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        if not form_allowed:
            st.error("⛔ Commitment entry closed (11:30 AM crossed)")

        st.subheader("📋 Daily Commitment Entry")

        channel = st.session_state.channel
        st.info(f"Channel : {channel}")
        emp_code = st.session_state.emp_code

        # ---------- HELPER TO GET/SET SESSION VALUE ----------
        def get_sess_val(field, default=""):
            key = f"{emp_code}_{field}"
            return st.session_state.get(key, default)

        def set_sess_val(field, value):
            key = f"{emp_code}_{field}"
            st.session_state[key] = value

        # ---------- ASSOCIATION ----------
        if channel == "Association":
            association = st.selectbox(
                "Association",
                ["IMA","IAP","RMA","MSBIRIA","ISCP","NON-IMA"],
                index=["IMA","IAP","RMA","MSBIRIA","ISCP","NON-IMA"].index(get_sess_val("association","IMA"))
            )
            set_sess_val("association", association)

            product = st.selectbox(
                "Product",
                ["PI","HI","Umbrella","Other Products"],
                index=["PI","HI","Umbrella","Other Products"].index(get_sess_val("product","PI"))
            )
            set_sess_val("product", product)

            deal_id = st.text_input("Deal ID", value=get_sess_val("deal_id"))
            set_sess_val("deal_id", deal_id)

            client_name = st.text_input("Client Name", value=get_sess_val("client_name"))
            set_sess_val("client_name", client_name)

            commitment_nop = st.number_input(
                "Commitment NOP", min_value=0, value=int(get_sess_val("commitment_nop",0))
            )
            set_sess_val("commitment_nop", commitment_nop)

            deals_commitment = st.text_input("Deals Commitment", value=get_sess_val("deals_commitment"))
            set_sess_val("deals_commitment", deals_commitment)

            deals_created_product = st.selectbox(
                "Deals Created Product",
                ["Health","Life","Fire","Motor","Misc"],
                index=["Health","Life","Fire","Motor","Misc"].index(get_sess_val("deals_created_product","Health"))
            )
            set_sess_val("deals_created_product", deals_created_product)

            deal_assigned_to = st.selectbox(
                "Deal Assigned To",
                ["Satish","Divya","Ravi Raj","Rasika","Manisha"],
                index=["Satish","Divya","Ravi Raj","Rasika","Manisha"].index(get_sess_val("deal_assigned_to","Satish"))
            )
            set_sess_val("deal_assigned_to", deal_assigned_to)

            followups = st.selectbox(
                "Follow-up Count",
                ["1st","2nd","3rd","4th","5th","6th","7th or more"],
                index=["1st","2nd","3rd","4th","5th","6th","7th or more"].index(get_sess_val("followups","1st"))
            )
            set_sess_val("followups", followups)

            closure_date = st.date_input("Expected Closure Date", value=get_sess_val("closure_date", date.today()))
            set_sess_val("closure_date", closure_date)

            expected_premium = 0
            sub_product = case_type = product_type = client_mobile = meeting_type = ""

        # ---------- CROSS SELL ----------
        elif channel == "Cross Sell":
            association = ""
            product = st.selectbox(
                "Product",
                ["Health","Life","Motor","Fire","Misc"],
                index=["Health","Life","Motor","Fire","Misc"].index(get_sess_val("product","Health"))
            )
            set_sess_val("product", product)

            # Sub-product logic
            if product == "Health":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Port","New"],
                    index=["Port","New"].index(get_sess_val("sub_product","Port"))
                )
            elif product == "Life":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Term", "Investment", "Traditional"],
                    index=["Term", "Investment", "Traditional"].index(get_sess_val("sub_product","Term"))
                )
            elif product == "Motor":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Car", "Bike", "Commercial Vehicle"],
                    index=["Car", "Bike", "Commercial Vehicle"].index(get_sess_val("sub_product","Car"))
                )
            else:
                sub_product = st.text_input("Sub Product", value=get_sess_val("sub_product"))
            set_sess_val("sub_product", sub_product)

            client_name = st.text_input("Client Name", value=get_sess_val("client_name"))
            set_sess_val("client_name", client_name)

            deal_id = st.text_input("Deal ID", value=get_sess_val("deal_id"))
            set_sess_val("deal_id", deal_id)

            expected_premium = st.number_input(
                "Expected Premium", min_value=0, value=int(get_sess_val("expected_premium",0))
            )
            set_sess_val("expected_premium", expected_premium)

            followups = st.selectbox(
                "Follow-up Count",
                ["1st","2nd","3rd","4th","5th","6th","7th or more"],
                index=["1st","2nd","3rd","4th","5th","6th","7th or more"].index(get_sess_val("followups","1st"))
            )
            set_sess_val("followups", followups)

            closure_date = st.date_input(
                "Expected Closure Date",
                value=get_sess_val("closure_date", date.today())
            )
            set_sess_val("closure_date", closure_date)

            commitment_nop = 0
            deals_commitment = deals_created_product = deal_assigned_to = ""
            case_type = product_type = client_mobile = meeting_type = ""

        # ---------- AFFILIATE ----------
        elif channel == "Affiliate":
            # Similar to Cross Sell, just using session persistence
            association = ""
            product = st.selectbox(
                "Product",
                ["Health","Life","Motor","Fire","Misc"],
                index=["Health","Life","Motor","Fire","Misc"].index(get_sess_val("product","Health"))
            )
            set_sess_val("product", product)

            if product == "Health":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Port","New"],
                    index=["Port","New"].index(get_sess_val("sub_product","Port"))
                )
            elif product == "Life":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Term", "Investment", "Traditional"],
                    index=["Term","Investment","Traditional"].index(get_sess_val("sub_product","Term"))
                )
            elif product == "Motor":
                sub_product = st.selectbox(
                    "Sub Product",
                    ["Car","Bike","Commercial Vehicle"],
                    index=["Car","Bike","Commercial Vehicle"].index(get_sess_val("sub_product","Car"))
                )
            else:
                sub_product = st.text_input("Sub Product", value=get_sess_val("sub_product"))
            set_sess_val("sub_product", sub_product)

            expected_premium = st.number_input(
                "Expected Premium", min_value=0, value=int(get_sess_val("expected_premium",0))
            )
            set_sess_val("expected_premium", expected_premium)

            followups = st.selectbox(
                "Follow-up Count",
                ["1st","2nd","3rd","4th","5th","6th","7th or more"],
                index=["1st","2nd","3rd","4th","5th","6th","7th or more"].index(get_sess_val("followups","1st"))
            )
            set_sess_val("followups", followups)

            closure_date = st.date_input(
                "Expected Closure Date",
                value=get_sess_val("closure_date", date.today())
            )
            set_sess_val("closure_date", closure_date)

            meeting_type = st.selectbox(
                "Meeting Type", ["Visit Partner","Partner Client","Self Business"],
                index=["Visit Partner","Partner Client","Self Business"].index(get_sess_val("meeting_type","Visit Partner"))
            )
            set_sess_val("meeting_type", meeting_type)

            client_name = ""
            commitment_nop = 0
            deal_id = deals_commitment = deals_created_product = deal_assigned_to = ""
            case_type = product_type = client_mobile = ""

        # ---------- CORPORATE / OTHER ----------
        else:
            association = ""
            client_name = st.text_input("Client Name", value=get_sess_val("client_name"))
            set_sess_val("client_name", client_name)

            client_mobile = st.text_input("Client Mobile", value=get_sess_val("client_mobile"))
            set_sess_val("client_mobile", client_mobile)

            case_type = st.selectbox(
                "Case Type", ["Fresh","Renewal"],
                index=["Fresh","Renewal"].index(get_sess_val("case_type","Fresh"))
            )
            set_sess_val("case_type", case_type)

            product_type = st.selectbox(
                "Product Type", ["EB","Non EB","Retail"],
                index=["EB","Non EB","Retail"].index(get_sess_val("product_type","EB"))
            )
            set_sess_val("product_type", product_type)

            # Sub-product logic
            if product_type == "EB":
                sub_product = st.selectbox(
                    "Sub Product", ["GPA","GTL","GMC"],
                    index=["GPA","GTL","GMC"].index(get_sess_val("sub_product","GPA"))
                )
            elif product_type == "Non EB":
                sub_product = st.selectbox(
                    "Sub Product", ["Liability", "Misc", "DNO","Fire","WC"],
                    index=["Liability","Misc","DNO","Fire","WC"].index(get_sess_val("sub_product","Liability"))
                )
            elif product_type == "Retail":
                sub_product = st.selectbox(
                    "Sub Product", ["Retail Health","Retail Life","Retail Motor"],
                    index=["Retail Health","Retail Life","Retail Motor"].index(get_sess_val("sub_product","Retail Health"))
                )
            else:
                sub_product = st.text_input("Sub Product", value=get_sess_val("sub_product"))
            set_sess_val("sub_product", sub_product)

            expected_premium = st.number_input(
                "Expected Premium", min_value=0, value=int(get_sess_val("expected_premium",0))
            )
            set_sess_val("expected_premium", expected_premium)

            followups = st.selectbox(
                "Follow-up Count", ["1st","2nd","3rd","4th","5th","6th","7th or more"],
                index=["1st","2nd","3rd","4th","5th","6th","7th or more"].index(get_sess_val("followups","1st"))
            )
            set_sess_val("followups", followups)

            closure_date = st.date_input(
                "Expected Closure Date",
                value=get_sess_val("closure_date", date.today())
            )
            set_sess_val("closure_date", closure_date)

            meeting_type = st.selectbox(
                "Meeting Type", ["With team","Individual"],
                index=["With team","Individual"].index(get_sess_val("meeting_type","With team"))
            )
            set_sess_val("meeting_type", meeting_type)

            commitment_nop = 0
            deal_id= product = deals_commitment = deals_created_product = deal_assigned_to = ""

        # ---------- SUBMIT FORM ----------
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
                        followups,
                        closure_date.strftime("%Y-%m-%d"),
                        deal_id,
                        deals_commitment,
                        deals_created_product,
                        deal_assigned_to,
                        case_type,
                        product_type,
                        meeting_type,
                        client_mobile,
                        submit_time
                    ]
                )

                st.success("✅ Commitment submitted successfully")
                st.info(f"🕒 Submitted at: **{submit_time}**")

                # ---------- CLEAR FORM SESSION KEYS AFTER SUBMIT ----------
                form_fields = ["association","product","deal_id","client_name","commitment_nop","deals_commitment",
                               "deals_created_product","deal_assigned_to","sub_product","case_type","product_type",
                               "meeting_type","client_mobile","followups","closure_date"]
                for f in form_fields:
                    key = f"{emp_code}_{f}"
                    if key in st.session_state:
                        del st.session_state[key]

        st.markdown("</div>", unsafe_allow_html=True)
# ================= RIGHT PANEL =================
with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📌 Notes")
    st.markdown("""
    • Commitment allowed till **11:30 AM**  
    • Achievement auto-fetched  
    • Contact admin for correction  
    """)
    st.markdown("</div>", unsafe_allow_html=True)


