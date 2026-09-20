import streamlit as st
import pandas as pd
import plotly.express as px
import os
import base64
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="FTC Scouting Hub", layout="wide", initial_sidebar_state="collapsed")

# --- SPREADSHEET CONFIGURATION ---
SHEET_ID = "1mXWkiXWxSOLymfjCzeUhZpjR10aQaxKpMgUnwIadNlY"  # Replace with your actual Google Sheet ID
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# --- DATA FETCHING WITH CACHING ---
@st.cache_data(ttl=30)
def get_google_data(sheet_id: str, tab_name: str) -> pd.DataFrame:
    """Fetch and standardize data from a Google Sheet tab using Streamlit secrets."""
    if "gcp_service_account" not in st.secrets:
        st.error("Missing `gcp_service_account` in Streamlit secrets.")
        return pd.DataFrame()

    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(tab_name)
        records = worksheet.get_all_records()

        if not records:
            return pd.DataFrame()

        df_out = pd.DataFrame(records)
        df_out.columns = [str(c).strip().lower() for c in df_out.columns]
        return df_out

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{tab_name}' not found.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching '{tab_name}': {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def load_all_ftc_data():
    """Loads all worksheets and preprocesses fields for application logic."""
    data = get_google_data(SHEET_ID, "Data")
    schema = get_google_data(SHEET_ID, "Matches")
    ali = get_google_data(SHEET_ID, "Alliances")

    if data.empty or schema.empty:
        return None, None, None

    # Process Numeric Scoring Columns
    for col in ['+1', '+3', '+5', 'amount in hub']:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

    score_cols = [c for c in ['+1', '+3', '+5'] if c in data.columns]
    data['total score'] = data[score_cols].sum(axis=1) if score_cols else 0

    # Clean boolean flags
    def clean_bool(val):
        return 1 if str(val).lower() in ['true', '1', '1.0', 'yes', 'y'] else 0

    for col in ['moved?', 'died?', 'tipped/fell over?', 'defence/ to other side']:
        if col in data.columns:
            clean_key = col.replace('?', '').split('/')[0].strip() + '_num'
            data[clean_key] = data[col].apply(clean_bool)

    return data, schema, ali

# Load data into session memory
df, schema_df, alliance_df = load_all_ftc_data()

if df is None:
    st.error("Failed to load FTC Data. Check your Google Sheet ID, tab names, and credentials.")
    st.stop()

# --- INITIALIZE SESSION STATE ---
if 'nav_view' not in st.session_state:
    st.session_state.nav_view = "🗺️ Field Map"

if 'alliances_state' not in st.session_state:
    st.session_state.alliances_state = {i: {"c": 0, "p1": 0} for i in range(1, 9)}

if 'm_sel_val' not in st.session_state:
    st.session_state.m_sel_val = 1 

if 'active_team_selection' not in st.session_state:
    st.session_state.active_team_selection = None

