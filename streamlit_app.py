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

# Persistence for Playoff setup
if 'playoff_red_ali' not in st.session_state: 
    st.session_state.playoff_red_ali = "Alliance 1"
if 'playoff_blue_ali' not in st.session_state: 
    st.session_state.playoff_blue_ali = "Alliance 2"
if 'playoff_red_swap' not in st.session_state: 
    st.session_state.playoff_red_swap = False
if 'playoff_blue_swap' not in st.session_state: 
    st.session_state.playoff_blue_swap = False
if 'playoff_red_out' not in st.session_state: 
    st.session_state.playoff_red_out = None
if 'playoff_blue_out' not in st.session_state: 
    st.session_state.playoff_blue_out = None

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main .block-container { max-width: 100%; padding: 0.5rem 1rem; }
    .sb-predict-box { padding: 12px; background: rgba(255, 255, 255, 0.05); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.1); margin-top: 10px; }
    .team-info-box-detailed { padding: 8px; border-radius: 8px; border-top: 4px solid; background-color: rgba(255, 255, 255, 0.08); font-size: 12px; box-shadow: 1px 1px 4px rgba(0,0,0,0.3); margin-bottom: 2px; }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 1px; }
    .note-text { font-style: italic; font-size: 10px; color: #BDC3C7; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 3px; padding-top: 2px; height: 32px; overflow: hidden; }
    .field-side-label { text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 380px; }
    .side-big { font-size: 42px; font-weight: 900; color: #4F8BF9; line-height: 1; }
    .side-small { font-size: 11px; color: #BDC3C7; text-transform: uppercase; margin-top: -5px; }
    .alliance-container { background: rgba(255,255,255,0.03); padding: 10px; border-radius: 10px; border: 1px solid #444; margin-bottom: 10px; }
    .staging-area { background: rgba(79, 139, 249, 0.2); padding: 15px; border-radius: 10px; border: 2px solid #4F8BF9; margin-bottom: 20px; text-align: center; }
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
    data = pd.read_excel(file_name, sheet_name="Data_Input")
    data.columns = data.columns.str.strip()
    for col in ['+1', '+3', '+5', 'Amount in Hub']:
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    data['Total Score'] = data['+1'] + data['+3'] + data['+5']
    def clean_bool(val): return 1 if str(val).lower() in ['true', '1', '1.0', 'yes', 'y'] else 0
    data['Moved_Num'] = data['Moved?'].apply(clean_bool)
    data['Died_Num'] = data['Died?'].apply(clean_bool)
    data['Tipped_Num'] = data['Tipped/Fell Over?'].apply(clean_bool)
    data['Defense_Num'] = data['Defence/ to other side'].apply(clean_bool)
    for col in ['PickUp Ground', 'PickUP Human Player', 'PickUp Depot']:
        data[col] = data[col].apply(clean_bool)
    pit = pd.read_excel(file_name, sheet_name="Pit_Input")
    pit.columns = pit.columns.str.strip()
    ali = pd.read_excel(file_name, sheet_name="Alliances")
    ali.columns = ali.columns.str.strip()
    return data, pit, schema, ali

try:
    df, pit_df, schema_df, alliance_df = load_frc_data()
except Exception as e:
    st.error(f"Data Load Error: {e}")
    st.stop()

# --- 2. HELPERS ---
def get_team_stats(team_num):
    t_data = df[df['Team Number'] == team_num]
    if t_data.empty: 
        return {"avg": 0, "count": 0, "climb_pref": "N/A", "last_note": "No data", "driver": 0, "died": 0, "def": 0, "warn": False, "auto": 0}
    avg = t_data['Total Score'].mean()
    def_pct = t_data['Defense_Num'].mean() * 100
    move = t_data['Moved_Num'].mean() * 100
    climb = t_data['Climbing'].dropna().mode().iloc[0] if not t_data['Climbing'].dropna().empty else "N/A"
    driver = t_data['driver skill'].mean() if 'driver skill' in t_data else 0
    note_series = t_data.dropna(subset=['Comments'])
    note = note_series.iloc[-1]['Comments'] if not note_series.empty else "No notes"
    died_tipped = t_data['Died_Num'].sum() + t_data['Tipped_Num'].sum()
    warn = True if (died_tipped / len(t_data)) > 0.2 else False
    return {"avg": avg, "count": len(t_data), "climb_pref": climb, "last_note": note, "driver": driver, "died": int(died_tipped), "def": def_pct, "warn": warn, "auto": move}

def detailed_card(team_num, color_hex):
    s = get_team_stats(team_num)
    warn_icon = "⚠️ " if s['warn'] else ""
    st.markdown(f"""<div class="team-info-box-detailed" style="border-top-color: {color_hex};">
        <div class="stat-row"><b>{warn_icon}{team_num}</b> <span>{s['count']} matches</span></div>
        <div class="stat-row">Avg: <b>{round(s['avg'], 1)}</b> <span>Def: {round(s['def'])}%</span></div>
        <div class="stat-row">Climb: {s['climb_pref']} <span>Skill: {round(s['driver'], 1)}</span></div>
        <div class="note-text">{s['last_note'][:75]}...</div>
    </div>""", unsafe_allow_html=True)

def render_field_interactive(red_teams, blue_teams, match_label, red_pred, blue_pred):
    f_l, f_m, f_r = st.columns([0.7, 4.6, 0.7])
    with f_l: 
        st.markdown(f'<div class="field-side-label"><div class="side-big">{match_label}</div><div class="side-small">MATCH</div></div>', unsafe_allow_html=True)
    with f_m:
        if os.path.exists("field.png"):
            with open("field.png", "rb") as f: 
                img_b64 = base64.b64encode(f.read()).decode()
            html_content = f"""
            <div id="controls" style="display:flex; gap:10px; margin-bottom:5px;">
                <button onclick="setMode('move')" style="flex:1; padding:8px; cursor:pointer; background:#4F8BF9; color:white; border:none; border-radius:5px; font-weight:bold;">Move Bots</button>
                <button onclick="setMode('draw')" style="flex:1; padding:8px; cursor:pointer; background:#2ECC71; color:white; border:none; border-radius:5px; font-weight:bold;">Draw Path</button>
                <button onclick="clearCanvas()" style="flex:0.5; padding:8px; cursor:pointer; background:#E74C3C; color:white; border:none; border-radius:5px; font-weight:bold;">Clear Sketch</button>
            </div>
            <div id="field-container" style="position: relative; width: 100%; max-width: 1050px; margin: 0 auto; border: 2px solid #555; border-radius: 12px; overflow: hidden; touch-action: none; background-color: #000;">
                <img id="field-img" src="data:image/png;base64,{img_b64}" style="width: 100%; height: auto; display: block; pointer-events: none;">
                <canvas id="strategy-canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:50; cursor:crosshair;"></canvas>
                <div class="bot red" style="left: 10%; top: 15%; z-index:100;">{red_teams[0]}</div>
                <div class="bot red" style="left: 10%; top: 40%; z-index:100;">{red_teams[1]}</div>
                <div class="bot red" style="left: 10%; top: 65%; z-index:100;">{red_teams[2]}</div>
                <div class="bot blue" style="right: 10%; top: 15%; z-index:100;">{blue_teams[0]}</div>
                <div class="bot blue" style="right: 10%; top: 40%; z-index:100;">{blue_teams[1]}</div>
                <div class="bot blue" style="right: 10%; top: 70%; z-index:100;">{blue_teams[2]}</div>
            </div>
            <style>
                .bot {{ position: absolute; width: 34px; height: 34px; border-radius: 50%; color: white; font-family: sans-serif; font-weight: bold; font-size: 8px; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 4px 8px black; cursor: move; }}
                .red {{ background: rgba(255, 75, 75, 0.95); }} .blue {{ background: rgba(31, 119, 180, 0.95); }}
            </style>
            <script>
                const canvas = document.getElementById('strategy-canvas');
                const ctx = canvas.getContext('2d');
                const container = document.getElementById('field-container');
                const bots = document.querySelectorAll('.bot');
                let mode = 'move';
                let drawing = false;

                function resizeCanvas() {{
                    canvas.width = container.offsetWidth;
                    canvas.height = container.offsetHeight;
                }}
                window.addEventListener('resize', resizeCanvas);
                setTimeout(resizeCanvas, 100);

                function setMode(m) {{
                    mode = m;
                    if(mode === 'move') {{
                        canvas.style.pointerEvents = 'none';
                        bots.forEach(b => b.style.pointerEvents = 'auto');
                    }} else {{
                        canvas.style.pointerEvents = 'auto';
                        bots.forEach(b => b.style.pointerEvents = 'none');
                    }}
                }}
                setMode('move');

                function clearCanvas() {{
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }}

                canvas.addEventListener('mousedown', startDraw);
                canvas.addEventListener('mousemove', draw);
                canvas.addEventListener('mouseup', stopDraw);
                canvas.addEventListener('touchstart', (e) => {{ startDraw(e.touches[0]); e.preventDefault(); }}, {{passive:false}});
                canvas.addEventListener('touchmove', (e) => {{ draw(e.touches[0]); e.preventDefault(); }}, {{passive:false}});
                canvas.addEventListener('touchend', stopDraw);

                function startDraw(e) {{
                    if(mode !== 'draw') return;
                    drawing = true;
                    ctx.beginPath();
                    const rect = canvas.getBoundingClientRect();
                    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
                    ctx.strokeStyle = '#2ECC71'; ctx.lineWidth = 3; ctx.lineCap = 'round';
                }}
                function draw(e) {{
                    if(!drawing || mode !== 'draw') return;
                    const rect = canvas.getBoundingClientRect();
                    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
                    ctx.stroke();
                }}
                function stopDraw() {{ drawing = false; }}

                bots.forEach(bot => {{
                    let isDragging = false; let offsetX, offsetY;
                    bot.onmousedown = (e) => {{
                        if(mode !== 'move') return;
                        isDragging = true;
                        offsetX = e.clientX - bot.getBoundingClientRect().left;
                        offsetY = e.clientY - bot.getBoundingClientRect().top;
                    }};
                    document.addEventListener('mousemove', (e) => {{
                        if (!isDragging) return;
                        const rect = container.getBoundingClientRect();
                        let x = ((e.clientX - rect.left - offsetX) / rect.width) * 100;
                        let y = ((e.clientY - rect.top - offsetY) / rect.height) * 100;
                        bot.style.left = Math.max(0, Math.min(96, x)) + '%';
                        bot.style.top = Math.max(0, Math.min(95, y)) + '%';
                    }});
                    document.onmouseup = () => isDragging = false;
                    
                    bot.ontouchstart = (e) => {{
                        if(mode !== 'move') return;
                        isDragging = true;
                        offsetX = e.touches[0].clientX - bot.getBoundingClientRect().left;
                        offsetY = e.touches[0].clientY - bot.getBoundingClientRect().top;
                    }};
                    bot.ontouchmove = (e) => {{
                        if (!isDragging) return;
                        const rect = container.getBoundingClientRect();
                        let x = ((e.touches[0].clientX - rect.left - offsetX) / rect.width) * 100;
                        let y = ((e.touches[0].clientY - rect.top - offsetY) / rect.height) * 100;
                        bot.style.left = Math.max(0, Math.min(96, x)) + '%';
                        bot.style.top = Math.max(0, Math.min(95, y)) + '%';
                    }};
                    bot.ontouchend = () => isDragging = false;
                    const end = () => isDragging = false;
                    document.addEventListener('mouseup', end); 
                    document.addEventListener('touchend', end);
                }});
            </script>
            """
            st.components.v1.html(html_content, height=480)
    with f_r: 
        st.markdown(f'<div class="field-side-label"><div style="color:#FF4B4B; font-size:10px;">RED</div><div style="font-size:24px; font-weight:900;">{round(red_pred,1)}</div><div style="height:20px;"></div><div style="color:#1F77B4; font-size:10px;">BLUE</div><div style="font-size:24px; font-weight:900;">{round(blue_pred,1)}</div></div>', unsafe_allow_html=True)

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("⚙️ HUB CONTROL")
    view = st.radio("Navigation", ["🗺️ Field Map", "📊 Overview", "🤖 Deep Dive", "🤝 Alliance Selection", "🏆 Playoffs"], label_visibility="collapsed")
    st.divider()
    if view in ["🗺️ Field Map", "📊 Overview"]:
        m_list = sorted(schema_df['match_number'].unique().astype(int))
        try:
            m_idx = m_list.index(st.session_state.m_sel_val)
        except:
            m_idx = 0
        st.session_state.m_sel_val = st.selectbox("Select Match", m_list, index=m_idx)
    if st.button("🔄 Sync Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. VIEW: PLAYOFFS ---
if view == "🏆 Playoffs":
    st.title("🏆 Playoff Match Planner")
    a_names = [f"Alliance {i+1}" for i in alliance_df.index]
    c1, c2 = st.columns(2)
    with c1:
        r_choice = st.selectbox("🔴 Red Alliance", a_names, index=a_names.index(st.session_state.playoff_red_ali))
        st.session_state.playoff_red_ali = r_choice
        r_row = alliance_df.iloc[a_names.index(r_choice)]
        r_roster = [int(r_row['C']), int(r_row['1e']), int(r_row['2e'])]
        if pd.notna(r_row['3e']):
            swap_r = st.toggle("Use Red Backup?", value=st.session_state.playoff_red_swap)
            st.session_state.playoff_red_swap = swap_r
            if swap_r:
                try: 
                    out_idx = r_roster.index(st.session_state.playoff_red_out) if st.session_state.playoff_red_out in r_roster else 0
                except: 
                    out_idx = 0
                out = st.selectbox("Red to sit out", r_roster, index=out_idx)
                st.session_state.playoff_red_out = out
                r_roster = [int(r_row['3e']) if x == out else x for x in r_roster]
    with c2:
        b_choice = st.selectbox("🔵 Blue Alliance", a_names, index=a_names.index(st.session_state.playoff_blue_ali))
        st.session_state.playoff_blue_ali = b_choice
        b_row = alliance_df.iloc[a_names.index(b_choice)]
        b_roster = [int(b_row['C']), int(b_row['1e']), int(b_row['2e'])]
        if pd.notna(b_row['3e']):
            swap_b = st.toggle("Use Blue Backup?", value=st.session_state.playoff_blue_swap)
            st.session_state.playoff_blue_swap = swap_b
            if swap_b:
                try: 
                    out_b_idx = b_roster.index(st.session_state.playoff_blue_out) if st.session_state.playoff_blue_out in b_roster else 0
                except: 
                    out_b_idx = 0
                out_b = st.selectbox("Blue to sit out", b_roster, index=out_b_idx)
                st.session_state.playoff_blue_out = out_b
                b_roster = [int(b_row['3e']) if x == out_b else x for x in b_roster]

    r_score = sum(get_team_stats(t)['avg'] for t in r_roster)
    b_score = sum(get_team_stats(t)['avg'] for t in b_roster)
    
    rc = st.columns(3)
    for i, t in enumerate(r_roster):
        with rc[i]:
            detailed_card(t, "#FF4B4B")
    render_field_interactive(r_roster, b_roster, "PLAYOFF", r_score, b_score)
    bc = st.columns(3)
    for i, t in enumerate(b_roster):
        with bc[i]:
            detailed_card(t, "#1F77B4")

# --- 5. VIEW: FIELD MAP ---
elif view == "🗺️ Field Map":
    m_row = schema_df[schema_df['match_number'] == st.session_state.m_sel_val].iloc[0]
    rt = [int(m_row['red1']), int(m_row['red2']), int(m_row['red3'])]
    bt = [int(m_row['blue1']), int(m_row['blue2']), int(m_row['blue3'])]
    r_pred = sum(get_team_stats(t)['avg'] for t in rt)
    b_pred = sum(get_team_stats(t)['avg'] for t in bt)
    rc_cols = st.columns(3)
    for i, t in enumerate(rt):
        with rc_cols[i]:
            detailed_card(t, "#FF4B4B")
    render_field_interactive(rt, bt, st.session_state.m_sel_val, r_pred, b_pred)
    bc_cols = st.columns(3)
    for i, t in enumerate(bt):
        with bc_cols[i]:
            detailed_card(t, "#1F77B4")

# --- 6. VIEW: OVERVIEW ---
elif view == "📊 Overview":
    m_row = schema_df[schema_df['match_number'] == st.session_state.m_sel_val].iloc[0]
    rt = [int(m_row['red1']), int(m_row['red2']), int(m_row['red3'])]
    bt = [int(m_row['blue1']), int(m_row['blue2']), int(m_row['blue3'])]
    st.title(f"Overview - Match {st.session_state.m_sel_val}")
    o1, o2 = st.columns(2)
    with o1:
        st.subheader("🔴 Red Alliance")
        for t in rt:
            detailed_card(t, "#FF4B4B")
    with o2:
        st.subheader("🔵 Blue Alliance")
        for t in bt:
            detailed_card(t, "#1F77B4")

# --- 7. VIEW: DEEP DIVE ---
elif view == "🤖 Deep Dive":
    t_list = sorted(set(df['Team Number'].unique()))
    if 't_sel_val' not in st.session_state: 
        st.session_state.t_sel_val = t_list[0]
    sel_t = st.selectbox("🔍 Select Team", t_list, index=t_list.index(st.session_state.t_sel_val))
    st.session_state.t_sel_val = sel_t
    stats = get_team_stats(sel_t)
    st.title(f"Team {sel_t}")
    m = st.columns(5)
    m[0].metric("Avg", round(stats['avg'],1))
    m[1].metric("Auto Move", f"{round(stats['auto'])}%")
    m[2].metric("Climb", stats['climb_pref'])
    m[3].metric("Def %", f"{round(stats['def'])}%")
    m[4].metric("Samples", stats['count'])
    st.divider()
    l, r = st.columns([2, 1.2])
    with l:
        st.subheader("Trend")
        team_m = schema_df[(schema_df[['red1','red2','red3','blue1','blue2','blue3']] == sel_t).any(axis=1)][['match_number']]
        merged = pd.merge(team_m, df[df['Team Number'] == sel_t], left_on='match_number', right_on='Match Number', how='left')
        merged['X'] = merged['match_number'].apply(lambda x: f"M{int(x)}")
        st.plotly_chart(px.line(merged.dropna(subset=['Total Score']), x="X", y="Total Score", markers=True, template="plotly_dark", height=280), use_container_width=True)
        pick = df[df['Team Number'] == sel_t][['PickUp Ground', 'PickUP Human Player', 'PickUp Depot']].mean().fillna(0)*100
        st.plotly_chart(px.bar(x=pick.index.tolist(), y=pick.values.tolist(), height=220, template="plotly_dark"), use_container_width=True)
    with r:
        p_dat = pit_df[pit_df['team_number'] == sel_t]
        if not p_dat.empty:
            st.subheader("🛠️ Pit")
            st.dataframe(p_dat.T, use_container_width=True)
        if stats['died'] > 0:
            st.error(f"Died/Tipped in {stats['died']} matches")
    st.subheader("Match Logs")
    st.table(df[df['Team Number'] == sel_t].dropna(subset=['Comments'])[['Match Number', 'Comments', 'driver skill']].sort_values('Match Number', ascending=False))

# --- 8. VIEW: ALLIANCE SELECTION ---
elif view == "🤝 Alliance Selection":
    st.title("🤝 Alliance Selection Board")
    if st.session_state.active_team_selection:
        st.markdown(f"""<div class="staging-area"><h3>Team {st.session_state.active_team_selection} SELECTED</h3><p>Click a slot on the right to assign them.</p></div>""", unsafe_allow_html=True)
        if st.button("Cancel Selection"):
            st.session_state.active_team_selection = None
            st.rerun()
    drafted = []
    for a in st.session_state.alliances.values():
        drafted.extend([a['c'], a['p1'], a['p2']])
    drafted = [t for t in drafted if t > 0]
    col_l, col_r = st.columns([1.2, 2.5])
    with col_l:
        st.subheader("📋 Teams")
        team_data_list = []
        for t in sorted(set(df['Team Number'].unique())):
            if t > 0:
                team_data_list.append({"team": t, **get_team_stats(t)})
        draft_sorted = pd.DataFrame(team_data_list).sort_values('avg', ascending=False)
        for _, tr in draft_sorted.iterrows():
            t_num = int(tr['team'])
            is_taken = t_num in drafted
            is_active = st.session_state.active_team_selection == t_num
            summary = f"{t_num} — Avg: {round(tr['avg'],1)} | Def: {round(tr['def'])}%"
            with st.expander(f"{'➡️ ' if is_active else ''}{'~~' if is_taken else ''}{summary}"):
                if not is_taken:
                    if st.button(f"SELECT {t_num}", key=f"sel_{t_num}"):
                        st.session_state.active_team_selection = t_num
                        st.rerun()
                st.write(f"Driver: {round(tr['driver'],1)} | Climb: {tr['climb_pref']}")
    with col_r:
        grid = st.columns(2)
        for i in range(1, 9):
            with grid[(i-1)%2]:
                st.markdown(f'<div class="alliance-container"><b>Alliance {i}</b>', unsafe_allow_html=True)
                for l, k in [("Capt","c"),("Pick 1","p1"),("Pick 2","p2")]:
                    curr = st.session_state.alliances[i][k]
                    if st.button(f"{l}: {curr if curr > 0 else 'empty'}", key=f"a{i}{k}", use_container_width=True):
                        if st.session_state.active_team_selection:
                            st.session_state.alliances[i][k] = st.session_state.active_team_selection
                            st.session_state.active_team_selection = None
                            st.rerun()
                        else:
                            st.session_state.alliances[i][k] = 0
                            st.rerun()
                sum_v = sum(get_team_stats(st.session_state.alliances[i][k])['avg'] for k in ['c','p1','p2'])
                st.markdown(f"<div style='text-align:right; color:#4F8BF9;'>Σ Avg: {round(sum_v,1)}</div></div>", unsafe_allow_html=True)