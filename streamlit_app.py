import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration & Constants ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Set your Google Sheet ID here or put it in st.secrets["sheet_id"]
SHEET_ID = st.secrets.get("sheet_id", "1mXWkiXWxSOLymfjCzeUhZpjR10aQaxKpMgUnwIadNlY")

st.set_page_config(page_title="FTC Scouting Dashboard", layout="wide")

# --- Google Sheets Data Fetcher ---
@st.cache_data(ttl=30)
def get_google_data(sheet_id: str, tab_name: str) -> pd.DataFrame:
    """
    Fetch data starting from Row 2 and Column B onward.
    Handles duplicate, blank, and unnamed headers gracefully.
    """
    if "gcp_service_account" not in st.secrets:
        st.error("Missing `gcp_service_account` in Streamlit secrets.")
        return pd.DataFrame()

    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(tab_name)

        all_rows = worksheet.get_all_values()

        # Requires Row 2 (headers) and Row 3+ (data)
        if not all_rows or len(all_rows) < 2:
            return pd.DataFrame()

        # Slice Row 2+ and Column B+ (index 1 in 0-based Python)
        raw_headers = [col for col in all_rows[1][1:]]  # Row 2, Col B+
        data_rows = [row[1:] for row in all_rows[2:]]   # Row 3+, Col B+

        # Clean and deduplicate column headers
        cleaned_headers = []
        seen = {}
        for idx, col in enumerate(raw_headers):
            c_name = str(col).strip().lower()
            if not c_name:
                c_name = f"unnamed_{idx}"

            if c_name in seen:
                seen[c_name] += 1
                c_name = f"{c_name}_{seen[c_name]}"
            else:
                seen[c_name] = 0

            cleaned_headers.append(c_name)

        df_out = pd.DataFrame(data_rows, columns=cleaned_headers)

        # Drop trailing empty/unnamed columns
        df_out = df_out.loc[:, ~df_out.columns.str.startswith("unnamed_")]

        # Replace whitespace-only cells with None
        df_out = df_out.replace(r"^\s*$", None, regex=True)

        return df_out

    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading tab '{tab_name}': {e}")
        return pd.DataFrame()


# --- FTC Data Loader & Dynamic Schema Generator ---
@st.cache_data(ttl=30)
def load_all_ftc_data():
    """Loads sheet data and dynamically creates fallback Matches/Alliances dataframes if missing."""
    data = get_google_data(SHEET_ID, "Data")
    if data.empty:
        data = get_google_data(SHEET_ID, "Per_Team")

    if data.empty:
        st.error("No scouting data found in 'Data' or 'Per_Team' tabs.")
        return None, None, None

    schema = get_google_data(SHEET_ID, "Matches")
    ali = get_google_data(SHEET_ID, "Alliances")

    # Detect team and match column names in primary data
    t_col = next((c for c in ['team_number', 'team number', 'team', 'team_num'] if c in data.columns), None)
    m_col = next((c for c in ['match_number', 'match number', 'match', 'match_num'] if c in data.columns), None)

    # Dynamic Fallback: Build Matches DataFrame if missing
    if schema.empty and m_col and t_col:
        grouped = data.groupby(m_col)[t_col].apply(list).reset_index()
        match_rows = []
        for _, row in grouped.iterrows():
            teams = row[t_col]
            match_rows.append({
                'match_number': row[m_col],
                'red1': teams[0] if len(teams) > 0 else 0,
                'red2': teams[1] if len(teams) > 1 else 0,
                'blue1': teams[2] if len(teams) > 2 else 0,
                'blue2': teams[3] if len(teams) > 3 else 0,
            })
        schema = pd.DataFrame(match_rows)

    # Dynamic Fallback: Build Alliances DataFrame if missing
    if ali.empty and t_col:
        unique_teams = sorted(data[t_col].dropna().unique())
        ali_rows = []
        for i in range(0, min(16, len(unique_teams)), 2):
            ali_rows.append({
                'c': unique_teams[i],
                '1e': unique_teams[i + 1] if i + 1 < len(unique_teams) else 0,
                '2e': 0
            })
        ali = pd.DataFrame(ali_rows)

    # Convert numeric scoring metrics safely
    for col in ['+1', '+3', '+5', 'amount in hub']:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

    score_cols = [c for c in ['+1', '+3', '+5'] if c in data.columns]
    data['total score'] = data[score_cols].sum(axis=1) if score_cols else 0

    # Clean boolean flags into numeric indicators
    def clean_bool(val):
        return 1 if str(val).lower() in ['true', '1', '1.0', 'yes', 'y'] else 0

    for col in ['moved?', 'died?', 'tipped/fell over?', 'defence/ to other side']:
        if col in data.columns:
            clean_key = col.replace('?', '').split('/')[0].strip() + '_num'
            data[clean_key] = data[col].apply(clean_bool)

    return data, schema, ali


# --- Main App Logic ---
st.title("🤖 FTC Scouting Dashboard")

data_df, schema_df, alliance_df = load_all_ftc_data()

if data_df is not None:
    # 1. Identify Match Column in primary data
    m_data_col = next((c for c in ['match_number', 'match number', 'match'] if c in data_df.columns), None)
    
    if m_data_col:
        available_matches = sorted(data_df[m_data_col].dropna().unique())
    else:
        available_matches = [1]

    # Select match
    if 'm_sel_val' not in st.session_state:
        st.session_state.m_sel_val = available_matches[0] if available_matches else 1

    st.selectbox(
        "Select Match Number:",
        options=available_matches,
        key="m_sel_val"
    )

    # 2. Safe Matches Matrix Lookup
    m_row = None
    if schema_df is not None and not schema_df.empty:
        # Detect match column in schema_df
        m_schema_col = next((c for c in ['match_number', 'match number', 'match', 'm_num', 'm'] if c in schema_df.columns), None)
        
        if m_schema_col is None and len(schema_df.columns) > 0:
            m_schema_col = schema_df.columns[0]

        if m_schema_col:
            sel_val_str = str(st.session_state.m_sel_val).strip()
            matched = schema_df[schema_df[m_schema_col].astype(str).str.strip() == sel_val_str]
            if not matched.empty:
                m_row = matched.iloc[0]

    # Safe Team Extractor
    def safe_get_team(row, col_names):
        if row is None:
            return "N/A"
        for col in col_names:
            if col in row.index:
                val = str(row[col]).strip()
                if val and val != "None":
                    return val
        return "N/A"

    red1 = safe_get_team(m_row, ['red1', 'red 1', 'red_1'])
    red2 = safe_get_team(m_row, ['red2', 'red 2', 'red_2'])
    blue1 = safe_get_team(m_row, ['blue1', 'blue 1', 'blue_1'])
    blue2 = safe_get_team(m_row, ['blue2', 'blue 2', 'blue_2'])

    # Display Match Summary
    st.subheader(f"Match {st.session_state.m_sel_val} Overview")
    col1, col2 = st.columns(2)

    with col1:
        st.error(f"🔴 **Red Alliance:** Team {red1} & Team {red2}")
    with col2:
        st.info(f"🔵 **Blue Alliance:** Team {blue1} & Team {blue2}")

    # Display Scouting Data Table
    st.write("---")
    st.subheader("Raw Scouting Records")
    st.dataframe(data_df, use_container_width=True)