if 'playoff_red_swap' not in st.session_state: st.session_state.playoff_red_swap = False
if 'playoff_blue_swap' not in st.session_state: st.session_state.playoff_blue_swap = False
if 'playoff_red_out' not in st.session_state: st.session_state.playoff_red_out = None
if 'playoff_blue_out' not in st.session_state: st.session_state.playoff_blue_out = None

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    .main .block-container { max-width: 100%; padding: 0.5rem 0.8rem 6rem 0.8rem; }
    
    .team-info-box-detailed { 
        padding: 8px; 
        border-radius: 8px; 
        border-top: 4px solid; 
        background-color: rgba(255, 255, 255, 0.08); 
        font-size: 13px; 
        box-shadow: 1px 1px 4px rgba(0,0,0,0.3); 
        margin-bottom: 8px; 
    }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 2px; }
    .note-text { 
        font-style: italic; 
        font-size: 11px; 
        color: #BDC3C7; 
        border-top: 1px solid rgba(255,255,255,0.1); 
        margin-top: 4px; 
        padding-top: 2px; 
        height: 36px; 
        overflow: hidden; 
    }
    .staging-area { 
        background: rgba(79, 139, 249, 0.2); 
        padding: 12px; 
        border-radius: 10px; 
        border: 2px solid #4F8BF9; 
        margin-bottom: 15px; 
        text-align: center; 
    }

    .bottom-nav-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #0E1117;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        padding: 8px 16px;
        z-index: 99999;
        box-shadow: 0 -4px 12px rgba(0,0,0,0.5);
    }
    
    [data-testid="stHtml"] { padding: 0 !important; margin: 0 !important; }
    iframe { display: block; margin: 0 auto; border: none; overflow: hidden; }

    @media (max-width: 1024px) {
        .team-info-box-detailed { font-size: 11px; }
        .note-text { font-size: 10px; height: 30px; }
        .stButton button { font-size: 12px !important; padding: 4px 8px !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_team_stats(team_num):
    if team_num == 0: 
        return {"avg": 0, "count": 0, "climb_pref": "N/A", "last_note": "No notes", "driver": 0, "died": 0, "warn": False}
    
    t_data = df[df['team number'] == team_num] if 'team number' in df.columns else pd.DataFrame()
    stat_dict = {"avg": 0, "count": 0, "climb_pref": "N/A", "last_note": "No notes", "driver": 0, "warn": False}
    
    if not t_data.empty:
        stat_dict.update({"avg": t_data['total score'].mean(), "count": len(t_data)})
        if 'climbing' in t_data: 
            stat_dict["climb_pref"] = t_data['climbing'].dropna().mode().iloc[0] if not t_data['climbing'].dropna().empty else "N/A"
        if 'driver skill' in t_data: 
            stat_dict["driver"] = pd.to_numeric(t_data['driver skill'], errors='coerce').fillna(0).mean()
        if 'comments' in t_data:
            note_s = t_data.dropna(subset=['comments'])
            if not note_s.empty: 
                stat_dict['last_note'] = str(note_s.iloc[-1]['comments'])
        
        died_sum = (t_data['died_num'].sum() if 'died_num' in t_data else 0) + (t_data['tipped_num'].sum() if 'tipped_num' in t_data else 0)
        stat_dict['died'] = int(died_sum)
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

def render_field_interactive(red_teams, blue_teams):
    img_file = "ftcfield.png"
    max_w = "500px"
    
    img_b64 = ""
    if os.path.exists(img_file):
        with open(img_file, "rb") as f: 
            img_b64 = base64.b64encode(f.read()).decode()
    
    red_bots = "".join([f'<div class="bot red" style="left: 15%; top: {25+(i*35)}%;" id="r{i}">{red_teams[i]}</div>' for i in range(len(red_teams))])
    blue_bots = "".join([f'<div class="bot blue" style="right: 15%; top: {25+(i*35)}%;" id="b{i}">{blue_teams[i]}</div>' for i in range(len(blue_teams))])

    html_content = f"""
    <div id="controls" style="display:flex; gap:8px; margin:0 auto; max-width:{max_w}; padding:0 0 5px 0;">
        <button onclick="setMode('move')" style="flex:1; padding:6px; cursor:pointer; background:#4F8BF9; color:white; border:none; border-radius:5px; font-weight:bold; font-size:11px;">Move</button>
        <button onclick="setMode('draw')" style="flex:1; padding:6px; cursor:pointer; background:#2ECC71; color:white; border:none; border-radius:5px; font-weight:bold; font-size:11px;">Draw</button>
        <button onclick="clearCanvas()" style="flex:0.5; padding:6px; cursor:pointer; background:#E74C3C; color:white; border:none; border-radius:5px; font-weight:bold; font-size:11px;">Clear</button>
    </div>
    <div id="field-viewport" style="width:100%; max-width:{max_w}; margin:0 auto; overflow:hidden; border: 2px solid #555; border-radius: 8px; background:#000; line-height:0;">
        <div id="field-container" style="position: relative; width: 100%; padding-bottom: 100%; height: 0; touch-action: none; margin:0;">
            <img src="data:image/png;base64,{img_b64}" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit: contain; pointer-events: none; display:block;">
            <canvas id="strategy-canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:10; cursor:crosshair; pointer-events:none;"></canvas>
            {red_bots} {blue_bots}
        </div>
    </div>
    <style>
        .bot {{ position: absolute; width: 34px; height: 34px; border-radius: 50%; color: white; font-family: sans-serif; font-weight: bold; font-size: 10px; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 3px 6px black; cursor: grab; z-index: 20; touch-action: none; transform: translate(-50%, -50%); }}
        .bot:active {{ cursor: grabbing; }} .red {{ background: #FF4B4B; }} .blue {{ background: #1F77B4; }}
    </style>
    <script>
        const canvas = document.getElementById('strategy-canvas'); const ctx = canvas.getContext('2d');
        const container = document.getElementById('field-container'); const bots = document.querySelectorAll('.bot');
        let mode = 'move'; let drawing = false;
        function setMode(m) {{ mode = m; canvas.style.pointerEvents = (m === 'draw' ? 'auto' : 'none'); }}
        function clearCanvas() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); }}
        function resize() {{ canvas.width = container.clientWidth; canvas.height = container.clientHeight; }}
        window.onload = resize; window.onresize = resize; setTimeout(resize, 100);
        function getPos(e) {{
            const rect = canvas.getBoundingClientRect();
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            return {{ x: clientX - rect.left, y: clientY - rect.top }};
        }}
        canvas.addEventListener('mousedown', e => {{ if(mode==='draw') {{ drawing=true; const p=getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }} }});
        canvas.addEventListener('mousemove', e => {{ if(drawing && mode==='draw') {{ const p=getPos(e); ctx.lineTo(p.x, p.y); ctx.strokeStyle='#2ECC71'; ctx.lineWidth=4; ctx.stroke(); }} }});
        canvas.addEventListener('mouseup', () => drawing=false);
        canvas.addEventListener('touchstart', e => {{ if(mode==='draw') {{ drawing=true; const p=getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }} }}, {{passive:false}});
        canvas.addEventListener('touchmove', e => {{ if(drawing && mode==='draw') {{ const p=getPos(e); ctx.lineTo(p.x, p.y); ctx.strokeStyle='#2ECC71'; ctx.lineWidth=4; ctx.stroke(); }} }}, {{passive:false}});
        canvas.addEventListener('touchend', () => drawing=false);
        bots.forEach(bot => {{
            let isDragging = false;
            const move = (e) => {{
                if (!isDragging) return; const evt = e.touches ? e.touches[0] : e;
                const rect = container.getBoundingClientRect();
                bot.style.left = ((evt.clientX - rect.left) / rect.width * 100) + '%';
                bot.style.top = ((evt.clientY - rect.top) / rect.height * 100) + '%';
                if(e.touches) e.preventDefault();
            }};
            bot.addEventListener('mousedown', () => {{ if(mode==='move') isDragging = true; }});
            bot.addEventListener('touchstart', () => {{ if(mode==='move') isDragging = true; }}, {{passive:false}});
            document.addEventListener('mousemove', move); document.addEventListener('touchmove', move, {{passive:false}});
            document.addEventListener('mouseup', () => isDragging = false); document.addEventListener('touchend', () => isDragging = false);
        }});
    </script>
    """
    st.components.v1.html(html_content, height=540)

# --- TOP MATCH SELECTOR ---
if st.session_state.nav_view in ["🗺️ Field Map", "📊 Overview"]:
    m_col = 'match_number' if 'match_number' in schema_df.columns else 'match number'
    if m_col in schema_df.columns:
        m_list = sorted(schema_df[m_col].dropna().unique().astype(int))
        st.session_state.m_sel_val = st.selectbox(
            "Select Match Number", 
            m_list, 
            index=m_list.index(st.session_state.m_sel_val) if st.session_state.m_sel_val in m_list else 0
        )

# --- VIEW ROUTING ---
view = st.session_state.nav_view

if view == "🗺️ Field Map":
    m_col = 'match_number' if 'match_number' in schema_df.columns else 'match number'
    m_row = schema_df[schema_df[m_col] == st.session_state.m_sel_val].iloc[0]
    
    r_keys = [c for c in ['red1','red2'] if c in m_row.index and pd.notna(m_row[c])]
    b_keys = [c for c in ['blue1','blue2'] if c in m_row.index and pd.notna(m_row[c])]
    rt, bt = [int(m_row[c]) for c in r_keys], [int(m_row[c]) for c in b_keys]
    
    c1, c2, c3 = st.columns([1.2, 3.2, 1.2])
    with c1:
        st.markdown("<div style='text-align:center; color:#FF4B4B; font-weight:bold; margin-bottom:5px;'>RED ALLIANCE</div>", unsafe_allow_html=True)
        for t in rt: detailed_card(t, "#FF4B4B")
    with c2:
        render_field_interactive(rt, bt)
        st.markdown(f"<div style='text-align:center; font-weight:bold; color:#BDC3C7; margin-top:-10px;'>MATCH {st.session_state.m_sel_val}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div style='text-align:center; color:#1F77B4; font-weight:bold; margin-bottom:5px;'>BLUE ALLIANCE</div>", unsafe_allow_html=True)
        for t in bt: detailed_card(t, "#1F77B4")

elif view == "🤖 per team":
    t_list = sorted(set(df['team number'].dropna().unique()))
    sel_t = st.selectbox("🔍 Select Team", t_list)
    stats = get_team_stats(sel_t)
    
    st.title(f"Team {sel_t}")
    m = st.columns(4)
    m[0].metric("Avg Score", round(stats['avg'], 1))
    m[1].metric("Climb", stats['climb_pref'])
    m[2].metric("Skill", round(stats['driver'], 1))
    m[3].metric("Samples", stats['count'])
    
    st.divider()
    l, r = st.columns([2, 1.2])
    with l:
        merged = df[df['team number'] == sel_t].copy()
        m_col = 'match number' if 'match number' in merged.columns else 'match_number'
        merged['X'] = merged[m_col].apply(lambda x: f"M{int(x)}")
        st.plotly_chart(px.line(merged.sort_values(m_col), x="X", y="total score", markers=True, template="plotly_dark", height=280), use_container_width=True)
        if 'comments' in merged.columns:
            st.table(merged.dropna(subset=['comments'])[[m_col, 'comments']].sort_values(m_col, ascending=False))
    with r:
        if stats['died'] > 0: 
            st.error(f"⚠️ Team Died/Tipped in {stats['died']} matches!")

elif view == "🤝 Alliance Selection":
    st.title("🤝 FTC Draft Board")
    if st.session_state.active_team_selection:
        st.markdown(f'<div class="staging-area"><h3>Team {st.session_state.active_team_selection} SELECTED</h3></div>', unsafe_allow_html=True)
        if st.button("Cancel"): 
            st.session_state.active_team_selection = None
            st.rerun()
            
    col_l, col_r = st.columns([1.2, 2.5])
    with col_l:
        st.subheader("📋 Teams")
        t_data = pd.DataFrame([{"t": t, **get_team_stats(t)} for t in sorted(set(df['team number'].unique()))]).sort_values('avg', ascending=False)
        for _, tr in t_data.iterrows():
            t_num = int(tr['t'])
            if st.button(f"{t_num} (Avg: {round(tr['avg'], 1)})", key=f"sel_{t_num}", use_container_width=True):
                st.session_state.active_team_selection = t_num
                st.rerun()
                
    with col_r:
        grid = st.columns(2)
        slots = [("Capt", "c"), ("Pick 1", "p1")]
        for i in range(1, 9):
            with grid[(i-1)%2]:
                with st.container(border=True):
                    st.markdown(f"**Alliance {i}**")
                    for label, key in slots:
                        curr = st.session_state.alliances_state[i][key]
                        if st.button(f"{label}: {curr if curr > 0 else 'empty'}", key=f"a{i}{key}", use_container_width=True):
                            if st.session_state.active_team_selection:
                                st.session_state.alliances_state[i][key] = st.session_state.active_team_selection
                                st.session_state.active_team_selection = None
                                st.rerun()
                            else: 
                                st.session_state.alliances_state[i][key] = 0
                                st.rerun()

elif view == "📊 Overview":
    m_col = 'match_number' if 'match_number' in schema_df.columns else 'match number'
    m_row = schema_df[schema_df[m_col] == st.session_state.m_sel_val].iloc[0]
    r_keys = [c for c in ['red1','red2'] if c in m_row.index and pd.notna(m_row[c])]
    b_keys = [c for c in ['blue1','blue2'] if c in m_row.index and pd.notna(m_row[c])]
    rt, bt = [int(m_row[c]) for c in r_keys], [int(m_row[c]) for c in b_keys]
    
    st.title(f"Overview - Match {st.session_state.m_sel_val}")
    o1, o2 = st.columns(2)
    with o1:
        st.subheader("🔴 Red Alliance")
        for t in rt: detailed_card(t, "#FF4B4B")
    with o2:
        st.subheader("🔵 Blue Alliance")
        for t in bt: detailed_card(t, "#1F77B4")

elif view == "🏆 Playoffs":
    st.title("🏆 FTC Playoffs")
    if not alliance_df.empty:
        a_names = [f"Alliance {i+1}" for i in range(len(alliance_df))]
        p_slots = [c for c in ['c', '1e'] if c in alliance_df.columns]
        
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            r_choice = st.selectbox("🔴 Red Alliance", a_names, index=0)
            r_row = alliance_df.iloc[a_names.index(r_choice)]
            r_roster = [int(r_row[k]) for k in p_slots if pd.notna(r_row[k])]
            if '2e' in r_row and pd.notna(r_row['2e']):
                swap_r = st.toggle("Use Red Backup?", key="playoff_red_swap")
                if swap_r:
                    out_r = st.selectbox("Red to sit out", r_roster, index=r_roster.index(st.session_state.playoff_red_out) if st.session_state.playoff_red_out in r_roster else 0)
                    st.session_state.playoff_red_out = out_r
                    r_roster = [int(r_row['2e']) if x == out_r else x for x in r_roster]
                    
        with c_sel2:
            b_choice = st.selectbox("🔵 Blue Alliance", a_names, index=min(1, len(a_names)-1))
            b_row = alliance_df.iloc[a_names.index(b_choice)]
            b_roster = [int(b_row[k]) for k in p_slots if pd.notna(b_row[k])]
            if '2e' in b_row and pd.notna(b_row['2e']):
                swap_b = st.toggle("Use Blue Backup?", key="playoff_blue_swap")
                if swap_b:
                    out_b = st.selectbox("Blue to sit out", b_roster, index=b_roster.index(st.session_state.playoff_blue_out) if st.session_state.playoff_blue_out in b_roster else 0)
                    st.session_state.playoff_blue_out = out_b
                    b_roster = [int(b_row['2e']) if x == out_b else x for x in b_roster]

        c1, c2, c3 = st.columns([1.2, 3.2, 1.2])
        with c1:
            for t in r_roster: detailed_card(t, "#FF4B4B")
        with c2: 
            render_field_interactive(r_roster, b_roster)
        with c3:
            for t in b_roster: detailed_card(t, "#1F77B4")

# --- FIXED BOTTOM NAVIGATION DOCK ---
st.markdown('<div class="bottom-nav-container">', unsafe_allow_html=True)
b_col1, b_col2, b_col3, b_col4, b_col5, b_col6 = st.columns([1, 1, 1, 1, 1, 0.8])

nav_items = [
    ("🗺️ Map", "🗺️ Field Map"),
    ("📊 Overview", "📊 Overview"),
    ("🤖 Team", "🤖 per team"),
    ("🤝 Alliances", "🤝 Alliance Selection"),
    ("🏆 Playoffs", "🏆 Playoffs")
]

for col, (label, target_view) in zip([b_col1, b_col2, b_col3, b_col4, b_col5], nav_items):
    with col:
        is_active = st.session_state.nav_view == target_view
        if st.button(label, key=f"nav_btn_{target_view}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.nav_view = target_view
            st.rerun()

with b_col6:
    if st.button("🔄 Sync", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)