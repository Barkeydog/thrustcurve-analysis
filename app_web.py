import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import plotly.graph_objects as go
import numpy as np
import json
import requests
import base64
import io

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
                "id": m.get('motorId', m.get('id')), # Handle both naming conventions if present
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
        
        # Create lookup dictionary for full details
        # Using the ID as key. Ensure 'id' exists in your JSON.
        # If your JSON keys match the TS interface, it should have 'id' or 'motorId'
        motor_lookup = {m.get('motorId', m.get('id')): m for m in data}

        return pd.DataFrame(processed_data), motor_lookup
    except FileNotFoundError:
        st.error("Data file 'motors_all.json' not found. Please regenerate data.")
        return pd.DataFrame(), {}

@st.cache_data
def fetch_thrust_curve(motor_id):
    """
    Fetches the thrust curve data for a given motor ID from ThrustCurve.org.
    Parses RASP format.
    Returns a DataFrame with 'Time (s)' and 'Thrust (N)'.
    """
    url = "https://www.thrustcurve.org/api/v1/download.json"
    payload = {
        "motorIds": [motor_id]
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        if not results:
            return None

        # Look for a RASP format file
        rasp_data = None
        for res in results:
            if res.get('format') == 'RASP':
                rasp_data = res.get('data')
                break
        
        # If no RASP, take the first one available and hope it works or add more parsers
        if rasp_data is None and results:
             if 'data' in results[0]:
                 rasp_data = results[0]['data']

        if not rasp_data:
            return None

        # Decode Base64
        decoded_bytes = base64.b64decode(rasp_data)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        
        # Parse RASP
        # Lines starting with ; are comments
        # First data line is motor info
        # Subsequent lines are: time thrust [mass]
        
        times = []
        thrusts = []
        
        lines = decoded_str.splitlines()
        header_parsed = False
        
        for line in lines:
            line = line.strip()
            if not line: 
                continue
            if line.startswith(';'): 
                continue
            
            parts = line.split()
            
            if not header_parsed:
                # The first non-comment line is the motor header. We skip it to get to data.
                # Format: name diameter length delays propellant_weight total_weight manufacturer
                # We assume it has at least 3 parts to be a valid header line?
                if len(parts) >= 3:
                   header_parsed = True
                continue
            
            # Data Points
            try:
                t = float(parts[0])
                f = float(parts[1])
                times.append(t)
                thrusts.append(f)
            except (ValueError, IndexError):
                continue
                
        if not times:
            return None
            
        return pd.DataFrame({'Time (s)': times, 'Thrust (N)': thrusts})

    except Exception as e:
        print(f"Error fetching thrust curve: {e}")
        return None

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

df, motor_lookup = load_data()

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
            
            # --- Fetch & Plot Thrust Curve ---
            st.header("Thrust Curve")
            
            # Use the ID to fetch data
            if 'id' in selected_motor:
                mid = selected_motor['id']
                curve_df = fetch_thrust_curve(mid)
                
                if curve_df is not None and not curve_df.empty:
                    # Plot using Plotly for consistency/interactivity
                    fig_curve = px.line(curve_df, x='Time (s)', y='Thrust (N)', title=f"Thrust Curve: {selected_motor['Name']}")
                    st.plotly_chart(fig_curve, use_container_width=True)
                else:
                    st.info("No thrust curve data available for this motor.")
            else:
                 st.warning("Motor ID not found, cannot fetch curve.")

            st.divider()
            st.header("Full Specifications")
            # Get full details from lookup
            full_details = selected_motor.to_dict() # Fallback to dataframe row
            if 'id' in selected_motor:
                full_details = motor_lookup.get(selected_motor['id'], full_details)

            # Display key metrics at top
            st.subheader(f"{full_details.get('manufacturer', 'Unknown')} {full_details.get('commonName', 'Unknown')}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Thrust:** {full_details.get('avgThrustN', 'N/A')} N")
                st.write(f"**Impulse:** {full_details.get('totImpulseNs', 'N/A')} Ns")
                st.write(f"**Burn Time:** {full_details.get('burnTimeS', 'N/A')} s")
            with col_b:
                st.write(f"**Weight:** {full_details.get('totalWeightG', 'N/A')} g")
                st.write(f"**Size:** {full_details.get('diameter', 'N/A')} x {full_details.get('length', 'N/A')} mm")
                st.write(f"**ISP:** {full_details.get('specificImpulseSec', 'N/A')} s")
            
            # Expandable full JSON
            with st.expander("See All Specs"):
                # Format specific keys nicely if needed, or just dump dictionary
                # Filter out huge lists if any exist in the future
                st.json(full_details)
