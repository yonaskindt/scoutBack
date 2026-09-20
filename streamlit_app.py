import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="FTC Scouting & Strategy Canvas",
    page_icon="🤖",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 1. HARDCODED GOOGLE SHEET CONFIGURATION & DATA LOADING
# -----------------------------------------------------------------------------
# Replace this URL with your actual public Google Sheet link
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXWkiXWxSOLymfjCzeUhZpjR10aQaxKpMgUnwIadNlY/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data(sheet_url: str) -> pd.DataFrame:
    """
    Loads scouting data from a public Google Sheet CSV export.
    Assumes header starts at Row 2 (skiprows=1) and data starts at Column B.
    """
    try:
        # Convert standard Google Sheet URL to direct CSV export URL
        if "/edit" in sheet_url:
            csv_url = sheet_url.split("/edit")[0] + "/gviz/tq?tqx=out:csv"
        else:
            csv_url = sheet_url

        # Read CSV starting from Row 2 and Column B onward
        df = pd.read_csv(csv_url, skiprows=1)
        df = df.iloc[:, 1:]  # Drop Column A (starts from Column B)
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        st.stop()

# Load Google Sheet directly
df = load_data(GOOGLE_SHEET_URL)

# Ensure Team Number is treated as string
if "Team Number" in df.columns:
    df["Team Number"] = df["Team Number"].astype(str)

# -----------------------------------------------------------------------------
# 2. MAIN NAVIGATION
# -----------------------------------------------------------------------------
st.title("🤖 FTC Strategy & Scouting Dashboard")

view_mode = st.radio(
    "Select View Mode",
    ["Tactical Strategy Canvas", "Match Overview", "Team Deep-Dive", "Alliance Draft Board", "Playoff Simulator"],
    horizontal=True
)

st.divider()

