import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import os
import base64

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FTC Scouting & Strategy Dashboard",
    page_icon="🤖",
    layout="wide"
)

# Set your target Google Spreadsheet ID (found in your Google Sheet URL)
SPREADSHEET_ID = "1mXWkiXWxSOLymfjCzeUhZpjR10aQaxKpMgUnwIadNlY"

# -----------------------------------------------------------------------------
# 1. LOCAL FIELD IMAGE HELPER (ftcfield.png)
# -----------------------------------------------------------------------------
def get_image_base64(file_path: str) -> str:
    """Converts local image to base64 string for direct embedding into HTML5 Canvas."""
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    else:
        st.error(f"⚠️ Image file '{file_path}' not found in the root directory. Make sure 'ftcfield.png' is placed next to 'streamlit_app.py'.")
        return ""

FIELD_IMAGE_B64 = get_image_base64("ftcfield.png")

# -----------------------------------------------------------------------------
# 2. GOOGLE SERVICE ACCOUNT DATA LOADER
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_all_sheets():
    """
    Connects via Google Service Account and parses:
    - 'Data' sheet: Header on Row 2, drops Column A (Scouter Initial)
    - 'Per_Team' sheet: Header on Row 2, unique teams on Column B
    """
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes,
        )

        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # ------------------- A. LOAD 'Data' SHEET -------------------
        data_ws = spreadsheet.worksheet("Data")
        data_vals = data_ws.get_all_values()

        if len(data_vals) >= 2:
            # Header is on Row 2 (index 1), Data starts on Row 3 (index 2)
            headers_data = data_vals[1]
            rows_data = data_vals[2:]

            df_data = pd.DataFrame(rows_data, columns=headers_data)

            # Drop Column A (index 0 - Scouter Initial)
            df_data = df_data.iloc[:, 1:]

            # Remove entirely empty rows
            df_data = df_data.replace("", np.nan).dropna(how="all")

            # Clean and convert team/match identifiers
            for col in df_data.columns:
                if "team" in col.lower():
                    df_data[col] = df_data[col].astype(str).str.strip()
                elif "match" in col.lower():
                    df_data[col] = pd.to_numeric(df_data[col], errors="coerce").fillna(0)
                else:
                    # Try numeric conversion for scoring columns
                    df_data[col] = pd.to_numeric(df_data[col], errors="ignore")
        else:
            df_data = pd.DataFrame()

        # ------------------- B. LOAD 'Per_Team' SHEET -------------------
        per_team_ws = spreadsheet.worksheet("Per_Team")
        per_team_vals = per_team_ws.get_all_values()

        if len(per_team_vals) >= 2:
            # Header is on Row 2 (index 1), Data starts on Row 3 (index 2)
            headers_team = per_team_vals[1]
            rows_team = per_team_vals[2:]

            df_per_team = pd.DataFrame(rows_team, columns=headers_team)
            df_per_team = df_per_team.replace("", np.nan).dropna(how="all")

            # Dynamic identification of Column B (Team Number)
            team_col_name = df_per_team.columns[1] if len(df_per_team.columns) > 1 else df_per_team.columns[0]
            df_per_team[team_col_name] = df_per_team[team_col_name].astype(str).str.strip()

            # Convert numeric columns
            for col in df_per_team.columns:
                if col != team_col_name:
                    df_per_team[col] = pd.to_numeric(df_per_team[col], errors="coerce").fillna(0)
        else:
            df_per_team = pd.DataFrame()

        return df_data, df_per_team

    except Exception as e:
        st.error(f"Error loading sheets via Service Account: {e}")
        st.stop()

# Execute Data Load
df_match_data, df_per_team = load_all_sheets()

# Helper to find column name in DataFrame case-insensitively
def find_col(df, keyword):
    for col in df.columns:
        if keyword.lower() in col.lower():
            return col
    return None

team_col_per_team = df_per_team.columns[1] if len(df_per_team.columns) > 1 else (df_per_team.columns[0] if not df_per_team.empty else "")
team_col_match = find_col(df_match_data, "team") or (df_match_data.columns[0] if not df_match_data.empty else "")

# -----------------------------------------------------------------------------
# 3. MAIN NAVIGATION
# -----------------------------------------------------------------------------
st.title("🤖 FTC Strategy & Scouting Dashboard")

view_mode = st.radio(
    "Select Dashboard View",
    ["Tactical Strategy Canvas", "Alliance Match Comparison", "Team Deep-Dive", "Leaderboard & Draft Board", "Playoff Simulator"],
    horizontal=True
)

st.divider()

