import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="FRC Scouting Hub", layout="wide", initial_sidebar_state="expanded")

# --- INITIALIZE SESSION STATE ---
if 'alliances' not in st.session_state:
    st.session_state.alliances = {i: {"c": 0, "p1": 0, "p2": 0} for i in range(1, 9)}

if 'm_sel_val' not in st.session_state:
    st.session_state.m_sel_val = 1 

if 'active_team_selection' not in st.session_state:
    st.session_state.active_team_selection = None

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main .block-container { max-width: 100%; padding: 0.5rem 1rem; }
    
    .sb-predict-box {
        padding: 12px; background: rgba(255, 255, 255, 0.05); border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1); margin-top: 10px;
    }
    
    .team-info-box-detailed {
        padding: 8px; border-radius: 8px; border-top: 4px solid;
        background-color: rgba(255, 255, 255, 0.08); font-size: 12px;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.3); margin-bottom: 2px;
    }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 1px; }
    .note-text { font-style: italic; font-size: 10px; color: #BDC3C7; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 3px; padding-top: 2px; height: 32px; overflow: hidden; }
    
    .field-side-label { text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 380px; }
    .side-big { font-size: 42px; font-weight: 900; color: #4F8BF9; line-height: 1; }
    .side-small { font-size: 11px; color: #BDC3C7; text-transform: uppercase; margin-top: -5px; }

    .alliance-container { background: rgba(255,255,255,0.03); padding: 10px; border-radius: 10px; border: 1px solid #444; margin-bottom: 10px; }
    .staging-area { background: rgba(79, 139, 249, 0.2); padding: 15px; border-radius: 10px; border: 2px solid #4F8BF9; margin-bottom: 20px; text-align: center; }
    
    /* Fast select button alignment */
    .draft-row { display: flex; align-items: center; gap: 10px; width: 100%; }
    
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
    st.error(f"Data Load Error: {e}")
    st.stop()

# --- 2. HELPERS ---
def get_team_stats(team_num):
    t_data = df[df['Team Number'] == team_num]
    if t_data.empty: 
        return {"avg": 0, "count": 0, "auto_move": 0, "climb_pref": "N/A", "last_note": "No data", "driver": 0, "hub": 0, "died": 0, "def": 0, "warn": False, "pickup": "N/A"}
    
    avg = t_data['Total Score'].mean()
    hub = t_data['Amount in Hub'].mean()
    move = t_data['Moved_Num'].mean() * 100
    defense_pct = t_data['Defense_Num'].mean() * 100
    climb_modes = t_data['Climbing'].dropna().mode()
    climb = climb_modes.iloc[0] if not climb_modes.empty else "N/A"
    driver = t_data['driver skill'].mean() if 'driver skill' in t_data else 0
    note_df = t_data.dropna(subset=['Comments'])
    note = note_df.iloc[-1]['Comments'] if not note_df.empty else "No notes"
    
    died_tipped = t_data['Died_Num'].sum() + t_data['Tipped_Num'].sum()
    warn = True if (len(t_data) > 0 and (died_tipped / len(t_data)) > 0.2) else False

    # Pickup Logic
    pk_ground = t_data['PickUp Ground'].mean()
    pk_hp = t_data['PickUP Human Player'].mean()
    pk_pref = "Ground" if pk_ground > pk_hp else "HP" if pk_hp > 0 else "N/A"
    
    return {
        "avg": avg, "count": int(t_data['Match Number'].count()), "auto_move": move, 
        "climb_pref": climb, "last_note": note, "driver": driver, "hub": hub, 
        "died": int(died_tipped), "def": defense_pct, "warn": warn, "pickup": pk_pref
    }

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("⚙️ Hub Control")
    view = st.radio("Navigation", ["🗺️ Field Map", "📊 Overview", "🤖 Deep Dive", "🤝 Alliance Selection", "🏆 Playoffs"], label_visibility="collapsed")
    st.divider()

    if view in ["🗺️ Field Map", "📊 Overview", "🏆 Playoffs"]:
        m_list = sorted(schema_df['match_number'].unique().astype(int))
        try:
            m_index = m_list.index(st.session_state.m_sel_val)
        except ValueError:
            m_index = 0
            
        selected_match = st.selectbox("Select Match", m_list, index=m_index, key="m_sel")
        st.session_state.m_sel_val = selected_match 
        
        row = schema_df[schema_df['match_number'] == selected_match].iloc[0]
        red_teams = [int(row['red1']), int(row['red2']), int(row['red3'])]
        blue_teams = [int(row['blue1']), int(row['blue2']), int(row['blue3'])]
        red_pred = sum(get_team_stats(t)['avg'] for t in red_teams if t > 0)
        blue_pred = sum(get_team_stats(t)['avg'] for t in blue_teams if t > 0)

        st.markdown(f"""<div class="sb-predict-box">
            <div style="font-size:11px; color:grey;">PREDICTED SCORES</div>
            <div style="color:#FF4B4B; font-weight:bold; font-size:22px;">RED: {round(red_pred,1)}</div>
            <div style="color:#1F77B4; font-weight:bold; font-size:22px;">BLUE: {round(blue_pred,1)}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 35vh;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Sync Data", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# --- 4. VIEW: FIELD MAP ---
if view == "🗺️ Field Map":
    def detailed_card(team_num, color_hex):
        s = get_team_stats(team_num)
        warn_icon = "⚠️ " if s['warn'] else ""
        st.markdown(f"""
        <div class="team-info-box-detailed" style="border-top-color: {color_hex};">
            <div class="stat-row"><b>{warn_icon}{team_num}</b> <span>{s['count']} matches</span></div>
            <div class="stat-row">Avg: <b>{round(s['avg'], 1)}</b> <span>Def: {round(s['def'])}%</span></div>
            <div class="stat-row">Climb: {s['climb_pref']} <span>Skill: {round(s['driver'], 1)}</span></div>
            <div class="note-text">{s['last_note'][:75]}...</div>
        </div>
        """, unsafe_allow_html=True)

    r_cols = st.columns(3)
    for i, t in enumerate(red_teams):
        with r_cols[i]: detailed_card(t, "#FF4B4B")

    f_l, f_m, f_r = st.columns([0.7, 4.6, 0.7])
    with f_l: st.markdown(f"""<div class="field-side-label"><div class="side-big">{selected_match}</div><div class="side-small">MATCH</div></div>""", unsafe_allow_html=True)
    with f_m:
        if os.path.exists("field.png"):
            with open("field.png", "rb") as f: img_b64 = base64.b64encode(f.read()).decode()
            html_content = f"""
            <div id="field-container" style="position: relative; width: 100%; max-width: 1050px; margin: 0 auto; border: 2px solid #555; border-radius: 12px; overflow: hidden; touch-action: none; background-color: #000;">
                <img src="data:image/png;base64,{img_b64}" style="width: 100%; height: auto; display: block; pointer-events: none;">
                <div class="bot red" style="left: 10%; top: 15%;">{red_teams[0]}</div>
                <div class="bot red" style="left: 10%; top: 40%;">{red_teams[1]}</div>
                <div class="bot red" style="left: 10%; top: 65%;">{red_teams[2]}</div>
                <div class="bot blue" style="right: 10%; top: 15%;">{blue_teams[0]}</div>
                <div class="bot blue" style="right: 10%; top: 40%;">{blue_teams[1]}</div>
                <div class="bot blue" style="right: 10%; top: 65%;">{blue_teams[2]}</div>
            </div>
            <style>
                .bot {{ position: absolute; width: 34px; height: 34px; border-radius: 50%; color: white; font-family: sans-serif; font-weight: bold; font-size: 8px; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 4px 8px black; cursor: move; z-index: 100; }}
                .red {{ background: rgba(255, 75, 75, 0.95); }} .blue {{ background: rgba(31, 119, 180, 0.95); }}
            </style>
            <script>
                const container = document.getElementById('field-container'); const bots = document.querySelectorAll('.bot');
                bots.forEach(bot => {{
                    let isDragging = false; let offsetX, offsetY;
                    const start = (e) => {{ isDragging = true; const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX; const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY; offsetX = clientX - bot.getBoundingClientRect().left; offsetY = clientY - bot.getBoundingClientRect().top; }};
                    const move = (e) => {{ if (!isDragging) return; const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX; const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY; const rect = container.getBoundingClientRect(); let x = ((clientX - rect.left - offsetX) / rect.width) * 100; let y = ((clientY - rect.top - offsetY) / rect.height) * 100; bot.style.left = Math.max(0, Math.min(96, x)) + '%'; bot.style.top = Math.max(0, Math.min(95, y)) + '%'; if(e.type.includes('touch')) e.preventDefault(); }};
                    const end = () => isDragging = false;
                    bot.addEventListener('mousedown', start); bot.addEventListener('touchstart', start, {{passive: false}}); document.addEventListener('mousemove', move); document.addEventListener('touchmove', move, {{passive: false}}); document.addEventListener('mouseup', end); document.addEventListener('touchend', end);
                }});
            </script>
            """
            st.components.v1.html(html_content, height=415)
    with f_r: st.markdown(f"""<div class="field-side-label"><div style="color:#FF4B4B; font-weight:800; font-size:10px;">RED</div><div style="font-size:24px; font-weight:900;">{round(red_pred,1)}</div><div style="height:25px;"></div><div style="color:#1F77B4; font-weight:800; font-size:10px;">BLUE</div><div style="font-size:24px; font-weight:900;">{round(blue_pred,1)}</div></div>""", unsafe_allow_html=True)
    
    b_cols = st.columns(3)
    for i, t in enumerate(blue_teams):
        with b_cols[i]: detailed_card(t, "#1F77B4")

# --- 5. VIEW: ALLIANCE SELECTION (QUICK SELECT) ---
elif view == "🤝 Alliance Selection":
    st.title("🤝 Alliance Selection Board")
    
    if st.session_state.active_team_selection:
        st.markdown(f"""<div class="staging-area"><h3>Team {st.session_state.active_team_selection} READY</h3><p>Assign to a playoff slot on the right.</p></div>""", unsafe_allow_html=True)
        if st.button("Clear Active Selection"):
            st.session_state.active_team_selection = None; st.rerun()

    drafted = []
    for a in st.session_state.alliances.values(): drafted.extend([a['c'], a['p1'], a['p2']])
    drafted = [t for t in drafted if t > 0]

    col_pick, col_alliances = st.columns([1.2, 2.5])
    with col_pick:
        st.subheader("📋 Draft Board")
        team_data_list = []
        for t in sorted(set(df['Team Number'].unique())):
            if t > 0: team_data_list.append({"team": t, **get_team_stats(t)})
        draft_sorted = pd.DataFrame(team_data_list).sort_values('avg', ascending=False)

        for _, tr in draft_sorted.iterrows():
            t_num = int(tr['team'])
            is_taken = t_num in drafted
            is_active = st.session_state.active_team_selection == t_num
            
            # Use columns for "Select without expanding"
            sel_col, exp_col = st.columns([0.3, 0.7])
            with sel_col:
                if not is_taken:
                    if st.button("➕", key=f"fast_sel_{t_num}", help="Select Team"):
                        st.session_state.active_team_selection = t_num; st.rerun()
                else: st.write("✅")
            
            with exp_col:
                summary = f"{t_num} — Avg: {round(tr['avg'],1)}"
                with st.expander(f"{'➡️ ' if is_active else ''}{'~~' if is_taken else ''}{summary}"):
                    st.write(f"**Driver Skill:** {round(tr['driver'],1)}/5")
                    st.write(f"**Pickup:** {tr['pickup']} | **Def:** {round(tr['def'])}%")
                    st.write(f"**Reliability:** {tr['died']} died/tipped matches")
                    st.info(f"**Last Note:** {tr['last_note']}")

    with col_alliances:
        st.subheader("🏆 Playoffs")
        grid = st.columns(2)
        for i in range(1, 9):
            with grid[(i-1) % 2]:
                st.markdown(f"""<div class="alliance-container"><b>Alliance {i}</b>""", unsafe_allow_html=True)
                for label, key in [("Capt", "c"), ("Pick 1", "p1"), ("Pick 2", "p2")]:
                    curr = st.session_state.alliances[i][key]
                    if st.button(f"{label}: {curr if curr > 0 else 'empty'}", key=f"btn_{i}_{key}", use_container_width=True):
                        if st.session_state.active_team_selection:
                            st.session_state.alliances[i][key] = st.session_state.active_team_selection
                            st.session_state.active_team_selection = None; st.rerun()
                        elif curr > 0:
                            st.session_state.alliances[i][key] = 0; st.rerun()
                total = sum(get_team_stats(st.session_state.alliances[i][k])['avg'] for k in ['c','p1','p2'])
                st.markdown(f"<div style='text-align:right; color:#4F8BF9;'>Σ {round(total,1)}</div></div>", unsafe_allow_html=True)

# --- 6. VIEW: DEEP DIVE (HEADER SELECTOR) ---
elif view == "🤖 Deep Dive":
    t_list = sorted(set(df['Team Number'].unique()) | set(pit_df['team_number'].unique()))
    t_list = [t for t in t_list if t > 0]
    
    if 't_sel_val' not in st.session_state: st.session_state.t_sel_val = t_list[0]
    try: t_index = t_list.index(st.session_state.t_sel_val)
    except ValueError: t_index = 0

    # Team Selector on Main Page
    header_l, header_r = st.columns([1, 1])
    with header_l:
        selected_team = st.selectbox("🔍 Deep Dive Selection", t_list, index=t_index, key="main_t_sel")
        st.session_state.t_sel_val = selected_team

    stats = get_team_stats(selected_team); p_data = pit_df[pit_df['team_number'] == selected_team]
    name = p_data.iloc[0]['team name'] if not p_data.empty else "Unknown Team"
    
    st.markdown(f"<div style='font-size: 48px; color: #4F8BF9; font-weight: 800;'>{selected_team}</div><div style='font-size: 22px; color: #BDC3C7;'>{name}</div>", unsafe_allow_html=True)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Avg Score", round(stats['avg'], 1)); m2.metric("Auto%", f"{round(stats['auto_move'])}%"); m3.metric("Avg Driver", f"{round(stats['driver'], 1)}/5"); m4.metric("Climb Pref", stats['climb_pref']); m5.metric("Matches", stats['count'])
    
    st.divider(); cl_l, cl_r = st.columns([2, 1.2])
    with cl_l:
        st.subheader("Trend")
        merged = pd.merge(schema_df[(schema_df[['red1','red2','red3','blue1','blue2','blue3']] == selected_team).any(axis=1)][['match_number']], df[df['Team Number'] == selected_team], left_on='match_number', right_on='Match Number', how='left')
        merged['X_Label'] = merged['match_number'].apply(lambda x: f"M{int(x)}")
        if not merged.dropna(subset=['Total Score']).empty: st.plotly_chart(px.line(merged.dropna(subset=['Total Score']), x="X_Label", y="Total Score", markers=True, template="plotly_dark", height=280), use_container_width=True)
        pick_stats = df[df['Team Number'] == selected_team][['PickUp Ground', 'PickUP Human Player', 'PickUp Depot']].mean().fillna(0) * 100
        st.plotly_chart(px.bar(x=pick_stats.index.tolist(), y=pick_stats.values.tolist(), height=220, template="plotly_dark"), use_container_width=True)
    with cl_r:
        if not p_data.empty: st.subheader("🛠️ Pit"); st.dataframe(p_data.T, use_container_width=True)
        if stats['died'] > 0: st.error(f"Reliability: {stats['died']} incidents")
    st.divider(); st.subheader("Match Logs")
    notes_df = df[df['Team Number'] == selected_team].dropna(subset=['Comments'])[['Match Number', 'Comments', 'driver skill']].sort_values('Match Number', ascending=False)
    if not notes_df.empty: st.table(notes_df)

elif view == "📊 Overview":
    st.title(f"Match {st.session_state.m_sel_val} Overview")
    o1, o2 = st.columns(2)
    with o1:
        st.subheader("🔴 Red"); [st.write(f"**{t}** | Avg: {round(get_team_stats(t)['avg'],1)}") for t in red_teams if t > 0]
    with o2:
        st.subheader("🔵 Blue"); [st.write(f"**{t}** | Avg: {round(get_team_stats(t)['avg'],1)}") for t in blue_teams if t > 0]

elif view == "🏆 Playoffs":
    st.title("🏆 Playoffs")
    st.info("Configured via Draft Board.")