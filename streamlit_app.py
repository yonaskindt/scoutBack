import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- Page Configuration ---
st.set_page_config(page_title="FTC Scouting Dashboard", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ID = st.secrets.get("sheet_id", "1mXWkiXWxSOLymfjCzeUhZpjR10aQaxKpMgUnwIadNlY")


# --- Google Sheets Loader (Reads Row 2+ and Column B+) ---
@st.cache_data(ttl=30)
def get_google_data(sheet_id: str, tab_name: str) -> pd.DataFrame:
    """Fetch sheet tab starting from Row 2 (headers) and Column B onward."""
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

        if not all_rows or len(all_rows) < 2:
            return pd.DataFrame()

        # Row 2 headers, Row 3+ data, starting at Column B (index 1)
        raw_headers = [col for col in all_rows[1][1:]]
        data_rows = [row[1:] for row in all_rows[2:]]

        # Clean and deduplicate headers
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
        df_out = df_out.loc[:, ~df_out.columns.str.startswith("unnamed_")]
        df_out = df_out.replace(r"^\s*$", None, regex=True)

        return df_out

    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading tab '{tab_name}': {e}")
        return pd.DataFrame()


# --- Full FTC Data Processing Pipeline ---
@st.cache_data(ttl=30)
def load_all_ftc_data():
    data = get_google_data(SHEET_ID, "Data")
    if data.empty:
        data = get_google_data(SHEET_ID, "Per_Team")

    schema = get_google_data(SHEET_ID, "Matches")
    ali = get_google_data(SHEET_ID, "Alliances")

    # Standardize headers across all DataFrames
    for df in [data, schema, ali]:
        if df is not None and not df.empty:
            df.columns = df.columns.str.strip().str.lower()

    # 1. Process Main Scouting Data
    if data is not None and not data.empty:
        # Detect Team & Match columns
        t_col = next((c for c in ['team_number', 'team number', 'team', 'team_num'] if c in data.columns), None)
        m_col = next((c for c in ['match_number', 'match number', 'match', 'match_num'] if c in data.columns), None)
        a_col = next((c for c in ['alliance', 'color'] if c in data.columns), None)

        if t_col:
            data.rename(columns={t_col: 'team_number'}, inplace=True)
            data['team_number'] = pd.to_numeric(data['team_number'], errors='coerce').fillna(0).astype(int)
        if m_col:
            data.rename(columns={m_col: 'match_number'}, inplace=True)
            data['match_number'] = pd.to_numeric(data['match_number'], errors='coerce').fillna(0).astype(int)
        if a_col:
            data.rename(columns={a_col: 'alliance'}, inplace=True)

        # Convert numeric scoring columns safely
        for col in ['+1', '+3', '+5', 'amount in hub', 'auto points', 'teleop points']:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

        score_cols = [c for c in ['+1', '+3', '+5'] if c in data.columns]
        if score_cols:
            data['total score'] = data[score_cols].sum(axis=1)
        elif 'total score' not in data.columns:
            data['total score'] = 0

        # Clean Boolean Flags
        def clean_bool(val):
            return 1 if str(val).lower() in ['true', '1', '1.0', 'yes', 'y'] else 0

        for col in ['moved?', 'died?', 'tipped/fell over?', 'defence/ to other side']:
            if col in data.columns:
                clean_key = col.replace('?', '').split('/')[0].strip() + '_num'
                data[clean_key] = data[col].apply(clean_bool)

    # 2. Process Matches Schema (Matches Tab: B2='match_number', C2='r1', D2='r2', E2='b1', F2='b2')
    if schema is not None and not schema.empty:
        m_schema_col = next((c for c in ['match_number', 'match number', 'match'] if c in schema.columns), schema.columns[0])
        schema.rename(columns={m_schema_col: 'match_number'}, inplace=True)
        schema['match_number'] = pd.to_numeric(schema['match_number'], errors='coerce').fillna(0).astype(int)

    return data, schema, ali


# Load Data
data_df, schema_df, alliance_df = load_all_ftc_data()

if data_df is None or data_df.empty:
    st.warning("⚠️ No scouting data loaded yet. Check your Google Sheet settings.")
    st.stop()


# --- Navigation Tabs ---
tabs = st.tabs(["⚔️ Match Strategy & Field View", "📊 Per-Team Analytics", "🤝 Alliance Selection", "📋 Raw Data"])


# ==============================================================================
# TAB 1: MATCH STRATEGY & FIELD VIEW
# ==============================================================================
with tabs[0]:
    st.title("Match Strategy & Field Overview")

    # Fetch available match numbers safely from schema or data
    if schema_df is not None and not schema_df.empty and 'match_number' in schema_df.columns:
        available_matches = sorted([m for m in schema_df['match_number'].unique() if m > 0])
    elif data_df is not None and not data_df.empty and 'match_number' in data_df.columns:
        available_matches = sorted([m for m in data_df['match_number'].unique() if m > 0])
    else:
        available_matches = [1]

    if not available_matches:
        available_matches = [1]

    col_m, _ = st.columns([1, 2])
    with col_m:
        selected_match = st.selectbox("Select Match:", options=available_matches, key="m_sel")

    # Match Schema Lookup
    m_row = None
    if schema_df is not None and not schema_df.empty and 'match_number' in schema_df.columns:
        matched = schema_df[schema_df['match_number'] == int(selected_match)]
        if not matched.empty:
            m_row = matched.iloc[0]

    # Team extraction helper for r1, r2, b1, b2 headers
    def safe_get_team(row, keys):
        if row is None:
            return 0
        for k in keys:
            if k in row.index:
                try:
                    val = str(row[k]).strip()
                    return int(float(val)) if val and val != "None" else 0
                except (ValueError, TypeError):
                    pass
        return 0

    r1 = safe_get_team(m_row, ['r1', 'red1', 'red 1'])
    r2 = safe_get_team(m_row, ['r2', 'red2', 'red 2'])
    b1 = safe_get_team(m_row, ['b1', 'blue1', 'blue 1'])
    b2 = safe_get_team(m_row, ['b2', 'blue2', 'blue 2'])

    # --- FIELD LAYOUT VISUALIZER ---
    st.subheader(f"Field Layout - Match {selected_match}")
    f_col1, f_col2 = st.columns(2)

    with f_col1:
        st.markdown(
            f"""
            <div style="background-color: #ff4b4b22; border: 2px solid #ff4b4b; padding: 15px; border-radius: 10px; text-align: center;">
                <h3 style="color: #ff4b4b; margin:0;">🔴 RED ALLIANCE</h3>
                <h2 style="margin:10px 0;">Team {r1 if r1 else 'N/A'} &nbsp;|&nbsp; Team {r2 if r2 else 'N/A'}</h2>
            </div>
            """, unsafe_allow_html=True
        )

    with f_col2:
        st.markdown(
            f"""
            <div style="background-color: #1c83e122; border: 2px solid #1c83e1; padding: 15px; border-radius: 10px; text-align: center;">
                <h3 style="color: #1c83e1; margin:0;">🔵 BLUE ALLIANCE</h3>
                <h2 style="margin:10px 0;">Team {b1 if b1 else 'N/A'} &nbsp;|&nbsp; Team {b2 if b2 else 'N/A'}</h2>
            </div>
            """, unsafe_allow_html=True
        )

    st.write("---")

    # --- SCOUTING METRICS FOR MATCH TEAMS ---
    st.subheader("Match Teams Performance Comparison")
    match_teams = [t for t in [r1, r2, b1, b2] if t > 0]

    if match_teams and 'team_number' in data_df.columns:
        match_data = data_df[data_df['team_number'].isin(match_teams)]

        if not match_data.empty:
            agg_dict = {'total score': 'mean'}
            for c in ['moved_num', 'died_num', 'tipped_num']:
                if c in match_data.columns:
                    agg_dict[c] = 'mean'

            metrics_df = match_data.groupby('team_number').agg(agg_dict).reset_index()
            
            rename_map = {'team_number': 'Team', 'total score': 'Avg Points'}
            if 'moved_num' in metrics_df.columns: rename_map['moved_num'] = 'Auto Move Rate'
            if 'died_num' in metrics_df.columns: rename_map['died_num'] = 'Died Rate'
            if 'tipped_num' in metrics_df.columns: rename_map['tipped_num'] = 'Tip Rate'

            metrics_df.rename(columns=rename_map, inplace=True)

            st.dataframe(metrics_df.style.highlight_max(axis=0, subset=['Avg Points'], color='#2e7bcf'), use_container_width=True)

            # Box plot chart for match teams
            fig_match = px.box(
                match_data,
                x='team_number',
                y='total score',
                color='team_number',
                title=f"Score Distribution for Match {selected_match} Teams",
                labels={'team_number': 'Team Number', 'total score': 'Total Score'}
            )
            st.plotly_chart(fig_match, use_container_width=True)
        else:
            st.info("No detailed scouting entries found for these 4 teams in the Data tab yet.")
    else:
        st.info("No alliance team mapping available for this match.")


# ==============================================================================
# TAB 2: PER-TEAM ANALYTICS
# ==============================================================================
with tabs[1]:
    st.title("Per-Team Performance Analysis")

    if 'team_number' in data_df.columns:
        all_teams = sorted([t for t in data_df['team_number'].unique() if t > 0])
        if all_teams:
            selected_team = st.selectbox("Select Team:", options=all_teams, key="t_sel")
            t_data = data_df[data_df['team_number'] == selected_team]

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            with kpi1:
                st.metric("Matches Scouted", len(t_data))
            with kpi2:
                st.metric("Avg Score", f"{t_data['total score'].mean():.1f}" if not t_data.empty else "0")
            with kpi3:
                st.metric("Max Score", int(t_data['total score'].max()) if not t_data.empty else 0)
            with kpi4:
                reliability = (1 - t_data['died_num'].mean()) * 100 if 'died_num' in t_data.columns and not t_data.empty else 100
                st.metric("Reliability", f"{reliability:.0f}%")

            if 'match_number' in t_data.columns and not t_data.empty:
                fig_trend = px.line(
                    t_data.sort_values('match_number'),
                    x='match_number',
                    y='total score',
                    markers=True,
                    title=f"Team {selected_team} Score Progression Across Matches"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No team numbers found in scouting data.")


# ==============================================================================
# TAB 3: ALLIANCE SELECTION RANKINGS
# ==============================================================================
with tabs[2]:
    st.title("Alliance Selection Leaderboard")

    if 'team_number' in data_df.columns and not data_df.empty:
        leaderboard = data_df.groupby('team_number').agg(
            Matches_Played=('total score', 'count'),
            Avg_Score=('total score', 'mean'),
            Max_Score=('total score', 'max')
        ).reset_index().sort_values(by='Avg_Score', ascending=False)

        st.dataframe(leaderboard, use_container_width=True)


# ==============================================================================
# TAB 4: RAW DATA
# ==============================================================================
with tabs[3]:
    st.title("Complete Scouting Dataset")
    st.dataframe(data_df, use_container_width=True)