import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="FRC Scouting Hub", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Navigation Bar Container */
    [data-testid="stHorizontalBlock"] {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 10px;
        align-items: center;
    }
    div.stButton > button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stButton > button[kind="primary"] { background-color: #4F8BF9 !important; color: white !important; border: 1px solid #FFFFFF; }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: 800; color: #FFFFFF !important; }
    
    .team-info-box {
        padding: 10px;
        border-radius: 8px;
        border-left: 6px solid;
        background-color: rgba(255, 255, 255, 0.05);
        margin-bottom: 8px;
        font-size: 13px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING & CLEANING ---
@st.cache_data
def load_frc_data():
    file_name = "scouting_data.xlsx"
    data = pd.read_excel(file_name, sheet_name="Data_Input")
    for col in ['+1', '+3', '+5']:
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    data['Total Fuel'] = data['+1'] + data['+3'] + data['+5']
    data['Moved?'] = pd.to_numeric(data['Moved?'], errors='coerce').fillna(0)
    
    pit = pd.read_excel(file_name, sheet_name="Pit_Input")
    schema = pd.read_excel(file_name, sheet_name="Scouting schema", header=1)
    schema.columns = schema.columns.str.strip()
    team_cols = ['red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3']
    for col in team_cols:
        schema[col] = pd.to_numeric(schema[col], errors='coerce').fillna(0).astype(int)
    
    schema = schema.dropna(subset=['match_number'])
    return data, pit, schema

try:
    df, pit_df, schema_df = load_frc_data()
except Exception as e:
    st.error(f"Excel Error: {e}")
    st.stop()

# --- 2. HELPERS ---
def get_team_stats(team_num):
    t_data = df[df['Team Number'] == team_num]
    if t_data.empty: 
        return {"avg": 0, "auto_move": 0, "climb_pref": "N/A", "last_note": "No data", "driver": 0}
    avg = (t_data['+1'].mean() + (t_data['+3'].mean() * 3) + (t_data['+5'].mean() * 5))
    move = t_data['Moved?'].mean() * 100
    climb_modes = t_data['Climbing'].dropna().mode()
    climb = climb_modes.iloc[0] if not climb_modes.empty else "N/A"
    driver = t_data['driver skill'].mean() if 'driver skill' in t_data else 0
    note_df = t_data.dropna(subset=['Comments'])
    note = note_df.iloc[-1]['Comments'] if not note_df.empty else "No notes"
    return {"avg": avg, "auto_move": move, "climb_pref": climb, "last_note": note, "driver": driver}

# --- 3. TOP NAVIGATION BAR ---
if 'view' not in st.session_state:
    st.session_state.view = "Field Map"

nav_cols = st.columns([1.2, 1.2, 1.2, 1.5, 1.5, 0.6])
with nav_cols[0]:
    if st.button("🗺️ Field Map", type="primary" if st.session_state.view == "Field Map" else "secondary"):
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
        selected_match = st.selectbox("Match", m_list, label_visibility="collapsed")
        row = schema_df[schema_df['match_number'] == selected_match].iloc[0]
        red_teams = [int(row['red1']), int(row['red2']), int(row['red3'])]
        blue_teams = [int(row['blue1']), int(row['blue2']), int(row['blue3'])]
        red_pred = sum(get_team_stats(t)['avg'] for t in red_teams if t > 0)
        blue_pred = sum(get_team_stats(t)['avg'] for t in blue_teams if t > 0)
    else:
        t_list = sorted(set(df['Team Number'].unique()) | set(pit_df['team_number'].unique()))
        selected_team = st.selectbox("Team", [t for t in t_list if t > 0], label_visibility="collapsed")

with nav_cols[4]:
    if st.session_state.view != "Deep Dive":
        st.markdown(f"🔴 **{round(red_pred,1)}** vs 🔵 **{round(blue_pred,1)}**")

with nav_cols[5]:
    if st.button("🔄 Sync"):
        st.cache_data.clear(); st.rerun()

st.divider()

# --- 4. VIEW: FIELD MAP ---
if st.session_state.view == "Field Map":
    st.markdown(f"### 🏟️ Match {selected_match} Strategic Map")
    
    red_col, field_col, blue_col = st.columns([1, 2.5, 1])
    
    def info_card(team_num, color):
        s = get_team_stats(team_num)
        st.markdown(f"""<div class="team-info-box" style="border-left-color: {color};">
            <b>Team {team_num}</b><br>Avg: {round(s['avg'], 1)} | Climb: {s['climb_pref']}<br>Auto: {round(s['auto_move'])}% | Note: {s['last_note']}
        </div>""", unsafe_allow_html=True)

    with red_col:
        st.subheader("🔴 Red")
        for t in red_teams: info_card(t, "#FF4B4B")
            
    with field_col:
        if os.path.exists("field.png"):
            with open("field.png", "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            # DRAGGABLE ENGINE FOR 6 ROBOTS
            html_content = f"""
            <div id="field-container" style="position: relative; width: 100%; border: 2px solid #555; border-radius: 10px; overflow: hidden; user-select: none;">
                <img src="data:image/png;base64,{img_b64}" style="width: 100%; display: block; pointer-events: none;">
                <div class="bot red" id="r1" style="left: 5%; top: 20%;">{red_teams[0]}</div>
                <div class="bot red" id="r2" style="left: 5%; top: 45%;">{red_teams[1]}</div>
                <div class="bot red" id="r3" style="left: 5%; top: 70%;">{red_teams[2]}</div>
                <div class="bot blue" id="b1" style="right: 5%; top: 20%;">{blue_teams[0]}</div>
                <div class="bot blue" id="b2" style="right: 5%; top: 45%;">{blue_teams[1]}</div>
                <div class="bot blue" id="b3" style="right: 5%; top: 70%;">{blue_teams[2]}</div>
            </div>
            <style>
                .bot {{
                    position: absolute; width: 50px; height: 50px; border-radius: 50%;
                    color: white; font-family: sans-serif; font-weight: bold; font-size: 11px;
                    display: flex; align-items: center; justify-content: center;
                    border: 2px solid white; box-shadow: 0 4px 8px black;
                    cursor: move; z-index: 100; touch-action: none;
                }}
                .red {{ background: rgba(255, 75, 75, 0.9); }}
                .blue {{ background: rgba(31, 119, 180, 0.9); }}
            </style>
            <script>
                const container = document.getElementById('field-container');
                const bots = document.querySelectorAll('.bot');
                
                bots.forEach(bot => {{
                    let isDragging = false;
                    let offsetX, offsetY;

                    bot.addEventListener('mousedown', (e) => {{
                        isDragging = true;
                        offsetX = e.clientX - bot.getBoundingClientRect().left;
                        offsetY = e.clientY - bot.getBoundingClientRect().top;
                    }});

                    document.addEventListener('mousemove', (e) => {{
                        if (!isDragging) return;
                        const rect = container.getBoundingClientRect();
                        let x = ((e.clientX - rect.left - offsetX) / rect.width) * 100;
                        let y = ((e.clientY - rect.top - offsetY) / rect.height) * 100;
                        bot.style.left = Math.max(0, Math.min(94, x)) + '%';
                        bot.style.top = Math.max(0, Math.min(92, y)) + '%';
                    }});

                    document.addEventListener('mouseup', () => isDragging = false);
                }});
            </script>
            """
            st.components.v1.html(html_content, height=550)

    with blue_col:
        st.subheader("🔵 Blue")
        for t in blue_teams: info_card(t, "#1F77B4")

# --- 5. VIEW: OVERVIEW ---
elif st.session_state.view == "Overview":
    st.title(f"📊 Match {selected_match} Alliance Comparison")
    o1, o2 = st.columns(2)
    def detail_card(t):
        s = get_team_stats(t)
        with st.container(border=True):
            st.markdown(f"#### Team {t}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Avg", round(s['avg'], 1))
            c2.metric("Climb", s['climb_pref'])
            c3.metric("Auto%", f"{round(s['auto_move'])}%")
            st.write(f"**Notes:** {s['last_note']}")
    with o1:
        st.subheader("🔴 Red")
        for t in red_teams: detail_card(t)
    with o2:
        st.subheader("🔵 Blue")
        for t in blue_teams: detail_card(t)

# --- 6. VIEW: DEEP DIVE ---
elif st.session_state.view == "Deep Dive":
    st.title(f"🤖 Team {selected_team} Performance")
    t_data = df[df['Team Number'] == selected_team]
    merged = pd.merge(schema_df[(schema_df[['red1','red2','red3','blue1','blue2','blue3']] == selected_team).any(axis=1)][['match_number']], 
                      t_data, left_on='match_number', right_on='Match Number', how='left')
    merged['X_Label'] = merged['match_number'].apply(lambda x: f"M{int(x)}")
    fig = px.line(merged.dropna(subset=['Total Fuel']), x="X_Label", y="Total Fuel", markers=True, template="plotly_dark")
    fig.update_layout(xaxis_type='category', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(t_data.dropna(subset=['Comments'])[['Match Number', 'Comments']], use_container_width=True, hide_index=True)