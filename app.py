import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="Evacuation ASET vs RSET", layout="wide")

st.title("🏃‍♂️ Advanced ASET vs. RSET Evacuation Calculator")
st.markdown("Model complex egress paths with multiple bottlenecks and stairwells using the SFPE Hydraulic Model.")

# --- SFPE Constants ---
SFPE_DATA = {
    "Door / Archway": {"speed": 1.19, "flow": 1.32, "boundary": 0.15},
    "Corridor": {"speed": 1.19, "flow": 1.32, "boundary": 0.20},
    "Stairs (Down)": {"speed": 0.85, "flow": 1.01, "boundary": 0.15}
}

# --- 1. Scenario Parameters ---
st.header("1. Scenario Settings (Seconds)")
col1, col2, col3 = st.columns(3)

with col1:
    aset_sec = st.number_input("ASET (Available Safe Egress Time in sec)", value=900.0, step=60.0)
with col2:
    t_detect_sec = st.number_input("Detection & Alarm Time (sec)", value=120.0, step=30.0)
with col3:
    t_pre_sec = st.number_input("Pre-Movement / Response Time (sec)", value=180.0, step=30.0)

# --- 2. Route Builder (Network) ---
st.divider()
st.header("2. Define Egress Route")
st.markdown("Map out the sequence of components. The table below will calculate the queue time for every single row and identify the governing bottleneck.")

default_route = pd.DataFrame([
    {"Component": "Room 1 Exit Door", "Type": "Door / Archway", "Width (m)": 0.9, "Travel Dist (m)": 15.0, "Population": 50},
    {"Component": "Corridor to Stair", "Type": "Corridor", "Width (m)": 1.5, "Travel Dist (m)": 20.0, "Population": 100},
    {"Component": "Stairwell Down", "Type": "Stairs (Down)", "Width (m)": 1.2, "Travel Dist (m)": 12.0, "Population": 150},
    {"Component": "Final Ground Exit", "Type": "Door / Archway", "Width (m)": 1.8, "Travel Dist (m)": 5.0, "Population": 150}
])

edited_route = st.data_editor(
    default_route,
    num_rows="dynamic",
    column_config={
        "Type": st.column_config.SelectboxColumn("Component Type", options=["Door / Archway", "Corridor", "Stairs (Down)"], required=True),
        "Width (m)": st.column_config.NumberColumn("Clear Width (m)", min_value=0.1, step=0.1),
        "Travel Dist (m)": st.column_config.NumberColumn("Travel Dist (m)", min_value=0.0, step=1.0),
        "Population": st.column_config.NumberColumn("Population Passing Through", min_value=1, step=1)
    },
    use_container_width=True
)

