import streamlit as st
from datetime import date, datetime, time
import pandas as pd
from sheets import get_client, read_sheet, append_row

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Commitment vs Achievement", layout="wide")

# ================= CSS =================
st.markdown("""
<style>
.card {
    background: #ffffff;
    padding: 22px;
    border-radius: 16px;
    box-shadow: 0px 2px 10px rgba(0,0,0,0.08);
    margin-bottom: 18px;
}
.stButton>button {
    width:100%;
    background-color: #1976d2;
    color: white;
    font-weight: 600;
    border-radius: 10px;
    padding: 10px 18px;
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

users.columns = users.columns.astype(str).str.lower()
commitments.columns = commitments.columns.astype(str).str.lower()
achievements.columns = achievements.columns.astype(str).str.lower()

if 'date' in commitments.columns:
    commitments['date'] = pd.to_datetime(commitments['date'], errors='coerce')

if 'date' in achievements.columns:
    achievements['date'] = pd.to_datetime(achievements['date'], errors='coerce')

# ================= SESSION =================
st.session_state.setdefault("verified", False)

# ================= TIME LOGIC =================
now = datetime.now()
cutoff = datetime.combine(date.today(), time(11, 30))
form_allowed = now < cutoff

# ================= LAYOUT =================
left, right = st.columns([1.5, 1])

# ================= LOGIN =================
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    emp_code = st.text_input("Employee Code")

    if st.button("Verify Employee Code"):
        user = users[users["empcode"].astype(str) == emp_code]
        if user.empty:
            st.error("Invalid Employee Code")
        else:
            st.session_state.verified = True
            st.session_state.emp_code = emp_code
            st.session_state.emp_name = user.iloc[0]["empname"]
            st.session_state.team = user.iloc[0]["team"]
            st.success(f"Welcome {st.session_state.emp_name} ({st.session_state.team})")
    st.markdown("</div>", unsafe_allow_html=True)

# ================= DASHBOARD =================
if st.session_state.verified:
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Commitment vs Achievement Summary")

        emp_commit = commitments[commitments["empcode"].astype(str) == st.session_state.emp_code]
        emp_ach = achievements[achievements["empcode"].astype(str) == st.session_state.emp_code]

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

        y_commit = calc(emp_commit, yesterday, yesterday, 'expected_premium')
        y_ach = calc(emp_ach, yesterday, yesterday, 'actual_premium')

        w_commit = calc(emp_commit, week_start, today, 'expected_premium')
        w_ach = calc(emp_ach, week_start, today, 'actual_premium')

        m_commit = calc(emp_commit, mtd_start, today, 'expected_premium')
        m_ach = calc(emp_ach, mtd_start, today, 'actual_premium')

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

        st.markdown("</div>", unsafe_allow_html=True)

# ================= COMMITMENT FORM =================
if st.session_state.verified:
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        if not form_allowed:
            st.error("⛔ Commitment entry closed for today (11:30 AM crossed)")

        st.subheader("📋 Daily Commitment Entry")

        channel = st.selectbox("Channel", ["IMA", "Cross Sell", "Affiliate", "Corporate"])

        # ---------- IMA ----------
        if channel == "IMA":
            product = st.selectbox("Product", ["PI", "HI", "Umbrella"])
            client_name = st.text_input("Client Name")
            commitment_nop = st.number_input("Commitment NOP Count", min_value=0, step=1)

            deals_commitment = st.text_input("Deals Commitment")

            deals_created_product = st.selectbox(
                "Deals Created Product",
                ["Health", "Life", "Fire", "Motor", "Misc"]
            )

            deal_assigned_to = st.selectbox(
                "Deal Assigned To (IMA)",
                ["Satish", "Divya", "Manisha", "Priti", "Ravi Raj"]
            )

            expected_premium = 0
            followups = ""
            closure_date = date.today()
            sub_product = ""

        # ---------- CROSS SELL ----------
        elif channel == "Cross Sell":
            product = st.selectbox("Product", ["Health", "Life", "Motor", "Fire", "Misc"])
            sub_product = ""

            if product == "Health":
                sub_product = st.selectbox("Type", ["Port", "Fresh"])
            elif product == "Life":
                sub_product = st.selectbox("Category", ["Term", "Investment", "Traditional"])
            elif product == "Motor":
                sub_product = st.selectbox("Vehicle Type", ["2W", "4W", "CV"])

            client_name = st.text_input("Client Name")
            expected_premium = st.number_input("Expected Premium", min_value=0)
            followups = st.number_input("Follow-up Count", min_value=0)
            closure_date = st.date_input("Expected Closure Date")
            commitment_nop = 0

        # ---------- AFFILIATE ----------
        elif channel == "Affiliate":
            product = st.selectbox("Product", ["Health", "Life", "Motor", "Fire", "Misc"])
            sub_product = ""

            if product == "Health":
                sub_product = st.selectbox("Type", ["Port", "Fresh"])
            elif product == "Life":
                sub_product = st.selectbox("Category", ["Term", "Investment", "Traditional"])
            elif product == "Motor":
                sub_product = st.selectbox("Vehicle Type", ["2W", "4W", "CV"])

            partner = st.text_input("Partner Name")

            followups = st.selectbox(
                "Follow-up Count",
                ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th or more"]
            )

            meeting_place = st.selectbox(
                "Meeting Place",
                ["Self Business", "Partner Client", "With Partner"]
            )

            closure_date = st.date_input("Expected Closure Date")

            client_name = ""
            expected_premium = 0
            commitment_nop = 0

        # ---------- CORPORATE ----------
        else:
            client_name = st.text_input("Client Name")
            product_type = st.selectbox("Product Type", ["EB", "Retail"])
            product = st.selectbox(
                "Product",
                ["GMC", "GPA", "GTL"] if product_type == "EB" else ["Motor", "Health", "Fire", "Liability"]
            )
            expected_premium = st.number_input("Expected Premium", min_value=0)
            case_type = st.selectbox("Case Type", ["Fresh", "Renewal"])
            closure_date = st.date_input("Expected Closure Date")

            followups = ""
            sub_product = ""
            commitment_nop = 0

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
                        client_name,
                        product,
                        sub_product,
                        expected_premium,
                        commitment_nop,
                        followups,
                        closure_date.strftime("%Y-%m-%d"),
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
    • Commitment entry allowed till **11:30 AM**  
    • Achievement auto-fetched from SIBRO  
    • Contact admin for corrections  
    """)
    st.markdown("</div>", unsafe_allow_html=True)