# -----------------------------------------------------------------------------
# VIEW 1: TACTICAL STRATEGY CANVAS (HTML5/JS Canvas with ftcfield.png)
# -----------------------------------------------------------------------------
if view_mode == "Tactical Strategy Canvas":
    st.subheader("📋 FTC Tactical Strategy Canvas")
    st.markdown("Draw autonomous routes, defense paths, and position alliance robots directly on the field.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("### Controls")
        draw_color = st.color_picker("Drawing Color", "#FF0000")
        line_width = st.slider("Line Thickness", 1, 12, 4)
        tool_mode = st.radio("Tool", ["Draw", "Clear Drawings"])
        st.info("💡 **Tip:** Drag the R1, R2, B1, B2 robot markers anywhere on the canvas to set positions.")

    canvas_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #canvas-container {{
                position: relative;
                width: 700px;
                height: 700px;
                background-image: url('{FIELD_IMAGE_B64}');
                background-size: 100% 100%;
                background-position: center;
                background-repeat: no-repeat;
                border: 3px solid #222;
                border-radius: 8px;
                user-select: none;
                overflow: hidden;
            }}
            canvas {{
                position: absolute;
                top: 0;
                left: 0;
                cursor: crosshair;
            }}
            .robot-marker {{
                position: absolute;
                width: 42px;
                height: 42px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-family: Arial, sans-serif;
                font-size: 14px;
                color: white;
                cursor: grab;
                box-shadow: 0 4px 8px rgba(0,0,0,0.6);
                border: 2.5px solid white;
                z-index: 10;
            }}
            .red-alliance {{ background-color: #E63946; }}
            .blue-alliance {{ background-color: #1D3557; }}
        </style>
    </head>
    <body>
        <div id="canvas-container">
            <canvas id="paintCanvas" width="700" height="700"></canvas>
            <div class="robot-marker red-alliance" id="r1" style="top: 80px; left: 40px;">R1</div>
            <div class="robot-marker red-alliance" id="r2" style="top: 160px; left: 40px;">R2</div>
            <div class="robot-marker blue-alliance" id="b1" style="top: 80px; left: 615px;">B1</div>
            <div class="robot-marker blue-alliance" id="b2" style="top: 160px; left: 615px;">B2</div>
        </div>

        <script>
            const canvas = document.getElementById('paintCanvas');
            const ctx = canvas.getContext('2d');
            let isDrawing = false;
            let color = '{draw_color}';
            let lineWidth = {line_width};
            let toolMode = '{tool_mode}';

            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            canvas.addEventListener('mousedown', (e) => {{
                if (toolMode === 'Clear Drawings') {{
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    return;
                }}
                isDrawing = true;
                ctx.beginPath();
                ctx.moveTo(e.offsetX, e.offsetY);
            }});

            canvas.addEventListener('mousemove', (e) => {{
                if (isDrawing && toolMode === 'Draw') {{
                    ctx.lineTo(e.offsetX, e.offsetY);
                    ctx.stroke();
                }}
            }});

            canvas.addEventListener('mouseup', () => isDrawing = false);
            canvas.addEventListener('mouseleave', () => isDrawing = false);

            // Drag and Drop Logic for Robot Markers
            const markers = document.querySelectorAll('.robot-marker');
            markers.forEach(marker => {{
                marker.addEventListener('mousedown', (e) => {{
                    let shiftX = e.clientX - marker.getBoundingClientRect().left;
                    let shiftY = e.clientY - marker.getBoundingClientRect().top;

                    function moveAt(pageX, pageY) {{
                        const container = document.getElementById('canvas-container').getBoundingClientRect();
                        let newLeft = pageX - container.left - shiftX;
                        let newTop = pageY - container.top - shiftY;

                        marker.style.left = newLeft + 'px';
                        marker.style.top = newTop + 'px';
                    }}

                    function onMouseMove(event) {{
                        moveAt(event.pageX, event.pageY);
                    }}

                    document.addEventListener('mousemove', onMouseMove);

                    document.addEventListener('mouseup', () => {{
                        document.removeEventListener('mousemove', onMouseMove);
                    }}, {{ once: true }});
                }});

                marker.ondragstart = () => false;
            }});
        </script>
    </body>
    </html>
    """

    with col2:
        st.components.v1.html(canvas_html, height=730)

# -----------------------------------------------------------------------------
# VIEW 2: ALLIANCE MATCH COMPARISON
# -----------------------------------------------------------------------------
elif view_mode == "Alliance Match Comparison":
    st.subheader("⚔️ Alliance Comparison & Match Predictor")

    if df_per_team.empty:
        st.warning("No team data found in 'Per_Team' sheet.")
    else:
        teams_list = sorted(df_per_team[team_col_per_team].unique())

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🔴 Red Alliance")
            r1 = st.selectbox("Red Team 1", teams_list, index=0)
            r2 = st.selectbox("Red Team 2", teams_list, index=min(1, len(teams_list)-1))
        with c2:
            st.markdown("### 🔵 Blue Alliance")
            b1 = st.selectbox("Blue Team 1", teams_list, index=min(2, len(teams_list)-1))
            b2 = st.selectbox("Blue Team 2", teams_list, index=min(3, len(teams_list)-1))

        red_teams = [r1, r2]
        blue_teams = [b1, b2]

        # Extract rows from Per_Team
        red_stats = df_per_team[df_per_team[team_col_per_team].isin(red_teams)]
        blue_stats = df_per_team[df_per_team[team_col_per_team].isin(blue_teams)]

        numeric_cols = df_per_team.select_dtypes(include=[np.number]).columns

        red_sums = red_stats[numeric_cols].sum()
        blue_sums = blue_stats[numeric_cols].sum()

        st.divider()
        st.markdown("### Summary Statistics Comparison")

        comp_data = []
        for col in numeric_cols:
            comp_data.append({
                "Metric": col,
                "Red Alliance": red_sums.get(col, 0),
                "Blue Alliance": blue_sums.get(col, 0)
            })

        df_comp = pd.DataFrame(comp_data)

        fig = px.bar(
            df_comp,
            x="Metric",
            y=["Red Alliance", "Blue Alliance"],
            barmode="group",
            color_discrete_sequence=["#E63946", "#1D3557"],
            title="Alliance Totals by Metric"
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# VIEW 3: TEAM DEEP-DIVE
# -----------------------------------------------------------------------------
elif view_mode == "Team Deep-Dive":
    st.subheader("🔍 Individual Team Performance")

    if df_per_team.empty:
        st.warning("No data found in 'Per_Team' sheet.")
    else:
        teams_list = sorted(df_per_team[team_col_per_team].unique())
        selected_team = st.selectbox("Select Team Number", teams_list)

        # Overview from Per_Team
        team_summary = df_per_team[df_per_team[team_col_per_team] == selected_team]
        st.markdown("#### 📊 Overall Team Aggregates (from `Per_Team` sheet)")
        st.dataframe(team_summary, use_container_width=True)

        # Detailed Match History from Data sheet
        st.divider()
        st.markdown("#### 📝 Match History Breakdown (from `Data` sheet)")
        if not df_match_data.empty and team_col_match:
            team_matches = df_match_data[df_match_data[team_col_match] == selected_team]
            if not team_matches.empty:
                st.dataframe(team_matches, use_container_width=True)
            else:
                st.info(f"No specific match records found for Team {selected_team} in 'Data' sheet.")

# -----------------------------------------------------------------------------
# VIEW 4: LEADERBOARD & DRAFT BOARD
# -----------------------------------------------------------------------------
elif view_mode == "Leaderboard & Draft Board":
    st.subheader("📊 Team Leaderboard & Pick List (`Per_Team` Sheet)")

    if df_per_team.empty:
        st.warning("No data found in 'Per_Team' sheet.")
    else:
        numeric_cols = list(df_per_team.select_dtypes(include=[np.number]).columns)
        
        if numeric_cols:
            sort_metric = st.selectbox("Sort Leaderboard By", numeric_cols, index=0)
            sorted_df = df_per_team.sort_values(by=sort_metric, ascending=False).reset_index(drop=True)
            
            st.dataframe(
                sorted_df.style.highlight_max(axis=0, color="#d4edda"),
                use_container_width=True
            )
        else:
            st.dataframe(df_per_team, use_container_width=True)

# -----------------------------------------------------------------------------
# VIEW 5: PLAYOFF SIMULATOR
# -----------------------------------------------------------------------------
elif view_mode == "Playoff Simulator":
    st.subheader("🏆 Alliance Playoff Simulator")

    if df_per_team.empty:
        st.warning("No team data found in 'Per_Team' sheet.")
    else:
        teams_list = sorted(df_per_team[team_col_per_team].unique())
        numeric_cols = list(df_per_team.select_dtypes(include=[np.number]).columns)

        if not numeric_cols:
            st.error("No numeric columns found in 'Per_Team' sheet to run simulation.")
        else:
            score_col = st.selectbox("Select Metric for Match Simulation", numeric_cols)

            col_a, col_b = st.columns(2)
            with col_a:
                a1 = st.selectbox("Alliance 1 - Captain", teams_list, index=0)
                a2 = st.selectbox("Alliance 1 - Pick 1", teams_list, index=min(1, len(teams_list)-1))

            with col_b:
                b1 = st.selectbox("Alliance 2 - Captain", teams_list, index=min(2, len(teams_list)-1))
                b2 = st.selectbox("Alliance 2 - Pick 1", teams_list, index=min(3, len(teams_list)-1))

            if st.button("🚀 Run Simulation"):
                val_a1 = df_per_team[df_per_team[team_col_per_team] == a1][score_col].values[0]
                val_a2 = df_per_team[df_per_team[team_col_per_team] == a2][score_col].values[0]
                val_b1 = df_per_team[df_per_team[team_col_per_team] == b1][score_col].values[0]
                val_b2 = df_per_team[df_per_team[team_col_per_team] == b2][score_col].values[0]

                score_a = val_a1 + val_a2
                score_b = val_b1 + val_b2

                m1, m2, m3 = st.columns(3)
                m1.metric("Alliance 1 Total", f"{score_a:.1f}")
                m2.metric("Alliance 2 Total", f"{score_b:.1f}")

                diff = score_a - score_b
                m3.metric("Projected Margin", f"{abs(diff):.1f}", delta=f"{'Alliance 1' if diff > 0 else 'Alliance 2'} Advantage")