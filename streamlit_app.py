import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="FRC Scouting Hub", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main .block-container { max-width: 100%; padding: 0.5rem 1rem; }
    
    /* Sidebar Prediction Box */
    .sb-predict-box {
        padding: 12px; background: rgba(255, 255, 255, 0.05); border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1); margin-top: 10px;
    }
    
    /* Team Cards - High Density */
    .team-info-box-detailed {
        padding: 8px; border-radius: 8px; border-top: 4px solid;
        background-color: rgba(255, 255, 255, 0.08); font-size: 12px;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.3); margin-bottom: 2px;
    }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 1px; }
    .note-text { font-style: italic; font-size: 10px; color: #BDC3C7; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 3px; padding-top: 2px; height: 32px; overflow: hidden; }
    
    /* Side labels for Field Map - Fixed Vertical Centering */
    .field-side-label { text-align: center; display: flex; flex-direction: column; justify-content: center; height: 400px; }
    .side-big { font-size: 40px; font-weight: 900; color: #4F8BF9; line-height: 1; }
    .side-small { font-size: 11px; color: #BDC3C7; text-transform: uppercase; margin-top: -5px; }

    /* Gap/Clipping mitigation */
    [data-testid="stHtml"] { padding: 0 !important; margin: 0 !important; }
    iframe { display: block; margin: 0 auto; border: none; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING ---
@st.cache_data
def load_frc_data():
    file_name = "scouting_data.xlsx"
    schema = pd.read_excel(file_name, sheet_name="Matches", header=0)
    schema.columns = schema.columns.str.strip()
    team_cols = ['red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3']
    for col in team_cols:
        schema[col] = schema[col].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    
    data = pd.read_excel(file_name, sheet_name="Data_Input")
    data.columns = data.columns.str.strip()
    for col in ['+1', '+3', '+5', 'Amount in Hub']:
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    data['Total Score'] = data['+1'] + data['+3'] + data['+5']
    
    def clean_bool(val):
        v = str(val).lower()
        return 1 if v in ['true', '1', '1.0', 'yes', 'y'] else 0

    data['Moved_Num'] = data['Moved?'].apply(clean_bool)
    data['Died_Num'] = data['Died?'].apply(clean_bool)
    data['Tipped_Num'] = data['Tipped/Fell Over?'].apply(clean_bool)
    data['Defense_Num'] = data['Defence/ to other side'].apply(clean_bool)
    for col in ['PickUp Ground', 'PickUP Human Player', 'PickUp Depot']:
        data[col] = data[col].apply(clean_bool)
    
    pit = pd.read_excel(file_name, sheet_name="Pit_Input")
    pit.columns = pit.columns.str.strip()
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
        return {"avg": 0, "count": 0, "auto_move": 0, "climb_pref": "N/A", "last_note": "No data", "driver": 0, "hub": 0}
    avg = t_data['Total Score'].mean()
    hub = t_data['Amount in Hub'].mean()
    move = t_data['Moved_Num'].mean() * 100
    climb_modes = t_data['Climbing'].dropna().mode()
    climb = climb_modes.iloc[0] if not climb_modes.empty else "N/A"
    driver = t_data['driver skill'].mean() if 'driver skill' in t_data else 0
    note_df = t_data.dropna(subset=['Comments'])
    note = note_df.iloc[-1]['Comments'] if not note_df.empty else "No notes"
    return {"avg": avg, "count": int(t_data['Match Number'].count()), "auto_move": move, "climb_pref": climb, "last_note": note, "driver": driver, "hub": hub}

# --- 3. SIDEBAR NAVIGATION & CONTROLS ---
with st.sidebar:
    st.title("⚙️ HUB CONTROL")
    view = st.radio("Navigation", ["🗺️ Field Map", "📊 Overview", "🤖 Deep Dive"], label_visibility="collapsed")
    st.divider()

    if view in ["🗺️ Field Map", "📊 Overview"]:
        m_list = sorted(schema_df['match_number'].unique().astype(int))
        selected_match = st.selectbox("Select Match", m_list, key="m_sel")
        
        row = schema_df[schema_df['match_number'] == selected_match].iloc[0]
        red_teams = [int(row['red1']), int(row['red2']), int(row['red3'])]
        blue_teams = [int(row['blue1']), int(row['blue2']), int(row['blue3'])]
        red_pred = sum(get_team_stats(t)['avg'] for t in red_teams if t > 0)
        blue_pred = sum(get_team_stats(t)['avg'] for t in blue_teams if t > 0)

        st.markdown(f"""
        <div class="sb-predict-box">
            <div style="font-size:11px; color:grey; margin-bottom:4px;">PREDICTED SCORES</div>
            <div style="color:#FF4B4B; font-weight:bold; font-size:22px;">RED: {round(red_pred,1)}</div>
            <div style="color:#1F77B4; font-weight:bold; font-size:22px;">BLUE: {round(blue_pred,1)}</div>
            <div style="font-size:11px; color:grey; margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:4px;">DIFF: {round(red_pred - blue_pred, 1)}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        t_list = sorted(set(df['Team Number'].unique()) | set(pit_df['team_number'].unique()))
        selected_team = st.selectbox("Select Team", [t for t in t_list if t > 0], key="t_sel")

    # Sync at the bottom
    st.markdown("<div style='height: 30vh;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Sync Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. VIEW: FIELD MAP ---
if view == "🗺️ Field Map":
    def detailed_card(team_num, color_hex):
        s = get_team_stats(team_num)
        st.markdown(f"""
        <div class="team-info-box-detailed" style="border-top-color: {color_hex};">
            <div class="stat-row"><b>{team_num}</b> <span>{s['count']} matches</span></div>
            <div class="stat-row">Avg: <b>{round(s['avg'], 1)}</b> <span>Hub: {round(s['hub'], 1)}</span></div>
            <div class="stat-row">Climb: {s['climb_pref']} <span>Skill: {round(s['driver'], 1)}</span></div>
            <div class="note-text">{s['last_note'][:75]}...</div>
        </div>
        """, unsafe_allow_html=True)

    # Red Cards (Top)
    r_cols = st.columns(3)
    for i, t in enumerate(red_teams):
        with r_cols[i]: detailed_card(t, "#FF4B4B")

    # Field Row with side labels
    f_left, f_mid, f_right = st.columns([0.8, 4.6, 0.8])
    
    with f_left:
        st.markdown(f"""<div class="field-side-label">
            <div class="side-big">{selected_match}</div>
            <div class="side-small">MATCH</div>
        </div>""", unsafe_allow_html=True)

    with f_mid:
        if os.path.exists("field.png"):
            with open("field.png", "rb") as f: img_b64 = base64.b64encode(f.read()).decode()
            html_content = f"""
            <div id="field-container" style="position: relative; width: 100%; max-width: 1000px; margin: 0 auto; border: 2px solid #555; border-radius: 12px; overflow: hidden; touch-action: none; background-color: #000;">
                <img src="data:image/png;base64,{img_b64}" style="width: 100%; height: auto; display: block; pointer-events: none;">
                <div class="bot red" style="left: 10%; top: 15%;">{red_teams[0]}</div>
                <div class="bot red" style="left: 10%; top: 40%;">{red_teams[1]}</div>
                <div class="bot red" style="left: 10%; top: 65%;">{red_teams[2]}</div>
                <div class="bot blue" style="right: 10%; top: 15%;">{blue_teams[0]}</div>
                <div class="bot blue" style="right: 10%; top: 40%;">{blue_teams[1]}</div>
                <div class="bot blue" style="right: 10%; top: 65%;">{blue_teams[2]}</div>
            </div>
            <style>
                .bot {{
                    position: absolute; width: 34px; height: 34px; border-radius: 50%;
                    color: white; font-family: sans-serif; font-weight: bold; font-size: 8px;
                    display: flex; align-items: center; justify-content: center;
                    border: 2px solid white; box-shadow: 0 4px 8px black; cursor: move; z-index: 100;
                }}
                .red {{ background: rgba(255, 75, 75, 0.95); }}
                .blue {{ background: rgba(31, 119, 180, 0.95); }}
            </style>
            <script>
                const container = document.getElementById('field-container');
                const bots = document.querySelectorAll('.bot');
                bots.forEach(bot => {{
                    let isDragging = false; let offsetX, offsetY;
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
                        bot.style.left = Math.max(0, Math.min(96, x)) + '%';
                        bot.style.top = Math.max(0, Math.min(95, y)) + '%';
                        if(e.type.includes('touch')) e.preventDefault();
                    }};
                    const end = () => isDragging = false;
                    bot.addEventListener('mousedown', start); bot.addEventListener('touchstart', start, {{passive: false}});
                    document.addEventListener('mousemove', move); document.addEventListener('touchmove', move, {{passive: false}});
                    document.addEventListener('mouseup', end); document.addEventListener('touchend', end);
                }});
            </script>
            """
            st.components.v1.html(html_content, height=450)

    with f_right:
        st.markdown(f"""<div class="field-side-label">
            <div style="color:#FF4B4B; font-weight:800; font-size:10px;">RED</div>
            <div style="font-size:24px; font-weight:900;">{round(red_pred,1)}</div>
            <div style="height:25px;"></div>
            <div style="color:#1F77B4; font-weight:800; font-size:10px;">BLUE</div>
            <div style="font-size:24px; font-weight:900;">{round(blue_pred,1)}</div>
        </div>""", unsafe_allow_html=True)

    # Blue Cards (Bottom)
    b_cols = st.columns(3)
    for i, t in enumerate(blue_teams):
        with b_cols[i]: detailed_card(t, "#1F77B4")

# --- 5. VIEW: OVERVIEW ---
elif view == "📊 Overview":
    st.title(f"Match {selected_match} Alliance Intelligence")
    o1, o2 = st.columns(2)
    def detail_card_full(t):
        s = get_team_stats(t)
        with st.container(border=True):
            st.markdown(f"#### {t}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Score", round(s['avg'], 1)); c2.metric("Climb", s['climb_pref'])
            c3.metric("Auto Move", f"{round(s['auto_move'])}%"); c4.metric("Samples", s['count'])
            st.info(f"**Last Note:** {s['last_note']}")
    with o1:
        st.subheader("🔴 Red Alliance")
        for t in red_teams: detail_card_full(t)
    with o2:
        st.subheader("🔵 Blue Alliance")
        for t in blue_teams: detail_card_full(t)

# --- 6. VIEW: DEEP DIVE ---
elif view == "🤖 Deep Dive":
    sel_t = selected_team
    t_data = df[df['Team Number'] == sel_t]
    stats = get_team_stats(sel_t)
    p_data = pit_df[pit_df['team_number'] == sel_t]
    name = p_data.iloc[0]['team name'] if not p_data.empty else "Unknown Team"

    st.markdown(f"<div style='font-size: 48px; color: #4F8BF9; font-weight: 800;'>{sel_t}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size: 22px; color: #BDC3C7; margin-bottom: 10px;'>{name}</div>", unsafe_allow_html=True)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Avg Score", round(stats['avg'], 1))
    m2.metric("Auto%", f"{round(stats['auto_move'])}%")
    m3.metric("Avg Driver", f"{round(stats['driver'], 1)}/5")
    m4.metric("Climb Pref", stats['climb_pref'])
    m5.metric("Matches", stats['count'])

    st.divider()
    col_l, col_r = st.columns([2, 1.2])
    
    with col_l:
        st.subheader("📊 Performance Trend")
        team_matches = schema_df[(schema_df[['red1','red2','red3','blue1','blue2','blue3']] == sel_t).any(axis=1)][['match_number']]
        merged = pd.merge(team_matches, df[df['Team Number'] == sel_t], left_on='match_number', right_on='Match Number', how='left')
        merged['X_Label'] = merged['match_number'].apply(lambda x: f"M{int(x)}")
        score_history = merged.dropna(subset=['Total Score'])
        if not score_history.empty:
            st.plotly_chart(px.line(score_history, x="X_Label", y="Total Score", markers=True, template="plotly_dark", height=280), use_container_width=True)

        c_h1, c_h2 = st.columns(2)
        with c_h1:
            st.markdown("**Starting Position**")
            pos_data = t_data['Starting Position'].dropna().value_counts().reset_index()
            pos_data.columns = ['Pos', 'Count']
            if not pos_data.empty:
                st.plotly_chart(px.pie(pos_data, values='Count', names='Pos', height=220, template="plotly_dark"), use_container_width=True)
        with c_h2:
            st.markdown("**Pickup Usage %**")
            pickups = t_data[['PickUp Ground', 'PickUP Human Player', 'PickUp Depot']].mean().fillna(0) * 100
            df_pick = pickups.reset_index()
            df_pick.columns = ['Type', 'Usage']
            st.plotly_chart(px.bar(df_pick, x='Type', y='Usage', height=220, template="plotly_dark"), use_container_width=True)

    with col_r:
        st.subheader("🪜 Climb Dist.")
        climb_dist = t_data['Climbing'].dropna().value_counts().reset_index()
        climb_dist.columns = ['Level', 'Count']
        if not climb_dist.empty:
            st.plotly_chart(px.bar(climb_dist, x='Level', y='Count', template="plotly_dark", height=220), use_container_width=True)
        
        if not p_data.empty:
            st.subheader("🛠️ Pit Specs")
            st.dataframe(p_data.T, use_container_width=True)
        
        st.subheader("⚠️ Reliability")
        died = int(t_data['Died_Num'].sum())
        tipped = int(t_data['Tipped_Num'].sum())
        if died > 0: st.error(f"Died in {died} matches")
        if tipped > 0: st.warning(f"Tipped in {tipped} matches")

    st.divider()
    st.subheader("💬 Match Logs")
    notes_df = t_data.dropna(subset=['Comments'])[['Match Number', 'Comments', 'driver skill']].sort_values('Match Number', ascending=False)
    st.table(notes_df)