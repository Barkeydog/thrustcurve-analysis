import json
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os
import numpy as np

# Load Data
try:
    with open('motors_all.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Error: 'motors_all.json' not found. Run the extraction script first.")
    exit()

# Extract Data Points
names = []
manufacturers = []
avg_thrust = []
total_impulse = []
total_weight = []
diameters = []
lengths = []
volumes = []
specific_impulse = []
specific_impulse = []
burn_times = []
indices = []

for m in data:
    avg_thrust.append(m['avgThrustN'])
    total_impulse.append(m['totImpulseNs'])
    total_weight.append(m['totalWeightG'])
    
    # Volume calculation
    d = m['diameter']
    l = m['length']
    r = (d / 2)
    vol = 3.14159 * (r*r) * l
    volumes.append(vol)
    
    specific_impulse.append(m['specificImpulseSec'])
    burn_times.append(m.get('burnTimeS', m['totImpulseNs'] / m['avgThrustN'] if m['avgThrustN'] > 0 else 0))
    diameters.append(d)
    lengths.append(l) # Keep lengths for completeness, though not directly used after volume calc
    
    names.append(m['commonName'])
    manufacturers.append(m['manufacturer'])
    indices.append(len(names) - 1)


class MotorVisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ThrustCurve Motor Analysis (All Motors)")
        self.geometry("1100x800") # Slightly wider for sidebar

        # Filter Toggles
        self.show_low = tk.BooleanVar(value=True) # A-G
        self.show_l1 = tk.BooleanVar(value=True)  # H-I
        self.show_l2 = tk.BooleanVar(value=True)  # J-L
        self.show_l3 = tk.BooleanVar(value=True)  # M-O

        # Split into Sidebar and Main Content
        main_layout = ttk.Frame(self)
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        sidebar = ttk.Frame(main_layout, width=150, padding=10)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        
        content_area = ttk.Frame(main_layout)
        content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Sidebar Controls
        ttk.Label(sidebar, text="Filters", font=('Helvetica', 12, 'bold')).pack(pady=5)
        
        def on_toggle():
            self.refresh_charts()

        ttk.Checkbutton(sidebar, text="Low Power (A-G)\n< 160 Ns", variable=self.show_low, command=on_toggle).pack(anchor='w', pady=2)
        ttk.Checkbutton(sidebar, text="Level 1 (H-I)\n160-640 Ns", variable=self.show_l1, command=on_toggle).pack(anchor='w', pady=2)
        ttk.Checkbutton(sidebar, text="Level 2 (J-L)\n640-5120 Ns", variable=self.show_l2, command=on_toggle).pack(anchor='w', pady=2)
        ttk.Checkbutton(sidebar, text="Level 3 (M-O)\n> 5120 Ns", variable=self.show_l3, command=on_toggle).pack(anchor='w', pady=2)

        # Graph Container
        container = ttk.Frame(content_area)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Navigation
        nav_frame = ttk.Frame(content_area)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.frames = {}
        
        # Create Frames for each Graph
        for F in (GraphThrustWeight, GraphThrustSize, GraphImpulseWeight, GraphImpulseSize, GraphIsp, GraphDiameterImpulse, GraphBurnTimeImpulse):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

            # Add Button to Nav
            btn = ttk.Button(nav_frame, text=F.title, command=lambda f=F: self.show_frame(f))
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.show_frame(GraphThrustWeight)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()
    
    def refresh_charts(self):
        for frame in self.frames.values():
            frame.redraw()

class GraphPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.figure = plt.Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add Navigation Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.annot = None
        self.sc = None
        self.names = []
        
        self.x_data = None
        self.y_data = None
        self.filter_metric = None # Usually Total Impulse
        self.labels_data = None
        self.labels_data = None
        self.indices_data = None
        self.lbl_x = ""
        self.lbl_y = ""
        self.lbl_title = ""

        self.canvas.mpl_connect("button_press_event", self.on_click)

    def set_data(self, x, y, filter_data, labels, indices, xlabel, ylabel, title):
        self.x_data = np.array(x)
        self.y_data = np.array(y)
        self.filter_metric = np.array(filter_data)
        self.labels_data = np.array(labels)
        self.indices_data = np.array(indices)
        self.lbl_x = xlabel
        self.lbl_y = ylabel
        self.lbl_title = title
        self.redraw()

    def redraw(self):
        if self.x_data is None: return
        
        # Build Filter Mask
        mask = np.zeros(len(self.filter_metric), dtype=bool)
        
        if self.controller.show_low.get():
            mask |= (self.filter_metric <= 160)
        if self.controller.show_l1.get():
            mask |= ((self.filter_metric > 160) & (self.filter_metric <= 640))
        if self.controller.show_l2.get():
            mask |= ((self.filter_metric > 640) & (self.filter_metric <= 5120))
        if self.controller.show_l3.get():
            mask |= (self.filter_metric > 5120)

        # Apply Mask
        x_filtered = self.x_data[mask]
        y_filtered = self.y_data[mask]
        labels_filtered = self.labels_data[mask]
        self.indices_filtered = self.indices_data[mask]

        self.plot_scatter(x_filtered, y_filtered, labels_filtered, self.lbl_x, self.lbl_y, self.lbl_title)

    def plot_scatter(self, x, y, labels, xlabel, ylabel, title):
        self.ax.clear()
        self.names = labels
        self.sc = self.ax.scatter(x, y, alpha=0.5, edgecolors='w', linewidth=0.5, picker=True)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        # Calculate Regression and Sigma Curves
        if len(x) > 1: # Only if enough points
            try:
                x_arr = np.array(x)
                y_arr = np.array(y)
                
                # Linear Fit (degree 1)
                m, b = np.polyfit(x_arr, y_arr, 1)
                
                # Generate trendline points
                x_sort = np.sort(x_arr)
                y_trend = m * x_sort + b
                
                # Predict values for residuals
                y_pred = m * x_arr + b
                residuals = y_arr - y_pred
                std_dev = np.std(residuals)
                
                # Plot Lines
                self.ax.plot(x_sort, y_trend, color='black', linestyle='-', linewidth=1.5, label='Mean Trend')
                
                # 1 Sigma
                self.ax.plot(x_sort, y_trend + std_dev, color='green', linestyle='--', linewidth=1, label='1 Sigma')
                self.ax.plot(x_sort, y_trend - std_dev, color='green', linestyle='--', linewidth=1)
                
                # 2 Sigma
                self.ax.plot(x_sort, y_trend + 2*std_dev, color='orange', linestyle=':', linewidth=1, label='2 Sigma')
                self.ax.plot(x_sort, y_trend - 2*std_dev, color='orange', linestyle=':', linewidth=1)
                
                self.ax.legend()
            except Exception as e:
                print(f"Error calculating regression: {e}")

        # Create Annotation (hidden by default)
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w"),
                            arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)

        self.canvas.mpl_connect("motion_notify_event", self.hover)
        self.canvas.draw()

    def hover(self, event):
        if self.sc is None or self.annot is None:
            return
            
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            cont, ind = self.sc.contains(event)
            if cont:
                self.update_annot(ind)
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            else:
                if vis:
                    self.annot.set_visible(False)
                    self.canvas.draw_idle()

    def update_annot(self, ind):
        if len(self.names) == 0:
            return
            
        pos = self.sc.get_offsets()[ind["ind"][0]]
        self.annot.xy = pos
        indices = ind["ind"]
        
        # Map indices back to filtered labels
        text = "\n".join([self.names[n] for n in indices[:5]])
        if len(indices) > 5:
            text += "\n..."
            
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_alpha(0.9)

    def plot_hist(self, data, xlabel, title, bins=20):
        # Deprecated / Not used in current scatter-only version
        pass

    def on_click(self, event):
        if self.sc is None:
            return
        if event.inaxes != self.ax:
            return

        cont, ind = self.sc.contains(event)
        if cont:
            # Get the first point clicked
            idx_in_filtered = ind["ind"][0]
            if hasattr(self, 'indices_filtered'):
                original_index = self.indices_filtered[idx_in_filtered]
                self.show_details_popup(original_index)

    def show_details_popup(self, index):
        motor = data[index]
        
        popup = tk.Toplevel(self.controller)
        popup.title(f"{motor['manufacturer']} {motor['commonName']}")
        popup.geometry("400x500")
        
        # Create a scrollable frame
        container = ttk.Frame(popup)
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        container.pack(fill="both", expand=True)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate data
        row = 0
        for key, value in motor.items():
            ttk.Label(scrollable_frame, text=key, font=('Helvetica', 10, 'bold')).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=str(value), wraplength=250).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

