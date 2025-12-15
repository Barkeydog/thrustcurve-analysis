
import json
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os

# Load Data
try:
    with open('motors_under_640ns.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Error: 'motors_under_640ns.json' not found. Run the extraction script first.")
    exit()

# Extract Data Points
names = [m['commonName'] for m in data]
manufacturers = [m['manufacturer'] for m in data]
avg_thrust = [m['avgThrustN'] for m in data]
total_impulse = [m['totImpulseNs'] for m in data]
total_weight = [m['totalWeightG'] for m in data]
# Calculate Size (Volume approx) for plotting
# Volume = Pi * (d/2)^2 * L
diameters = [m['diameter'] for m in data]
lengths = [m['length'] for m in data]
volumes = [(3.14159 * (d/2)**2 * l) for d, l in zip(diameters, lengths)]
specific_impulse = [m['specificImpulseSec'] for m in data]

class MotorVisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ThrustCurve Motor Analysis (< 640 Ns)")
        self.geometry("1000x800")

        # Main Container
        container = ttk.Frame(self)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Navigation Frame
        nav_frame = ttk.Frame(self)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.frames = {}
        
        # Create Frames for each Graph
        for F in (GraphThrustWeight, GraphThrustSize, GraphImpulseWeight, GraphImpulseSize, GraphIsp, GraphDiameterImpulse):
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

class GraphPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
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

    def plot_scatter(self, x, y, labels, xlabel, ylabel, title):
        self.ax.clear()
        self.names = labels
        self.sc = self.ax.scatter(x, y, alpha=0.5, edgecolors='w', linewidth=0.5, picker=True)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
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
        if not self.names:
            return
            
        # Get position of the first point listed in the event
        pos = self.sc.get_offsets()[ind["ind"][0]]
        self.annot.xy = pos
        
        # Get indices of all points being hovered
        indices = ind["ind"]
        
        # Limit to first 5 names if multiple overlap to avoid huge tooltip
        text = "\n".join([self.names[n] for n in indices[:5]])
        if len(indices) > 5:
            text += "\n..."
            
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_alpha(0.9)


    def plot_hist(self, data, xlabel, title, bins=20):
        self.ax.clear()
        self.ax.hist(data, bins=bins, color='skyblue', edgecolor='black')
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel("Frequency")
        self.ax.set_title(title)
        self.canvas.draw()
        # Clean up scatter interactions if previously used
        self.sc = None
        self.annot = None

class GraphThrustWeight(GraphPage):
    title = "Thrust vs Weight"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        # Create labels specifically for this graph
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(total_weight, avg_thrust, labels, "Total Weight (g)", "Average Thrust (N)", "Thrust vs Total Weight")

class GraphThrustSize(GraphPage):
    title = "Thrust vs Size"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(volumes, avg_thrust, labels, "Approx Volume (mm^3)", "Average Thrust (N)", "Thrust vs Size (Volume)")

class GraphImpulseWeight(GraphPage):
    title = "Impulse vs Weight"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(total_weight, total_impulse, labels, "Total Weight (g)", "Total Impulse (Ns)", "Impulse vs Total Weight")

class GraphImpulseSize(GraphPage):
    title = "Impulse vs Size"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(volumes, total_impulse, labels, "Approx Volume (mm^3)", "Total Impulse (Ns)", "Impulse vs Size (Volume)")

class GraphIsp(GraphPage):
    title = "Isp vs Impulse"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(total_impulse, specific_impulse, labels, "Total Impulse (Ns)", "Specific Impulse (s)", "Specific Impulse vs Total Impulse")

class GraphDiameterImpulse(GraphPage):
    title = "Diameter vs Impulse"
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        labels = [f"{n} ({m})" for n, m in zip(names, manufacturers)]
        self.plot_scatter(diameters, total_impulse, labels, "Diameter (mm)", "Total Impulse (Ns)", "Diameter vs Total Impulse")

if __name__ == "__main__":
    app = MotorVisApp()
    app.mainloop()
