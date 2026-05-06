import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="FRC Scouting Hub", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM CSS: VERTICAL CENTERING & LAYOUT ---
st.markdown("""
    <style>
    /* Center the app and handle vertical alignment */
    .main .block-container {
        max-width: 1400px;
        margin: auto;
        padding-top: 1rem;
    }

    /* Force the columns in the Field Map to align by their centers (Vertical Centering) */
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-self: center;
    }

    /* Navigation Bar Container */
    [data-testid="stHorizontalBlock"] {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 5px;
        align-items: center;
    }

    div.stButton > button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stButton > button[kind="primary"] { background-color: #4F8BF9 !important; color: white !important; border: 1px solid #FFFFFF; }
    
    [data-testid="stMetricValue"] { font-size: 20px; font-weight: 800; color: #FFFFFF !important; }
    
    /* Team Info Cards */
    .team-info-box {
        padding: 10px;
        border-radius: 8px;
        border-left: 6px solid;
        background-color: rgba(255, 255, 255, 0.07);
        margin-bottom: 8px;
        font-size: 13px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
    }
    .reliability-badge {
        font-size: 10px;
        background: rgba(255,255,255,0.15);
        padding: 1px 6px;
        border-radius: 10px;
        color: #BDC3C7;
        float: right;
    }
    .match-header {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 900;
        margin: 0;
        color: #4F8BF9;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING ---
@st.cache_data
def load_frc_data():
    file_name = "scouting_data.xlsx"
    
    # Load Main Data
    data = pd.read_excel(file_name, sheet_name="Data_Input")
    for col in ['+1', '+3', '+5']:
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    data['Total Fuel'] = data['+1'] + data['+3'] + data['+5']
    data['Moved?'] = data['Moved?'].astype(str).str.lower().map({'true': 1, '1': 1, 'false': 0, '0': 0}).fillna(0)
    
    # Load Pit Data
    pit = pd.read_excel(file_name, sheet_name="Pit_Input")
    
    # Load Matches tab
    schema = pd.read_excel(file_name, sheet_name="Matches", header=0)
    schema.columns = schema.columns.str.strip()
    
    # Clean team numbers (Extract digits)
    team_cols = ['red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3']
    for col in team_cols:
        schema[col] = schema[col].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    
    schema = schema.dropna(subset=['match_number'])
    return data, pit, schema

try:
    df, pit_df, schema_df = load_frc_data()
except Exception as e:
    st.error(f"Excel Error: {e}. Check if 'Matches' tab exists.")
    st.stop()

# --- 2. HELPERS ---
def get_team_stats(team_num):
    t_data = df[df['Team Number'] == team_num]
    if t_data.empty: 
        return {"avg": 0, "count": 0, "auto_move": 0, "climb_pref": "N/A", "last_note": "No data", "driver": 0}
    
    match_count = int(t_data['Total Fuel'].count())
    avg = (t_data['+1'].mean() + (t_data['+3'].mean() * 3) + (t_data['+5'].mean() * 5))
    move = t_data['Moved?'].mean() * 100
    climb_modes = t_data['Climbing'].dropna().mode()
    climb = climb_modes.iloc[0] if not climb_modes.empty else "N/A"
    driver = t_data['driver skill'].mean() if 'driver skill' in t_data else 0
    note_df = t_data.dropna(subset=['Comments'])
    note = note_df.iloc[-1]['Comments'] if not note_df.empty else "No notes"
    
    return {"avg": avg, "count": match_count, "auto_move": move, "climb_pref": climb, "last_note": note, "driver": driver}

# --- 3. NAVIGATION BAR (Selectors Integrated) ---
if 'view' not in st.session_state:
    st.session_state.view = "Field Map"

nav_cols = st.columns([1, 1, 1, 1.2, 2, 0.6])

with nav_cols[0]:
    if st.button("🗺️ Field", type="primary" if st.session_state.view == "Field Map" else "secondary"):
        st.session_state.view = "Field Map"; st.rerun()
with nav_cols[1]:
    if st.button("📊 Overview", type="primary" if st.session_state.view == "Overview" else "secondary"):
        st.session_state.view = "Overview"; st.rerun()
with nav_cols[2]:
    if st.button("🤖 Deep Dive", type="primary" if st.session_state.view == "Deep Dive" else "secondary"):
        st.session_state.view = "Deep Dive"; st.rerun()

with nav_cols[3]:
    if st.session_state.view in ["Field Map", "Overview"]:
        m_list = sorted(schema_df['match_number'].unique().astype(int))
        selected_match = st.selectbox("Match Select", m_list, label_visibility="collapsed", key="m_sel")
        row = schema_df[schema_df['match_number'] == selected_match].iloc[0]
        red_teams = [int(row['red1']), int(row['red2']), int(row['red3'])]
        blue_teams = [int(row['blue1']), int(row['blue2']), int(row['blue3'])]
        red_pred = sum(get_team_stats(t)['avg'] for t in red_teams if t > 0)
        blue_pred = sum(get_team_stats(t)['avg'] for t in blue_teams if t > 0)
    else:
        t_list = sorted(set(df['Team Number'].unique()) | set(pit_df['team_number'].unique()))
        selected_team = st.selectbox("Team Select", [t for t in t_list if t > 0], label_visibility="collapsed", key="t_sel")

with nav_cols[4]:
    if st.session_state.view != "Deep Dive":
        st.markdown(f"<div style='padding-top:10px;'>🔴 <b>{round(red_pred,1)}</b> pts vs 🔵 <b>{round(blue_pred,1)}</b> pts</div>", unsafe_allow_html=True)

with nav_cols[5]:
    if st.button("🔄 Sync"):
        st.cache_data.clear(); st.rerun()

# Restored Match Number Header
if st.session_state.view in [ "Overview"]:
    st.markdown(f"<h1 class='match-header'>MATCH {selected_match}</h1>", unsafe_allow_html=True)

st.divider()

# --- 4. VIEW: FIELD MAP ---
if st.session_state.view == "Field Map":
    # Columns center vertically via CSS align-self: center
    red_col, field_col, blue_col = st.columns([1.2, 2.5, 1.2])
    
    def info_card(team_num, color):
        s = get_team_stats(team_num)
        rel_color = "#FF4B4B" if s['count'] < 2 else "#BDC3C7"
        st.markdown(f"""<div class="team-info-box" style="border-left-color: {color};">
            <span class="reliability-badge" style="color:{rel_color};">{s['count']} matches</span>
            <b>Team {team_num}</b><br>
            Avg: <b>{round(s['avg'], 1)}</b> | Climb: {s['climb_pref']}<br>
            Auto: {round(s['auto_move'])}% | Notes: {s['last_note'][:40]}...
        </div>""", unsafe_allow_html=True)

    with red_col:
        for t in red_teams: info_card(t, "#FF4B4B")
            
    with field_col:
        st.markdown(f"<h1 class='match-header'>MATCH {selected_match}</h1>", unsafe_allow_html=True)
        if os.path.exists("field.png"):
            with open("field.png", "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            html_content = f"""
            <div id="field-container" style="position: relative; width: 100%; border: 2px solid #555; border-radius: 10px; overflow: hidden; user-select: none; touch-action: none;">
                <img src="data:image/png;base64,{img_b64}" style="width: 100%; display: block; pointer-events: none;">
                <div class="bot red" style="left: 10%; top: 20%;">{red_teams[0]}</div>
                <div class="bot red" style="left: 10%; top: 45%;">{red_teams[1]}</div>
                <div class="bot red" style="left: 10%; top: 70%;">{red_teams[2]}</div>
                <div class="bot blue" style="right: 10%; top: 20%;">{blue_teams[0]}</div>
                <div class="bot blue" style="right: 10%; top: 45%;">{blue_teams[1]}</div>
                <div class="bot blue" style="right: 10%; top: 70%;">{blue_teams[2]}</div>
            </div>
            <style>
                .bot {{
                    position: absolute; width: 50px; height: 50px; border-radius: 50%;
                    color: white; font-family: sans-serif; font-weight: bold; font-size: 11px;
                    display: flex; align-items: center; justify-content: center;
                    border: 3px solid white; box-shadow: 0 4px 8px black;
                    cursor: move; z-index: 100;
                }}
                .red {{ background: rgba(255, 75, 75, 0.95); }}
                .blue {{ background: rgba(31, 119, 180, 0.95); }}
            </style>
            <script>
                const container = document.getElementById('field-container');
                const bots = document.querySelectorAll('.bot');
                bots.forEach(bot => {{
                    let isDragging = false;
                    let offsetX, offsetY;
                    const start = (e) => {{
                        isDragging = true;
                        const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
                        const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
                        offsetX = clientX - bot.getBoundingClientRect().left;
                        offsetY = clientY - bot.getBoundingClientRect().top;
                    }};
                    const move = (e) => {{
                        if (!isDragging) return;
                        const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
                        const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
                        const rect = container.getBoundingClientRect();
                        let x = ((clientX - rect.left - offsetX) / rect.width) * 100;
                        let y = ((clientY - rect.top - offsetY) / rect.height) * 100;
                        bot.style.left = Math.max(0, Math.min(93, x)) + '%';
                        bot.style.top = Math.max(0, Math.min(91, y)) + '%';
                        if(e.type.includes('touch')) e.preventDefault();
                    }};
                    const end = () => isDragging = false;
                    bot.addEventListener('mousedown', start);
                    bot.addEventListener('touchstart', start, {{passive: false}});
                    document.addEventListener('mousemove', move);
                    document.addEventListener('touchmove', move, {{passive: false}});
                    document.addEventListener('mouseup', end);
                    document.addEventListener('touchend', end);
                }});
            </script>
            """
            st.components.v1.html(html_content, height=550)
        else:
            st.warning("Please upload 'field.png'.")

    with blue_col:
        for t in blue_teams: info_card(t, "#1F77B4")

# --- 5. VIEW: OVERVIEW ---
elif st.session_state.view == "Overview":
    o1, o2 = st.columns(2)
    def detail_card(t):
        s = get_team_stats(t)
        with st.container(border=True):
            st.markdown(f"#### Team {t}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg", round(s['avg'], 1))
            c2.metric("Climb", s['climb_pref'])
            c3.metric("Auto%", f"{round(s['auto_move'])}%")
            c4.metric("Matches", s['count'])
            st.info(f"**Last Scout Comment:** {s['last_note']}")
    with o1:
        st.subheader("🔴 Red Alliance")
        for t in red_teams: detail_card(t)
    with o2:
        st.subheader("🔵 Blue Alliance")
        for t in blue_teams: detail_card(t)

# --- 6. VIEW: DEEP DIVE ---
elif st.session_state.view == "Deep Dive":
    t_data = df[df['Team Number'] == selected_team]
    team_matches = schema_df[(schema_df[['red1','red2','red3','blue1','blue2','blue3']] == selected_team).any(axis=1)][['match_number']]
    merged = pd.merge(team_matches, t_data, left_on='match_number', right_on='Match Number', how='left')
    merged['X_Label'] = merged['match_number'].apply(lambda x: f"M{int(x)}")
    
    c1, c2 = st.columns([1, 3])
    c1.metric("Total Matches", int(t_data['Total Fuel'].count()))
    
    fig = px.line(merged.dropna(subset=['Total Fuel']), x="X_Label", y="Total Fuel", markers=True, template="plotly_dark")
    fig.update_layout(xaxis_type='category', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    n1, n2 = st.columns([1, 2])
    with n1:
        st.subheader("Pit Scouting")
        p = pit_df[pit_df['team_number'] == selected_team]
        if not p.empty: st.write(p.T)
    with n2:
        st.subheader("Comments History")
        st.dataframe(t_data.dropna(subset=['Comments'])[['Match Number', 'Comments']], use_container_width=True, hide_index=True)