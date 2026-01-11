import streamlit as st
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from sheets import get_client, read_sheet, append_row

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Commitment vs Achievement", layout="wide")

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
}
.stButton>button {
    width: 100%;
    background: linear-gradient(90deg, #1976d2, #63a4ff);
    color: white;
    font-weight: 600;
    border-radius: 12px;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)

# ================= HEADER =================
st.markdown("## 📊 Commitment vs Achievement")
st.caption("From commitment to measurable achievement")

# ================= DATA LOAD =================
gc = get_client()
sh = gc.open("Sales_Commitment_Tracker")

users = read_sheet(sh, "user_master")
commitments = read_sheet(sh, "daily_commitments")
achievements = read_sheet(sh, "daily_achievement")
lead_team_map = read_sheet(sh, "lead_team_map")

users.columns = users.columns.str.lower()
commitments.columns = commitments.columns.str.lower()
achievements.columns = achievements.columns.str.lower()
lead_team_map.columns = lead_team_map.columns.str.lower()

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
    time(11, 30),
    tzinfo=ist
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

        def calc(df, start, end, col):
            if df.empty or col not in df.columns:
                return 0
            return pd.to_numeric(
                df[(df['date'].dt.date >= start) & (df['date'].dt.date <= end)][col],
                errors='coerce'
            ).fillna(0).sum()

        def show_dashboard(commit_df, ach_df, title):
            y_commit = calc(commit_df, yesterday, yesterday, 'expected_premium')
            y_ach = calc(ach_df, yesterday, yesterday, 'actual_premium')
            w_commit = calc(commit_df, week_start, today, 'expected_premium')
            w_ach = calc(ach_df, week_start, today, 'actual_premium')
            m_commit = calc(commit_df, mtd_start, today, 'expected_premium')
            m_ach = calc(ach_df, mtd_start, today, 'actual_premium')

            st.subheader(title)
            c1, c2, c3 = st.columns(3)

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

            # -------- CHANNEL SELECTION --------
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

            # -------- USER SELECTION --------
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

        # ---------- ASSOCIATION ----------
        if channel == "Association":
            association = st.selectbox("Association", ["IMA","IAP","RMA","MSBIRIA","ISCP","NON-IMA"])
            product = st.selectbox("Product", ["PI","HI","Umbrella","Other Products"])
            deal_id = st.text_input("Deal ID")
            client_name = st.text_input("Client Name")
            commitment_nop = st.number_input("Commitment NOP", min_value=0)
            deals_commitment = st.text_input("Deals Commitment")
            deals_created_product = st.selectbox("Deals Created Product", ["Health","Life","Fire","Motor","Misc"])
            deal_assigned_to = st.selectbox("Deal Assigned To",["Satish","Divya","Ravi Raj","Rasika","Manisha"])
            followups = st.selectbox("Follow-up Count", ["1st","2nd","3rd","4th","5th","6th","7th or more"])
            closure_date = st.date_input("Expected Closure Date")
            expected_premium = 0
            sub_product = case_type = product_type = client_mobile = ""

        # ---------- CROSS SELL ----------
        elif channel == "Cross Sell":
            association = ""
            product = st.selectbox("Product", ["Health","Life","Motor","Fire","Misc"])
            if product == "Health":
                sub_product = st.selectbox("Sub Product", ["Port","New"])
            elif product == "Life":
                sub_product = st.selectbox("Sub Product", ["Term", "Investment", "Traditional"])
            elif product == "Motor":
                sub_product = st.selectbox("Sub Product", ["Car", "Bike", "Commercial Vehicle"])
            else:
                sub_product = st.text_input("Sub Product")
            client_name = st.text_input("Client Name")
            deal_id = st.text_input("Deal ID")
            expected_premium = st.number_input("Expected Premium", min_value=0)
            followups = st.selectbox("Follow-up Count", ["1st","2nd","3rd","4th","5th","6th","7th or more"])
            closure_date = st.date_input("Expected Closure Date")
            commitment_nop = 0
            deals_commitment = deals_created_product = deal_assigned_to = ""
            case_type = product_type = client_mobile = ""

        # ---------- AFFILIATE ----------
        elif channel == "Affiliate":
            association = ""
            product = st.selectbox("Product", ["Health","Life","Motor","Fire","Misc"])
            if product == "Health":
                sub_product = st.selectbox("Sub Product", ["Port","New"])
            elif product == "Life":
                sub_product = st.selectbox("Sub Product", ["Term", "Investment", "Traditional"])
            elif product == "Motor":
                sub_product = st.selectbox("Sub Product", ["Car", "Bike", "Commercial Vehicle"])
            else:
                sub_product = st.text_input("Sub Product")
            expected_premium = st.number_input("Expected Premium", min_value=0)
            followups = st.selectbox("Follow-up Count", ["1st","2nd","3rd","4th","5th","6th","7th or more"])
            closure_date = st.date_input("Expected Closure Date")
            meeting_type = st.selectbox("Meeting Type", ["Visit Partner","Partner Client","Self Business"])
            client_name = ""
            commitment_nop = 0
            deal_id = deals_commitment = deals_created_product = deal_assigned_to = ""
            case_type = product_type = client_mobile = ""

        # ---------- CORPORATE / OTHER ----------
        else:
            association = ""
            client_name = st.text_input("Client Name")
            client_mobile = st.text_input("Client Mobile")
            case_type = st.selectbox("Case Type", ["Fresh","Renewal"])
            product_type = st.selectbox("Product Type", ["EB","Non EB","Retail"])
            if product_type == "EB":
                sub_product = st.selectbox("Sub Product", ["GPA", "GTL","GMC"])
            elif product_type == "Non EB":
                sub_product = st.selectbox("Sub Product", ["Liability", "Misc", "DNO","Fire","WC"])
            elif product_type == "Retail":
                sub_product = st.selectbox("Sub Product", ["Retail Health", "Retail Life", "Retail Motor"])
            else:
                sub_product = st.text_input("Sub Product")
            product = st.text_input("Product")
            expected_premium = st.number_input("Expected Premium", min_value=0)
            followups = st.selectbox("Follow-up Count", ["1st","2nd","3rd","4th","5th","6th","7th or more"])
            closure_date = st.date_input("Expected Closure Date")
            meeting_type = st.selectbox("Meeting Type", ["With team","Individual"])
            commitment_nop = 0
            deal_id = deals_commitment = deals_created_product = deal_assigned_to = ""

        # ---------- SUBMIT FORM ----------
        with st.form("submit_form"):
            submit = st.form_submit_button("🚀 Submit Commitment", disabled=not form_allowed)
            if submit:
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
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                )
                st.success("✅ Commitment submitted successfully")

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

