import streamlit as st
from datetime import date, datetime
import pandas as pd
from sheets import get_client, read_sheet, append_row
import base64

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Commitment vs Achievement", layout="wide")

# ================= CSS =================
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #e0f7fa, #ffffff);
}
.card {
    background: #ffffff;
    padding: 22px;
    border-radius: 16px;
    box-shadow: 6px solid #1976d2;
    margin-bottom: 18px;
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

# ================= HELPERS =================
def header_banner(path, height="100px"):
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <div style="width:100%; overflow:hidden; margin-bottom:10px;">
            <img src="data:image/png;base64,{img}"
                 style="width:100%; height:{height}; object-fit:cover; border-radius:16px;">
        </div>
        """,
        unsafe_allow_html=True
    )

def show_image_responsive(path, max_width=360):
    st.markdown(
        f"""
        <div style="display:flex; justify-content:center; margin-bottom:16px;">
            <img src="{path}" style="
                width:100%;
                max-width:{max_width}px;
                height:auto;
                border-radius:14px;
            ">
        </div>
        """,
        unsafe_allow_html=True
    )

# ================= HERO =================
header_banner("assets/header.png", height="100px")
st.markdown("## Commitment vs Achievement")
st.caption("From commitment to measurable achievement")

# ================= DATA =================
gc = get_client()
sh = gc.open("Sales_Commitment_Tracker")
users = read_sheet(sh, "user_master")
commitments = read_sheet(sh, "daily_commitments")
users.columns = users.columns.str.strip()

# ================= CONSTANTS =================
CHANNELS = ["IMA", "IMA Cross Sales", "Affiliate", "Corporate"]

IMA_PRODUCTS = ["PI", "HI", "Umbrella"]

OTHER_PRODUCTS = [
    "Health (Non Life)", "Life", "Marine Cargo", "Motor",
    "Misc", "Fire", "Engineering", "Marine Hull",
    "PI", "HI", "Umbrella"
]

# ================= SESSION =================
st.session_state.setdefault("verified", False)

# ================= LAYOUT =================
left, right = st.columns([1.25, 1])

# ================= EMPLOYEE VERIFICATION =================
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🧾 Employee Verification")

    emp_code = st.text_input("Employee Code")

    if st.button("Verify Employee Code"):
        user = users[users["EmpCode"].astype(str) == emp_code]

        if user.empty:
            st.error("Invalid Employee Code")
            st.session_state.verified = False
        else:
            st.session_state.verified = True
            st.session_state.emp_code = emp_code
            st.session_state.emp_name = user.iloc[0]["EmpName"]
            st.session_state.team = user.iloc[0]["Team"]
            st.success(f"Welcome {st.session_state.emp_name} ({st.session_state.team})")

    st.markdown("</div>", unsafe_allow_html=True)

# ================= COMMITMENT SECTION =================
if st.session_state.verified:

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📋 Daily Commitment Details")

        # Channel selector (outside form)
        channel = st.selectbox("Channel", CHANNELS)

        # Dynamic fields per channel
        if channel == "IMA":
            product = st.selectbox("Product", IMA_PRODUCTS)
            nop = st.number_input("NOP", min_value=0)
            amount = st.number_input("Amount (₹)", min_value=0)
            meetings = ""
            deal_id = st.text_input("Deal ID")  # only for IMA

        elif channel == "IMA Cross Sales":
            product = st.selectbox("Product", OTHER_PRODUCTS)
            nop = 0
            amount = st.number_input("Amount (₹)", min_value=0)
            meetings = ""
            deal_id = st.text_input("Deal ID")  # only for IMA Cross Sales

        elif channel == "Affiliate":
            product = st.selectbox("Product", OTHER_PRODUCTS)
            nop = 0
            amount = st.number_input("Amount (₹)", min_value=0)
            meetings = st.text_input("Today Meetings")
            deal_id = ""  # no Deal ID for Affiliate

        else:  # Corporate
            product = st.selectbox("Product", OTHER_PRODUCTS)
            nop = 0
            amount = st.number_input("Amount (₹)", min_value=0)
            meetings = ""
            deal_id = ""  # no Deal ID for Corporate

        # Submit only inside form
        with st.form("submit_form"):
            submit = st.form_submit_button("🚀 Submit Commitment")

            if submit:
                today = date.today()
                commitments["EmpCode"] = commitments["EmpCode"].astype(str)
                commitments["Date"] = pd.to_datetime(commitments["Date"], errors="coerce")

                exists = commitments[
                    (commitments["EmpCode"] == st.session_state.emp_code) &
                    (commitments["Date"].dt.date == today)
                ]

                if not exists.empty:
                    st.warning("You have already submitted today's commitment")
                else:
                    append_row(
                        sh,
                        "daily_commitments",
                        [
                            today.strftime("%Y-%m-%d"),
                            st.session_state.emp_code,
                            st.session_state.emp_name,
                            st.session_state.team,
                            channel,
                            deal_id,
                            product,
                            nop,
                            amount,
                            meetings,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ],
                    )
                    st.success("Commitment submitted successfully")

        st.markdown("</div>", unsafe_allow_html=True)

# ================= RIGHT VISUAL =================
with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 Track Your Commitments")

    st.image("assets/achievement.png", width=400)
    st.image("assets/commitment.png", width=400)

    st.markdown("</div>", unsafe_allow_html=True)