# -----------------------------------------------------------------------------
# VIEW 1: TACTICAL STRATEGY CANVAS (HTML5/JS Canvas Engine)
# -----------------------------------------------------------------------------
if view_mode == "Tactical Strategy Canvas":
    st.subheader("📋 FTC Tactical Canvas")
    st.markdown("Draw match plans, set paths, and position alliance robots directly on the FTC field.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("### Controls")
        draw_color = st.color_picker("Drawing Color", "#FF0000")
        line_width = st.slider("Line Thickness", 1, 10, 3)
        tool_mode = st.radio("Tool", ["Draw", "Erase Clear Path"])
        st.info("Drag robot markers directly on the field. Use the canvas to draw auto routes or defense paths.")

    # HTML5/JS Embedded Canvas with Drag-and-Drop Markers & Freehand Drawing
    canvas_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #canvas-container {{
                position: relative;
                width: 700px;
                height: 700px;
                background-image: url('https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/FTC_Field_Diagram.svg/1024px-FTC_Field_Diagram.svg.png');
                background-size: cover;
                background-position: center;
                border: 3px solid #333;
                border-radius: 8px;
                user-select: none;
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
                font-family: sans-serif;
                color: white;
                cursor: grab;
                box-shadow: 0 4px 6px rgba(0,0,0,0.4);
                border: 2px solid white;
                z-index: 10;
            }}
            .red-alliance {{ background-color: #E63946; }}
            .blue-alliance {{ background-color: #1D3557; }}
        </style>
    </head>
    <body>
        <div id="canvas-container">
            <canvas id="paintCanvas" width="700" height="700"></canvas>
            <!-- FTC Robots (2 Red, 2 Blue) -->
            <div class="robot-marker red-alliance" id="r1" style="top: 100px; left: 50px;">R1</div>
            <div class="robot-marker red-alliance" id="r2" style="top: 180px; left: 50px;">R2</div>
            <div class="robot-marker blue-alliance" id="b1" style="top: 100px; left: 600px;">B1</div>
            <div class="robot-marker blue-alliance" id="b2" style="top: 180px; left: 600px;">B2</div>
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

            canvas.addEventListener('mousedown', (e) => {{
                if (toolMode === 'Erase Clear Path') {{
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    return;
                }}
                isDrawing = true;
                ctx.beginPath();
                ctx.moveTo(e.offsetX, e.offsetY);
            }});

            canvas.addEventListener('mousemove', (e) => {{
                if (isDrawing) {{
                    ctx.lineTo(e.offsetX, e.offsetY);
                    ctx.stroke();
                }}
            }});

            canvas.addEventListener('mouseup', () => isDrawing = false);
            canvas.addEventListener('mouseleave', () => isDrawing = false);

            // Drag and Drop for Robot Markers
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
        st.components.v1.html(canvas_html, height=720)

# -----------------------------------------------------------------------------
# VIEW 2: MATCH OVERVIEW
# -----------------------------------------------------------------------------
elif view_mode == "Match Overview":
    st.subheader("⚔️ Match Strategy & Alliance Comparison")

    all_teams = sorted(df["Team Number"].unique())
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🔴 Red Alliance")
        red1 = st.selectbox("Red 1", all_teams, index=0)
        red2 = st.selectbox("Red 2", all_teams, index=min(1, len(all_teams)-1))

    with col2:
        st.markdown("### 🔵 Blue Alliance")
        blue1 = st.selectbox("Blue 1", all_teams, index=min(2, len(all_teams)-1))
        blue2 = st.selectbox("Blue 2", all_teams, index=min(3, len(all_teams)-1))

    red_teams = [red1, red2]
    blue_teams = [blue1, blue2]

    # Compute alliance expected scores
    red_df = df[df["Team Number"].isin(red_teams)]
    blue_df = df[df["Team Number"].isin(blue_teams)]

    red_avg = red_df.groupby("Team Number")["Total Points"].mean().sum()
    blue_avg = blue_df.groupby("Team Number")["Total Points"].mean().sum()

    st.divider()
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Predicted Red Score", f"{red_avg:.1f} pts")
    metric_col2.metric("Predicted Blue Score", f"{blue_avg:.1f} pts")
    diff = red_avg - blue_avg
    metric_col3.metric("Projected Margin", f"{abs(diff):.1f} pts", delta=f"{'Red' if diff > 0 else 'Blue'} Advantage")

    # Comparison Breakdown Chart
    comp_df = df[df["Team Number"].isin(red_teams + blue_teams)].copy()
    avg_breakdown = comp_df.groupby("Team Number")[["Auto Score", "Teleop Score", "Endgame Score"]].mean().reset_index()

    fig = px.bar(
        avg_breakdown,
        x="Team Number",
        y=["Auto Score", "Teleop Score", "Endgame Score"],
        title="Average Point Breakdown by Match Phase",
        labels={"value": "Average Points", "variable": "Phase"},
        barmode="stack"
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# VIEW 3: TEAM DEEP-DIVE
# -----------------------------------------------------------------------------
elif view_mode == "Team Deep-Dive":
    st.subheader("🔍 Individual Team Analysis")

    selected_team = st.selectbox("Select Team", sorted(df["Team Number"].unique()))
    team_df = df[df["Team Number"] == selected_team].sort_values("Match Number")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Matches Played", len(team_df))
    m2.metric("Avg Total Score", f"{team_df['Total Points'].mean():.1f}")
    m3.metric("Avg Auto Score", f"{team_df['Auto Score'].mean():.1f}")
    m4.metric("Avg Endgame Score", f"{team_df['Endgame Score'].mean():.1f}")

    # Trend Chart Over Matches
    fig_trend = px.line(
        team_df,
        x="Match Number",
        y=["Auto Score", "Teleop Score", "Endgame Score", "Total Points"],
        markers=True,
        title=f"Performance Trend - Team {selected_team}"
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # Scout Comments
    st.markdown("### 📝 Scout Comments & Notes")
    for _, row in team_df.iterrows():
        st.write(f"**Match {row['Match Number']}:** {row.get('Scout Comments', 'No comments recorded.')}")

# -----------------------------------------------------------------------------
# VIEW 4: ALLIANCE DRAFT BOARD
# -----------------------------------------------------------------------------
elif view_mode == "Alliance Draft Board":
    st.subheader("📊 Alliance Selection Draft Rankings")

    # Compute overall team metrics
    draft_df = df.groupby("Team Number").agg(
        Avg_Total=("Total Points", "mean"),
        Avg_Auto=("Auto Score", "mean"),
        Avg_Teleop=("Teleop Score", "mean"),
        Avg_Endgame=("Endgame Score", "mean"),
        Max_Total=("Total Points", "max"),
        Consistency=("Total Points", "std")
    ).reset_index()

    # Fill NaN std with 0 for single matches
    draft_df["Consistency"] = draft_df["Consistency"].fillna(0)

    # Sort option
    sort_by = st.selectbox("Sort Draft Board By", ["Avg_Total", "Avg_Auto", "Avg_Teleop", "Avg_Endgame", "Max_Total"])
    draft_df = draft_df.sort_values(by=sort_by, ascending=False).reset_index(drop=True)

    st.dataframe(
        draft_df.style.highlight_max(axis=0, color="#d4edda"),
        use_container_width=True
    )

    fig_scatter = px.scatter(
        draft_df,
        x="Avg_Auto",
        y="Avg_Teleop",
        size="Avg_Total",
        color="Team Number",
        text="Team Number",
        title="Auto vs. Teleop Efficiency Matrix"
    )
    fig_scatter.update_traces(textposition='top center')
    st.plotly_chart(fig_scatter, use_container_width=True)

# -----------------------------------------------------------------------------
# VIEW 5: PLAYOFF SIMULATOR
# -----------------------------------------------------------------------------
elif view_mode == "Playoff Simulator":
    st.subheader("🏆 Bracket & Playoff Simulator")

    st.markdown("Simulate a bracket matchup between two 2-robot alliance combinations.")

    all_teams = sorted(df["Team Number"].unique())

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Alliance 1")
        a1 = st.selectbox("Captain (Alliance 1)", all_teams, index=0, key="a1")
        a2 = st.selectbox("Pick 1 (Alliance 1)", all_teams, index=min(1, len(all_teams)-1), key="a2")

    with col_b:
        st.markdown("#### Alliance 2")
        b1 = st.selectbox("Captain (Alliance 2)", all_teams, index=min(2, len(all_teams)-1), key="b1")
        b2 = st.selectbox("Pick 1 (Alliance 2)", all_teams, index=min(3, len(all_teams)-1), key="b2")

    # Monte Carlo Match Simulation
    st.divider()
    if st.button("🚀 Run 1,000 Match Simulations"):
        a1_scores = df[df["Team Number"] == a1]["Total Points"].values
        a2_scores = df[df["Team Number"] == a2]["Total Points"].values
        b1_scores = df[df["Team Number"] == b1]["Total Points"].values
        b2_scores = df[df["Team Number"] == b2]["Total Points"].values

        # Sample with replacement
        n_sims = 1000
        sim_a = np.random.choice(a1_scores, n_sims) + np.random.choice(a2_scores, n_sims)
        sim_b = np.random.choice(b1_scores, n_sims) + np.random.choice(b2_scores, n_sims)

        a_wins = np.sum(sim_a > sim_b)
        b_wins = np.sum(sim_b > sim_a)
        ties = np.sum(sim_a == sim_b)

        st.markdown(f"### Simulation Results ({n_sims} iterations)")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("Alliance 1 Win Rate", f"{(a_wins/n_sims)*100:.1f}%")
        res_col2.metric("Alliance 2 Win Rate", f"{(b_wins/n_sims)*100:.1f}%")
        res_col3.metric("Tie Chance", f"{(ties/n_sims)*100:.1f}%")

        # Distribution plot
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Histogram(x=sim_a, name="Alliance 1", opacity=0.75, marker_color="red"))
        fig_sim.add_trace(go.Histogram(x=sim_b, name="Alliance 2", opacity=0.75, marker_color="blue"))
        fig_sim.update_layout(barmode='overlay', title="Score Distribution Simulation", xaxis_title="Total Alliance Points", yaxis_title="Frequency")
        st.plotly_chart(fig_sim, use_container_width=True)