# --- Calculation Engine ---
if len(edited_route) > 0:
    results_list = []
    total_walk_time_sec = 0
    max_flow_time_sec = 0
    governing_index = -1

    # First Pass: Calculate everything to find the max flow time
    for index, row in edited_route.iterrows():
        comp_type = row["Type"]
        width = row["Width (m)"]
        dist = row["Travel Dist (m)"]
        pop = row["Population"]
        
        speed = SFPE_DATA[comp_type]["speed"]
        spec_flow = SFPE_DATA[comp_type]["flow"]
        boundary = SFPE_DATA[comp_type]["boundary"]
        
        w_eff = max(0.0, width - (2 * boundary))
        walk_time = dist / speed if speed > 0 else 0
        flow_cap = w_eff * spec_flow
        flow_time = pop / flow_cap if flow_cap > 0 else float('inf')
        
        total_walk_time_sec += walk_time
        if flow_time > max_flow_time_sec and flow_time != float('inf'):
            max_flow_time_sec = flow_time
            governing_index = index
            governing_bottleneck_name = row["Component"]
            
        results_list.append({
            "Component": row["Component"],
            "Effective Width (m)": round(w_eff, 2),
            "Capacity (pax/sec)": round(flow_cap, 2),
            "Walk Time (s)": round(walk_time, 1),
            "Queue / Flow Time (s)": round(flow_time, 1) if flow_time != float('inf') else "Too narrow!",
            "Governing": "" # We will fill this in next
        })

    # Mark the governing bottleneck in the list
    if governing_index != -1:
        results_list[governing_index]["Governing"] = "✅ YES"

    # Total times
    t_move_sec = total_walk_time_sec + max_flow_time_sec
    rset_total_sec = t_detect_sec + t_pre_sec + t_move_sec
    safety_margin_sec = aset_sec - rset_total_sec

    # --- Results & Visualization ---
    st.divider()
    st.header("3. Evacuation Results")

    m1, m2, m3, m4 = st.columns(4)
    # Primary metric is now seconds, secondary metric is minutes
    m1.metric("Required Safe Egress (RSET)", f"{rset_total_sec:.0f} sec", f"{rset_total_sec / 60:.1f} min", delta_color="off")
    m2.metric("Available Safe Egress (ASET)", f"{aset_sec:.0f} sec", f"{aset_sec / 60:.1f} min", delta_color="off")
    
    margin_color = "normal" if safety_margin_sec >= 0 else "inverse"
    m3.metric("Safety Margin", f"{safety_margin_sec:.0f} sec", f"{safety_margin_sec / 60:.1f} min clear", delta_color=margin_color)
    m4.metric("Governing Bottleneck", governing_bottleneck_name, f"Queue: {max_flow_time_sec:.0f} sec", delta_color="off")

    st.write("")

    # Timeline Chart (Now in Seconds)
    st.subheader("ASET vs RSET Timeline (Seconds)")
    fig = go.Figure()

    fig.add_trace(go.Bar(y=["Timeline"], x=[t_detect_sec], name="Detection & Alarm", orientation='h', marker=dict(color='#3498db'), text=f"{t_detect_sec:.0f}s", textposition="inside"))
    fig.add_trace(go.Bar(y=["Timeline"], x=[t_pre_sec], name="Pre-Movement", orientation='h', marker=dict(color='#f1c40f'), text=f"{t_pre_sec:.0f}s", textposition="inside"))
    fig.add_trace(go.Bar(y=["Timeline"], x=[total_walk_time_sec], name="Total Walk Time", orientation='h', marker=dict(color='#e67e22'), text=f"{total_walk_time_sec:.0f}s", textposition="inside"))
    fig.add_trace(go.Bar(y=["Timeline"], x=[max_flow_time_sec], name="Bottleneck Queue", orientation='h', marker=dict(color='#d35400'), text=f"{max_flow_time_sec:.0f}s", textposition="inside"))

    fig.add_trace(go.Scatter(
        x=[aset_sec, aset_sec], y=[-0.5, 0.5], mode="lines+text", name="ASET Limit",
        line=dict(color="red", width=4, dash="dash"), text=["", f"ASET ({aset_sec:.0f} s)"], textposition="top right"
    ))

    fig.update_layout(
        barmode='stack', 
        xaxis_title="Time (Seconds)", 
        yaxis=dict(showticklabels=False), 
        height=300, 
        hovermode="y unified", 
        margin=dict(l=0, r=0, t=30, b=0)
    )
    fig.update_xaxes(range=[0, max(aset_sec, rset_total_sec) * 1.1])
    st.plotly_chart(fig, use_container_width=True)

    # Detailed Table
    st.subheader("Component Breakdown & Queue Times")
    st.markdown("SFPE methodology assumes the Total Movement Time is the sum of **all walk times** plus the **single longest queue time** (the governing bottleneck).")
    
    # Apply a quick highlight to the governing row using Pandas styling
    df_results = pd.DataFrame(results_list)
    def highlight_governing(val):
        color = '#d4edda' if val == "✅ YES" else ''
        return f'background-color: {color}'
    
    st.dataframe(df_results.style.map(highlight_governing, subset=['Governing']), use_container_width=True)

else:
    st.warning("Please add at least one component to the egress route.")
