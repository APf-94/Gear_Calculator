import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Page configuration must be the first Streamlit command
st.set_page_config(page_title="Bicycle Speed Calculator", layout="wide", page_icon="🚲")

st.title("🚲 Bicycle Speed Calculator")
st.markdown("Calculate and visualize your bicycle speed based on cadence, wheel circumference, and gearing.")

# --- SIDEBAR (Settings) ---
st.sidebar.header("⚙️ Settings")

# Wheel circumference & Cadence
circumference = st.sidebar.number_input("Wheel Circumference (in mm)", min_value=1000, max_value=3000, value=2110, step=10, 
                                        help="Common value for 28 inches (700x25C) is 2110 mm")
cadence = st.sidebar.slider("Cadence (RPM)", min_value=40, max_value=150, value=95, step=1)

# Chainrings
st.sidebar.subheader("Chainrings")
drivetrain = st.sidebar.radio("Drivetrain", ["2x", "1x"])

if drivetrain == "2x":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        cr_large = st.number_input("Large Chainring", min_value=30, max_value=60, value=52)
    with col2:
        cr_small = st.number_input("Small Chainring", min_value=20, max_value=50, value=36)
    chainrings = {"Large Chainring": cr_large, "Small Chainring": cr_small}
else:
    cr_single = st.sidebar.number_input("Chainring", min_value=30, max_value=60, value=42)
    chainrings = {"Chainring": cr_single}

# Cassette
st.sidebar.subheader("Cassette")
cassette_type = st.sidebar.selectbox("Gears", ["11-speed", "10-speed", "12-speed"])

# Default cogs based on selection
if cassette_type == "10-speed":
    default_cogs = "11, 12, 13, 14, 15, 17, 19, 21, 23, 25"
elif cassette_type == "11-speed":
    default_cogs = "11, 12, 13, 14, 15, 17, 19, 21, 23, 25, 28"
else:
    default_cogs = "11, 12, 13, 14, 15, 16, 17, 19, 21, 24, 27, 30"

cogs_input = st.sidebar.text_input("Cogs (comma-separated)", value=default_cogs)

# Parse and prepare cogs
try:
    # Convert to integers and sort descending (easiest to hardest gear)
    cogs = [int(x.strip()) for x in cogs_input.split(",")]
    cogs = sorted(cogs, reverse=True)
except ValueError:
    st.error("⚠️ Please enter the cogs as comma-separated numbers (e.g., 11, 12, 13).")
    st.stop()

# Warning if the number of entered cogs does not match the selection
expected_cogs = int(cassette_type.split("-")[0])
if len(cogs) != expected_cogs:
    st.warning(f"Warning: You selected {cassette_type}, but entered {len(cogs)} cogs.")

# --- CALCULATION & VISUALIZATION ---
fig = go.Figure()

# X-axis: Format cogs as strings for even spacing in the plot
x_labels = [str(c) for c in cogs]
colors = ['#1f77b4', '#ff7f0e'] # Blue and Orange

table_data = {"Cassette (Teeth)": cogs}

for i, (name, cr_teeth) in enumerate(chainrings.items()):
    # Speed Calculation
    speeds = [cadence * (cr_teeth / c) * circumference * 60 / 1_000_000 for c in cogs]
    
    # For data table
    table_data[f"{name} ({cr_teeth} T) - km/h"] = [round(s, 1) for s in speeds]
    
    # Add trace to plot
    fig.add_trace(go.Scatter(
        x=x_labels, 
        y=speeds, 
        mode='lines+markers',
        name=f'{name} ({cr_teeth} T)',
        line=dict(width=3, color=colors[i]),
        marker=dict(size=10, line=dict(width=2, color='white'))
    ))

# Plotly Layout
fig.update_layout(
    title=f"Speed Distribution at {cadence} RPM",
    xaxis_title="Cassette (Teeth) ➔ harder gear",
    yaxis_title="Speed (km/h)",
    hovermode="x unified",
    xaxis=dict(type='category', title_font=dict(size=14)),
    yaxis=dict(title_font=dict(size=14)),
    legend=dict(
        x=0.01, y=0.99, 
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="lightgray",
        borderwidth=1
    ),
    template="plotly_white"
)

# Output in main window
st.plotly_chart(fig, use_container_width=True)

# Data table output
st.subheader("Tabular Overview (km/h)")
df = pd.DataFrame(table_data)
st.dataframe(df.set_index("Cassette (Teeth)").T, use_container_width=True)

# --- DISCLAIMER & FOOTER ---
st.markdown("---") 

st.caption("""
**© 2026 Dr. Andreas Pfeiffer**  
*Disclaimer:* The calculated values represent theoretical speeds. Actual speeds on the road may vary slightly.
""")