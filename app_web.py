import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json

# Set Page Layout
st.set_page_config(layout="wide", page_title="ThrustCurve Analysis")

@st.cache_data
def load_data():
    try:
        with open('motors_all.json', 'r') as f:
            data = json.load(f)
        
        #Flatten data for DataFrame
        processed_data = []
        for m in data:
            # Volume Calculation
            d = m['diameter']
            l = m['length']
            r = d / 2
            vol = 3.14159 * (r * r) * l
            
            # Burn Time Fallback
            burn_time = m.get('burnTimeS', 0)
            if burn_time == 0 and m['avgThrustN'] > 0:
                burn_time = m['totImpulseNs'] / m['avgThrustN']

            processed_data.append({
                "Name": m['commonName'],
                "Manufacturer": m['manufacturer'],
                "Thrust (N)": m['avgThrustN'],
                "Impulse (Ns)": m['totImpulseNs'],
                "Weight (g)": m['totalWeightG'],
                "Diameter (mm)": m['diameter'],
                "Length (mm)": m['length'],
                "Volume (mm3)": vol,
                "Isp (s)": m['specificImpulseSec'],
                "Burn Time (s)": burn_time,
                "Label": f"{m['manufacturer']} {m['commonName']}"
            })
        
        return pd.DataFrame(processed_data)
    except FileNotFoundError:
        st.error("Data file 'motors_all.json' not found. Please regenerate data.")
        return pd.DataFrame()

def plot_with_sigma(df, x_col, y_col, title):
    if df.empty:
        st.warning(f"No data available for {title}")
        return None

    # Basic Scatter

    # Basic Scatter
    fig = px.scatter(
        df, x=x_col, y=y_col, 
        title=title,
        hover_name="Label",
        hover_data=["Manufacturer", "Name"]
    )

    # Linear Regression & Sigma Curves logic
    # Need numpy arrays
    x = df[x_col].values
    y = df[y_col].values

    if len(x) > 1:
        try:
            # Sort for clean lines
            sort_idx = np.argsort(x)
            x_sorted = x[sort_idx]
            
            # Fit y = mx + b
            m, b = np.polyfit(x, y, 1)
            y_trend = m * x_sorted + b

            # Calculate Residuals & Std Dev
            # We need to predict on ORIGINAL x to get residuals matching y
            y_pred_original = m * x + b
            residuals = y - y_pred_original
            std_dev = np.std(residuals)

            # Add Traces to Figure
            # Mean Trend
            fig.add_trace(go.Scatter(x=x_sorted, y=y_trend, mode='lines', name='Mean Trend', line=dict(color='black', width=2)))
            
            # 1 Sigma
            fig.add_trace(go.Scatter(x=x_sorted, y=y_trend + std_dev, mode='lines', name='1 Sigma', line=dict(color='green', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=x_sorted, y=y_trend - std_dev, mode='lines', showlegend=False, line=dict(color='green', width=1, dash='dash')))
            
            # 2 Sigma
            fig.add_trace(go.Scatter(x=x_sorted, y=y_trend + 2*std_dev, mode='lines', name='2 Sigma', line=dict(color='orange', width=1, dash='dot')))
            fig.add_trace(go.Scatter(x=x_sorted, y=y_trend - 2*std_dev, mode='lines', showlegend=False, line=dict(color='orange', width=1, dash='dot')))
            
        except Exception as e:
            st.error(f"Error converting data for regression: {e}")

    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key=title)
    return event


# --- Main Application ---
st.title("ThrustCurve Motor Analysis (Web)")

df = load_data()

if not df.empty:
    # Sidebar Filters
    st.sidebar.header("Filter by NAR Certification")
    
    show_low = st.sidebar.checkbox("Low Power (A-G) [< 160 Ns]", value=True)
    show_l1 = st.sidebar.checkbox("Level 1 (H-I) [160 - 640 Ns]", value=True)
    show_l2 = st.sidebar.checkbox("Level 2 (J-L) [640 - 5120 Ns]", value=True)
    show_l3 = st.sidebar.checkbox("Level 3 (M-O) [> 5120 Ns]", value=True)

    # Filtering
    mask = pd.Series([False] * len(df))
    
    if show_low:
        mask |= (df['Impulse (Ns)'] <= 160)
    if show_l1:
        mask |= ((df['Impulse (Ns)'] > 160) & (df['Impulse (Ns)'] <= 640))
    if show_l2:
        mask |= ((df['Impulse (Ns)'] > 640) & (df['Impulse (Ns)'] <= 5120))
    if show_l3:
        mask |= (df['Impulse (Ns)'] > 5120)

    filtered_df = df[mask]
    
    st.write(f"Showing **{len(filtered_df)}** motors out of **{len(df)}** total.")
    
    # Graphs Layout
    col1, col2 = st.columns(2)
    
    events = []

    with col1:
        events.append(plot_with_sigma(filtered_df, "Weight (g)", "Thrust (N)", "Thrust vs Weight"))
        events.append(plot_with_sigma(filtered_df, "Weight (g)", "Impulse (Ns)", "Impulse vs Weight"))
        events.append(plot_with_sigma(filtered_df, "Impulse (Ns)", "Isp (s)", "Specific Impulse vs Total Impulse"))
        events.append(plot_with_sigma(filtered_df, "Burn Time (s)", "Impulse (Ns)", "Impulse vs Burn Time"))

    with col2:
        events.append(plot_with_sigma(filtered_df, "Volume (mm3)", "Thrust (N)", "Thrust vs Size (Volume)"))
        events.append(plot_with_sigma(filtered_df, "Volume (mm3)", "Impulse (Ns)", "Impulse vs Size (Volume)"))
        events.append(plot_with_sigma(filtered_df, "Diameter (mm)", "Impulse (Ns)", "Diameter vs Impulse"))

    # Handle Selections
    selected_motor = None
    for event in events:
        if event and event.selection and len(event.selection.points) > 0:
            # Get the index relative to the filtered dataframe
            try:
                point_index = event.selection.points[0].point_index
                selected_motor = filtered_df.iloc[point_index]
                break # Show first selection found
            except Exception as e:
                st.warning(f"Error retrieving selection: {e}")

    if selected_motor is not None:
        with st.sidebar:
            st.divider()
            st.header("Selected Motor Details")
            st.subheader(f"{selected_motor['Manufacturer']} {selected_motor['Name']}")
            
            # Display stats in a clean format
            st.write(f"**Thrust:** {selected_motor['Thrust (N)']:.2f} N")
            st.write(f"**Impulse:** {selected_motor['Impulse (Ns)']:.2f} Ns")
            st.write(f"**Burn Time:** {selected_motor['Burn Time (s)']:.2f} s")
            st.write(f"**ISP:** {selected_motor['Isp (s)']:.2f} s")
            st.write(f"**Weight:** {selected_motor['Weight (g)']:.2f} g")
            st.write(f"**Diameter:** {selected_motor['Diameter (mm)']} mm")
            st.write(f"**Length:** {selected_motor['Length (mm)']} mm")
            
            details_expander = st.expander("Raw Data")
            details_expander.json(selected_motor.to_dict())
