import streamlit as st
import gspread
import pandas as pd
import json
from google.oauth2.service_account import Credentials

def get_client():
    creds_dict = st.secrets["gcp_service_account"]

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(credentials)

def read_sheet(sh, sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        print(e)
        return pd.DataFrame()

def append_row(sh, sheet_name, row):
    ws = sh.worksheet(sheet_name)
    ws.append_row(row)
