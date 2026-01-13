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
.card {
    background: rgba(255,255,255,0.95);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    margin-bottom: 18px;
    word-wrap: break-word;
}
.stButton>button {
    width: 100%;
    background: linear-gradient(90deg, #1976d2, #63a4ff);
    color: white;
    font-weight: 600;
    border-radius: 12px;
    padding: 12px;
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
    .css-1d391kg {  /* Streamlit columns wrapper */
        flex-direction: column !important;
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

        # ---------- HELPER FUNCTIONS ----------
        def calc(df, start, end, col):
            if df.empty or col not in df.columns:
                return 0
            return pd.to_numeric(
                df[(df['date'].dt.date >= start) & (df['date'].dt.date <= end)][col],
                errors='coerce'
            ).fillna(0).sum()

        def calculate_today_commitment_value(commit_df, channel):
            if commit_df.empty or 'date' not in commit_df.columns:
                return 0

            today_df = commit_df[commit_df['date'].dt.date == date.today()]

            if channel == "Association":
                col = today_df["commitment_nop"] if "commitment_nop" in today_df.columns else pd.Series([0])
                return pd.to_numeric(col, errors="coerce").fillna(0).sum()
            else:
                col = today_df["expected_premium"] if "expected_premium" in today_df.columns else pd.Series([0])
                return pd.to_numeric(col, errors="coerce").fillna(0).sum()


        def show_dashboard(commit_df, ach_df, title):
            y_commit = calc(commit_df, yesterday, yesterday, 'expected_premium')
            y_ach = calc(ach_df, yesterday, yesterday, 'actual_premium')
            w_commit = calc(commit_df, week_start, today, 'expected_premium')
            w_ach = calc(ach_df, week_start, today, 'actual_premium')
            m_commit = calc(commit_df, mtd_start, today, 'expected_premium')
            m_ach = calc(ach_df, mtd_start, today, 'actual_premium')
            t_commit = calculate_today_commitment_value(commit_df, st.session_state.channel)

            st.subheader(title)
            c0, c1, c2, c3 = st.columns(4)

            with c0:
                st.markdown("### 🟢 Today")
                if st.session_state.channel == "Association":
                    st.write(f"Commitment (NOP): {int(t_commit)}")
                else:
                    st.write(f"Commitment: ₹{t_commit:,.0f}")

            with c1:
                st.markdown("### 📅 Yesterday")
                st.write(f"Commitment: ₹{y_commit:,.0f}")
                st.write(f"Achievement: ₹{y_ach:,.0f}")
                st.write(f"% Achieved: {round((y_ach/y_commit)*100,0) if y_commit else 0}%")

            with c2:
                st.markdown("### 📆 Weekly")
                st.write(f"Commitment: ₹{w_commit:,.0f}")
                st.write(f"Achievement: ₹{w_ach:,.0f}")
                st.write(f"% Achieved: {round((w_ach/w_commit)*100,0) if w_commit else 0}%")

            with c3:
                st.markdown("### 📊 MTD")
                st.write(f"Commitment: ₹{m_commit:,.0f}")
                st.write(f"Achievement: ₹{m_ach:,.0f}")
                st.write(f"% Achieved: {round((m_ach/m_commit)*100,0) if m_commit else 0}%")

        # ---------- DASHBOARD DISPLAY ----------
        role = st.session_state.role
        emp_code = st.session_state.emp_code

        if role == "User":
            c_df = commitments[commitments["empcode"].astype(str) == emp_code]
            a_df = achievements[achievements["empcode"].astype(str) == emp_code]
            show_dashboard(c_df, a_df, "👤 My Performance")

        elif role == "Team Lead":
            self_c = commitments[commitments["empcode"].astype(str) == emp_code]
            self_a = achievements[achievements["empcode"].astype(str) == emp_code]
            show_dashboard(self_c, self_a, "👤 My Performance")

            teams = lead_team_map[lead_team_map["lead_empcode"].astype(str) == emp_code]["team"].unique()
            for t in teams:
                team_users = users[users["team"] == t]
                team_codes = team_users["empcode"].astype(str)

                t_c = commitments[commitments["empcode"].astype(str).isin(team_codes)]
                t_a = achievements[achievements["empcode"].astype(str).isin(team_codes)]
                show_dashboard(t_c, t_a, f"👥 Team – {t}")

                user_map = dict(zip(team_users["empcode"].astype(str), team_users["empname"]))
                sel = st.selectbox(
                    f"View User ({t})",
                    list(user_map.keys()),
                    format_func=lambda x: f"{x} - {user_map[x]}",
                    key=f"user_{t}"
                )

                uc = commitments[commitments["empcode"].astype(str) == sel]
                ua = achievements[achievements["empcode"].astype(str) == sel]
                show_dashboard(uc, ua, f"👤 {sel} - {user_map[sel]}")

        else:  # Management
            st.subheader("🏢 Overall Performance")
            channels = users['channel'].unique().tolist()
            selected_channel = st.selectbox("Select Channel", ["All Channels"] + channels, index=0)

            if selected_channel == "All Channels":
                c_df = commitments
                a_df = achievements
                title = "🏢 Overall Performance – All Channels"
            else:
                c_df = commitments[commitments["channel"] == selected_channel]
                a_df = achievements[achievements["channel"] == selected_channel]
                title = f"🏢 Channel – {selected_channel}"

            show_dashboard(c_df, a_df, title)

            if selected_channel != "All Channels":
                users_in_channel = users[users["channel"] == selected_channel]
                user_map = dict(zip(users_in_channel["empcode"].astype(str), users_in_channel["empname"]))
                if user_map:
                    selected_user = st.selectbox(
                        f"Select User ({selected_channel})",
                        list(user_map.keys()),
                        format_func=lambda x: f"{x} - {user_map[x]}",
                        key=f"user_mgmt_{selected_channel}"
                    )

                    uc = commitments[commitments["empcode"].astype(str) == selected_user]
                    ua = achievements[achievements["empcode"].astype(str) == selected_user]
                    show_dashboard(uc, ua, f"👤 {selected_user} - {user_map[selected_user]}")

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

