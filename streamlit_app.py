import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="Scouting Hub", layout="wide", initial_sidebar_state="expanded")

# --- INITIALIZE SESSION STATE ---
if 'comp_mode' not in st.session_state:
    st.session_state.comp_mode = "FTC" if os.path.exists("scouting_data_ftc.xlsx") else "FRC"

if 'alliances_state' not in st.session_state:
    st.session_state.alliances_state = {i: {"c": 0, "p1": 0, "p2": 0} for i in range(1, 9)}

if 'm_sel_val' not in st.session_state:
    st.session_state.m_sel_val = 1 

if 'active_team_selection' not in st.session_state:
    st.session_state.active_team_selection = None

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main .block-container { max-width: 100%; padding: 0.5rem 1rem; }
    .team-info-box-detailed { padding: 8px; border-radius: 8px; border-top: 4px solid; background-color: rgba(255, 255, 255, 0.08); font-size: 12px; box-shadow: 1px 1px 4px rgba(0,0,0,0.3); margin-bottom: 2px; }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 1px; }
    .note-text { font-style: italic; font-size: 10px; color: #BDC3C7; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 3px; padding-top: 2px; height: 32px; overflow: hidden; }
    .field-side-label { text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 380px; }
    .side-big { font-size: 42px; font-weight: 900; color: #4F8BF9; line-height: 1; }
    .side-small { font-size: 11px; color: #BDC3C7; text-transform: uppercase; margin-top: -5px; }
    .staging-area { background: rgba(79, 139, 249, 0.2); padding: 15px; border-radius: 10px; border: 2px solid #4F8BF9; margin-bottom: 20px; text-align: center; }
    [data-testid="stHtml"] { padding: 0 !important; margin: 0 !important; }
    iframe { display: block; margin: 0 auto; border: none; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING ---
@st.cache_data
def load_data(mode):
    file_name = "scouting_data.xlsx" if mode == "FRC" else "scouting_data_ftc.xlsx"
    if not os.path.exists(file_name):
        return None, None, None, None
    try:
        schema = pd.read_excel(file_name, sheet_name="Matches", header=0)
        data = pd.read_excel(file_name, sheet_name="Data_Input")
        ali = pd.read_excel(file_name, sheet_name="Alliances")
        pit = pd.read_excel(file_name, sheet_name="Pit_Input") if mode == "FRC" else pd.DataFrame()
        for d in [schema, data, ali]: 
            d.columns = d.columns.str.strip()
            if mode == "FTC": d.dropna(how='all', axis=1, inplace=True)
        for col in ['+1', '+3', '+5', 'Amount in Hub']:
            if col in data.columns: data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
        score_cols = [c for c in ['+1', '+3', '+5'] if c in data.columns]
        data['Total Score'] = data[score_cols].sum(axis=1) if score_cols else 0
        def clean_bool(val): return 1 if str(val).lower() in ['true', '1', '1.0', 'yes', 'y'] else 0
        for col in ['Moved?', 'Died?', 'Tipped/Fell Over?', 'Defence/ to other side']:
            if col in data.columns: data[col.replace('?','').split('/')[0]+'_Num'] = data[col].apply(clean_bool)
        return data, pit, schema, ali
    except Exception as e:
        return None, None, None, None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ HUB CONTROL")
    mode_selection = st.radio("Competition", ["FRC", "FTC"], index=0 if st.session_state.comp_mode == "FRC" else 1, horizontal=True)
    if mode_selection != st.session_state.comp_mode:
        st.session_state.comp_mode = mode_selection
        st.cache_data.clear()
        st.rerun()
    view = st.radio("Navigation", ["🗺️ Field Map", "📊 Overview", "🤖 per team", "🤝 Alliance Selection", "🏆 Playoffs"], label_visibility="collapsed")

df, pit_df, schema_df, alliance_df = load_data(st.session_state.comp_mode)
if df is None: st.stop()

# --- 2. HELPERS ---
def get_team_stats(team_num):
    if team_num == 0: return {"avg": 0, "count": 0, "climb_pref": "N/A", "last_note": "No notes", "driver": 0, "warn": False}
    t_data = df[df['Team Number'] == team_num]
    stat_dict = {"avg": 0, "count": 0, "climb_pref": "N/A", "last_note": "No notes", "driver": 0, "warn": False}
    if not t_data.empty:
        stat_dict.update({"avg": t_data['Total Score'].mean(), "count": len(t_data)})
        if 'Climbing' in t_data: stat_dict["climb_pref"] = t_data['Climbing'].dropna().mode().iloc[0] if not t_data['Climbing'].dropna().empty else "N/A"
        if 'driver skill' in t_data: stat_dict["driver"] = t_data['driver skill'].mean()
        note_s = t_data.dropna(subset=['Comments'])
        if not note_s.empty: stat_dict['last_note'] = note_s.iloc[-1]['Comments']
        died_sum = (t_data['Died_Num'].sum() if 'Died_Num' in t_data else 0) + (t_data['Tipped_Num'].sum() if 'Tipped_Num' in t_data else 0)
        stat_dict['warn'] = (died_sum / len(t_data)) > 0.2 if len(t_data) > 0 else False
    return stat_dict

def detailed_card(team_num, color_hex):
    s = get_team_stats(team_num)
    st.markdown(f"""<div class="team-info-box-detailed" style="border-top-color: {color_hex};">
        <div class="stat-row"><b>{'⚠️ ' if s['warn'] else ''}{team_num}</b> <span>{s['count']} matches</span></div>
        <div class="stat-row">Avg: <b>{round(s['avg'], 1)}</b></div>
        <div class="stat-row">Climb: {s['climb_pref']} <span>Skill: {round(s['driver'], 1)}</span></div>
        <div class="note-text">{s['last_note'][:75]}...</div>
    </div>""", unsafe_allow_html=True)

def render_field_interactive(red_teams, blue_teams, match_label, red_pred, blue_pred):
    f_l, f_m, f_r = st.columns([0.7, 4.6, 0.7])
    with f_l: st.markdown(f'<div class="field-side-label"><div class="side-big">{match_label}</div><div class="side-small">MATCH</div></div>', unsafe_allow_html=True)
    
    img_file = "field.png" if st.session_state.comp_mode == "FRC" else "ftcfield.png"
    # Aspect ratios and strict height limits to remove the "pushed down" gap
    # FRC: Panoramic (Wide), FTC: Square
    max_h = "450px" if st.session_state.comp_mode == "FRC" else "600px"
    max_w = "100%" if st.session_state.comp_mode == "FRC" else "600px"
    
    img_b64 = ""
    if os.path.exists(img_file):
        with open(img_file, "rb") as f: img_b64 = base64.b64encode(f.read()).decode()
    
    with f_m:
        red_bots = "".join([f'<div class="bot red" style="left: 15%; top: {25+(i*35)}%;" id="r{i}">{red_teams[i]}</div>' for i in range(len(red_teams))])
        blue_bots = "".join([f'<div class="bot blue" style="right: 15%; top: {25+(i*35)}%;" id="b{i}">{blue_teams[i]}</div>' for i in range(len(blue_teams))])

        html_content = f"""
        <div id="controls" style="display:flex; gap:10px; margin:0 auto; max-width:{max_w}; padding-bottom:2px;">
            <button onclick="setMode('move')" style="flex:1; padding:8px; cursor:pointer; background:#4F8BF9; color:white; border:none; border-radius:5px; font-weight:bold; font-size:12px;">Move</button>
            <button onclick="setMode('draw')" style="flex:1; padding:8px; cursor:pointer; background:#2ECC71; color:white; border:none; border-radius:5px; font-weight:bold; font-size:12px;">Draw</button>
            <button onclick="clearCanvas()" style="flex:0.5; padding:8px; cursor:pointer; background:#E74C3C; color:white; border:none; border-radius:5px; font-weight:bold; font-size:12px;">Clear</button>
        </div>
        <div id="field-viewport" style="width:100%; max-width:{max_w}; margin:0 auto; overflow:hidden; border: 2px solid #555; border-radius: 8px; background:#000;">
            <div id="field-container" style="position: relative; width: 100%; height: {max_h}; touch-action: none;">
                <img src="data:image/png;base64,{img_b64}" style="width:100%; height:100%; object-fit: contain; pointer-events: none;">
                <canvas id="strategy-canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:10; cursor:crosshair; pointer-events:none;"></canvas>
                {red_bots} {blue_bots}
            </div>
        </div>
        <style>
            .bot {{ position: absolute; width: 38px; height: 38px; border-radius: 50%; color: white; font-family: sans-serif; font-weight: bold; font-size: 10px; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 4px 8px black; cursor: grab; z-index: 20; touch-action: none; transform: translate(-50%, -50%); }}
            .bot:active {{ cursor: grabbing; }}
            .red {{ background: #FF4B4B; }} .blue {{ background: #1F77B4; }}
        </style>
        <script>
            const canvas = document.getElementById('strategy-canvas'); const ctx = canvas.getContext('2d');
            const container = document.getElementById('field-container'); const bots = document.querySelectorAll('.bot');
            let mode = 'move'; let drawing = false;
            function setMode(m) {{ mode = m; canvas.style.pointerEvents = (m === 'draw' ? 'auto' : 'none'); }}
            function clearCanvas() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); }}
            function resize() {{ canvas.width = container.clientWidth; canvas.height = container.clientHeight; }}
            window.onload = resize; window.onresize = resize; setTimeout(resize, 100);
            canvas.addEventListener('mousedown', e => {{ if(mode==='draw') {{ drawing=true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); }} }});
            canvas.addEventListener('mousemove', e => {{ if(drawing && mode==='draw') {{ ctx.lineTo(e.offsetX, e.offsetY); ctx.strokeStyle='#2ECC71'; ctx.lineWidth=4; ctx.stroke(); }} }});
            canvas.addEventListener('mouseup', () => drawing=false);
            bots.forEach(bot => {{
                let dragging = false;
                const move = (e) => {{
                    if (!dragging) return; const evt = e.touches ? e.touches[0] : e;
                    const rect = container.getBoundingClientRect();
                    bot.style.left = ((evt.clientX - rect.left) / rect.width * 100) + '%';
                    bot.style.top = ((evt.clientY - rect.top) / rect.height * 100) + '%';
                }};
                bot.addEventListener('mousedown', () => {{ if(mode==='move') dragging = true; }});
                bot.addEventListener('touchstart', (e) => {{ if(mode==='move') dragging = true; e.preventDefault(); }}, {{passive:false}});
                document.addEventListener('mousemove', move); document.addEventListener('touchmove', move, {{passive:false}});
                document.addEventListener('mouseup', () => dragging = false); document.addEventListener('touchend', () => dragging = false);
            }});
        </script>
        """
        st.components.v1.html(html_content, height=700 if st.session_state.comp_mode == "FTC" else 550)
    with f_r: st.markdown(f'<div class="field-side-label"><div style="color:#FF4B4B; font-size:10px;">RED</div><div style="font-size:24px; font-weight:900;">{round(red_pred,1)}</div><div style="height:20px;"></div><div style="color:#1F77B4; font-size:10px;">BLUE</div><div style="font-size:24px; font-weight:900;">{round(blue_pred,1)}</div></div>', unsafe_allow_html=True)

# --- 3. VIEWS ---
with st.sidebar:
    st.divider()
    if view in ["🗺️ Field Map", "📊 Overview"]:
        m_list = sorted(schema_df['match_number'].unique().astype(int))
        st.session_state.m_sel_val = st.selectbox("Select Match", m_list, index=m_list.index(st.session_state.m_sel_val) if st.session_state.m_sel_val in m_list else 0)
    if st.button("🔄 Sync Data", use_container_width=True): st.cache_data.clear(); st.rerun()

# Dynamic alliance slots detection
slots = [("Capt","c"),("Pick 1","p1")]
if '2e' in alliance_df.columns: slots.append(("Pick 2","p2"))

if view == "🏆 Playoffs":
    st.title(f"🏆 {st.session_state.comp_mode} Playoffs")
    a_names = [f"Alliance {i+1}" for i in range(len(alliance_df))]
    c1, c2 = st.columns(2)
    with c1:
        r_choice = st.selectbox("🔴 Red Alliance", a_names, index=0)
        r_row = alliance_df.iloc[a_names.index(r_choice)]
        r_roster = [int(r_row[k]) for _, k in slots if k in r_row and pd.notna(r_row[k])]
    with c2:
        b_choice = st.selectbox("🔵 Blue Alliance", a_names, index=min(1, len(a_names)-1))
        b_row = alliance_df.iloc[a_names.index(b_choice)]
        b_roster = [int(b_row[k]) for _, k in slots if k in b_row and pd.notna(b_row[k])]
    rc = st.columns(len(r_roster))
    for i, t in enumerate(r_roster):
        with rc[i]: detailed_card(t, "#FF4B4B")
    render_field_interactive(r_roster, b_roster, "PLAYOFF", sum(get_team_stats(t)['avg'] for t in r_roster), sum(get_team_stats(t)['avg'] for t in b_roster))
    bc = st.columns(len(b_roster))
    for i, t in enumerate(b_roster):
        with bc[i]: detailed_card(t, "#1F77B4")

elif view == "🗺️ Field Map":
    m_row = schema_df[schema_df['match_number'] == st.session_state.m_sel_val].iloc[0]
    r_keys = [c for c in ['red1','red2','red3'] if c in m_row.index and pd.notna(m_row[c])]
    b_keys = [c for c in ['blue1','blue2','blue3'] if c in m_row.index and pd.notna(m_row[c])]
    rt, bt = [int(m_row[c]) for c in r_keys], [int(m_row[c]) for c in b_keys]
    rc = st.columns(len(rt))
    for i, t in enumerate(rt):
        with rc[i]: detailed_card(t, "#FF4B4B")
    render_field_interactive(rt, bt, st.session_state.m_sel_val, sum(get_team_stats(t)['avg'] for t in rt), sum(get_team_stats(t)['avg'] for t in bt))
    bc = st.columns(len(bt))
    for i, t in enumerate(bt):
        with bc[i]: detailed_card(t, "#1F77B4")

elif view == "📊 Overview":
    m_row = schema_df[schema_df['match_number'] == st.session_state.m_sel_val].iloc[0]
    r_keys = [c for c in ['red1','red2','red3'] if c in m_row.index and pd.notna(m_row[c])]
    b_keys = [c for c in ['blue1','blue2','blue3'] if c in m_row.index and pd.notna(m_row[c])]
    rt, bt = [int(m_row[c]) for c in r_keys], [int(m_row[c]) for c in b_keys]
    st.title(f"Overview - Match {st.session_state.m_sel_val}")
    o1, o2 = st.columns(2)
    with o1:
        st.subheader("🔴 Red Alliance")
        for t in rt: detailed_card(t, "#FF4B4B")
    with o2:
        st.subheader("🔵 Blue Alliance")
        for t in bt: detailed_card(t, "#1F77B4")

elif view == "🤖 per team":
    t_list = sorted(set(df['Team Number'].unique()))
    sel_t = st.selectbox("🔍 Select Team", t_list)
    stats = get_team_stats(sel_t)
    st.title(f"Team {sel_t}")
    m = st.columns(4); m[0].metric("Avg Score", round(stats['avg'],1)); m[1].metric("Climb", stats['climb_pref']); m[2].metric("Skill", round(stats['driver'],1)); m[3].metric("Samples", stats['count'])
    merged = df[df['Team Number'] == sel_t].copy()
    merged['X'] = merged['Match Number'].apply(lambda x: f"M{int(x)}")
    st.plotly_chart(px.line(merged.sort_values('Match Number'), x="X", y="Total Score", markers=True, template="plotly_dark", height=300), use_container_width=True)
    st.table(df[df['Team Number'] == sel_t].dropna(subset=['Comments'])[['Match Number', 'Comments']].sort_values('Match Number', ascending=False))

elif view == "🤝 Alliance Selection":
    st.title("🤝 Draft Board")
    if st.session_state.active_team_selection:
        st.markdown(f'<div class="staging-area"><h3>Team {st.session_state.active_team_selection} SELECTED</h3></div>', unsafe_allow_html=True)
        if st.button("Cancel"): st.session_state.active_team_selection = None; st.rerun()
    col_l, col_r = st.columns([1.2, 2.5])
    with col_l:
        st.subheader("📋 Teams")
        t_data = pd.DataFrame([{"t": t, **get_team_stats(t)} for t in sorted(set(df['Team Number'].unique()))]).sort_values('avg', ascending=False)
        for _, tr in t_data.iterrows():
            t_num = int(tr['t'])
            if st.button(f"{t_num} (Avg: {round(tr['avg'],1)})", key=f"sel_{t_num}", use_container_width=True):
                st.session_state.active_team_selection = t_num; st.rerun()
    with col_r:
        grid = st.columns(2)
        for i in range(1, 9):
            with grid[(i-1)%2]:
                with st.container(border=True):
                    st.markdown(f"**Alliance {i}**")
                    for label, key in slots:
                        curr = st.session_state.alliances_state[i][key]
                        if st.button(f"{label}: {curr if curr > 0 else 'empty'}", key=f"a{i}{key}", use_container_width=True):
                            if st.session_state.active_team_selection:
                                st.session_state.alliances_state[i][key] = st.session_state.active_team_selection
                                st.session_state.active_team_selection = None; st.rerun()
                            else: st.session_state.alliances_state[i][key] = 0; st.rerun()