class GraphThrustWeight(GraphPage):
    title = "Thrust vs Weight"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(total_weight, avg_thrust, total_impulse, labels, indices, "Total Weight (g)", "Average Thrust (N)", "Thrust vs Total Weight")

class GraphThrustSize(GraphPage):
    title = "Thrust vs Size"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(volumes, avg_thrust, total_impulse, labels, indices, "Approx Volume (mm^3)", "Average Thrust (N)", "Thrust vs Size (Volume)")

class GraphImpulseWeight(GraphPage):
    title = "Impulse vs Weight"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(total_weight, total_impulse, total_impulse, labels, indices, "Total Weight (g)", "Total Impulse (Ns)", "Impulse vs Total Weight")

class GraphImpulseSize(GraphPage):
    title = "Impulse vs Size"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(volumes, total_impulse, total_impulse, labels, indices, "Approx Volume (mm^3)", "Total Impulse (Ns)", "Impulse vs Size (Volume)")

class GraphIsp(GraphPage):
    title = "Isp vs Impulse"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(total_impulse, specific_impulse, total_impulse, labels, indices, "Total Impulse (Ns)", "Specific Impulse (s)", "Specific Impulse vs Total Impulse")

class GraphDiameterImpulse(GraphPage):
    title = "Diameter vs Impulse"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(diameters, total_impulse, total_impulse, labels, indices, "Diameter (mm)", "Total Impulse (Ns)", "Diameter vs Total Impulse")

class GraphBurnTimeImpulse(GraphPage):
    title = "Impulse vs Burn Time"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.set_data(burn_times, total_impulse, total_impulse, labels, indices, "Burn Time (s)", "Total Impulse (Ns)", "Total Impulse vs Burn Time")

if __name__ == "__main__":
    app = MotorVisApp()
    app.mainloop()
