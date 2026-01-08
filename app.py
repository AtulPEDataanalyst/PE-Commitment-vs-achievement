import streamlit as st
from datetime import date, datetime, time
import pandas as pd
from sheets import get_client, read_sheet, append_row
import base64

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
.timer {
    font-size:18px;
    font-weight:700;
    color:#c62828;
}
.stButton>button {
    background-color: #1976d2;
    color: white;
    font-weight: 600;
    border-radius: 10px;
    padding: 10px 18px;
}
</style>
""", unsafe_allow_html=True)

# ================= HEADER IMAGE =================
def header_banner(path, height="100px"):
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    st.markdown(
        f"<div style='width:100%; overflow:hidden; margin-bottom:10px;'>"
        f"<img src='data:image/png;base64,{img}' style='width:100%; height:{height}; object-fit:cover; border-radius:16px;'>"
        f"</div>", unsafe_allow_html=True
    )

header_banner("assets/header.png", height="100px")
st.markdown("## Commitment vs Achievement")
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
time_left = cutoff - now
form_allowed = time_left.total_seconds() > 0

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

        col1, col2, col3 = st.columns(3)

        for col, title, c, a in [
            (col1, "📅 Yesterday", y_commit, y_ach),
            (col2, "📆 Weekly", w_commit, w_ach),
            (col3, "📊 MTD", m_commit, m_ach)
        ]:
            with col:
                pct = f"{(a/c*100):.0f}%" if c else "0%"
                st.markdown(f"### {title}")
                st.write(f"**Commitment:** ₹{c:,.0f}")
                st.write(f"**Achievement:** ₹{a:,.0f}")
                st.write(f"**Pending:** ₹{max(c-a,0):,.0f}")
                st.write(f"**% Achieved:** {pct}")

        st.markdown("</div>", unsafe_allow_html=True)

# ================= COMMITMENT FORM =================
if st.session_state.verified:
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        if not form_allowed:
            st.error("⛔ Commitment entry closed for today (11:30 AM crossed)")

        st.subheader("📋 Daily Commitment Entry")

        channel = st.selectbox(
            "Channel",
            ["IMA", "Cross Sale", "Affiliate", "Corporate"]
        )

        # ---------- IMA ----------
        if channel == "IMA":
            product = st.selectbox("Product", ["PI", "HI", "Umbrella"])

            # ✅ ADDED FIELDS
            client_name = st.text_input("Client Name")
            commitment_nop = st.number_input("Commitment NOP Count", min_value=0, step=1)

            deals_commitment = st.text_input("Deals Commitment")
            deals_created_product = st.text_input("Deals Created Product")
            deal_assigned_to = st.text_input("Deal Assigned To (Cross Sale)")

            expected_premium = 0
            followups = 0
            closure_date = date.today()
            sub_product = ""

        # ---------- CROSS SALE ----------
        elif channel == "Cross Sale":
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
            meeting_place = st.text_input("Meeting Place")
            followups = st.number_input("Follow-up Count", min_value=0)
            closure_date = st.date_input("Expected Closure Date")

            client_name = ""
            expected_premium = 0
            commitment_nop = 0

        # ---------- CORPORATE ----------
        else:
            client_name = st.text_input("Client Name")
            mobile = st.text_input("Client Mobile Number")
            product_type = st.selectbox("Product Type", ["EB", "Retail"])
            product = st.selectbox(
                "Product",
                ["GMC", "GPA", "GTL"] if product_type == "EB" else ["Motor", "Health", "Fire", "Liability"]
            )
            expected_premium = st.number_input("Expected Premium", min_value=0)
            case_type = st.selectbox("Case Type", ["Fresh", "Renewal"])
            closure_date = st.date_input("Expected Closure Date")
            followups = 0
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
    st.subheader("📌 Performance Snapshot")
    st.image("assets/achievement.png", width=380)
    st.image("assets/commitment.png", width=380)
    st.markdown("</div>", unsafe_allow_html=True)
