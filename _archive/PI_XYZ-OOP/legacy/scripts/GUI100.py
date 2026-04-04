import tkinter as tk
from tkinter import ttk, messagebox

# -- Simulation placeholder functions for demonstration --
# Replace with actual pipython controller logic as needed.

class DummyAxisController:
   def __init__(self, axis_key):
       self.axis_key = axis_key
       self.position = 0.0

   def MOV(self, axis, pos):
       print(f"[SIM] {self.axis_key}-Axis moving to {pos}")
       self.position = pos

   def qPOS(self, axis):
       return {axis: self.position}

   def axes(self):
       return

class DummyPiTools:
   @staticmethod
   def waitontarget(device): pass

# --- GUI Class ---
class MotionSequenceGUI:
   def __init__(self, root):
       self.root = root
       root.title("XYZ Motion Sequence Controller")

       self.simulation_var = tk.BooleanVar(value=True)
       ttk.Checkbutton(root, text="Simulation Mode (no hardware)", variable=self.simulation_var).grid(row=0, column=0, columnspan=4, sticky="w", pady=5)

       labels = ['Waypoint', 'X', 'Y', 'Z', 'Hold Time (s)']
       for c, name in enumerate(labels):
           ttk.Label(root, text=name).grid(row=1, column=c)

       self.entries = []
       self.num_waypoints = 4
       for r in range(self.num_waypoints):
           row_entries = []
           ttk.Label(root, text=f"{r+1}").grid(row=2+r, column=0)
           for c in range(1, 5):
               ent = ttk.Entry(root, width=10)
               ent.grid(row=2+r, column=c)
               row_entries.append(ent)
           self.entries.append(row_entries)

       ttk.Button(root, text="Start Motion Sequence", command=self.start_sequence).grid(row=2+self.num_waypoints, column=0, columnspan=4, pady=10)

   def start_sequence(self):
       try:
           waypoints = []
           for idx, row in enumerate(self.entries):
               xyz = [float(ent.get()) if ent.get() else None for ent in row[:3]]
               hold = float(row.get()) if row.get() else 0.0
               if all(v is not None for v in xyz):
                   waypoints.append({'X': xyz, 'Y': xyz, 'Z': xyz, 'hold': hold})
           sim_mode = self.simulation_var.get()
           self.execute_sequence(waypoints, sim_mode)
       except Exception as e:
           messagebox.showerror("Input Error", f"Invalid input: {e}")

   def execute_sequence(self, waypoints, simulate=True):
       if simulate:
           controllers = {axis: DummyAxisController(axis) for axis in ('X', 'Y', 'Z')}
           pitools = DummyPiTools()
       else:
           # -- Here, add the real pipython import/setup/init code --
           messagebox.showinfo("Not Implemented", "Hardware mode not yet implemented in this demo.")
           return
       for i, wp in enumerate(waypoints):
           print(f"\n[SCRIPT] Waypoint {i+1}: X={wp['X']} Y={wp['Y']} Z={wp['Z']}  Hold={wp['hold']}s")
           for axis in ['X', 'Y', 'Z']:
               controllers[axis].MOV(0, wp[axis])
           if simulate:
               print(f"  [SIM] Holding for {wp['hold']} seconds...")
           self.root.after(int(wp['hold'] * 1000), lambda: None)
       messagebox.showinfo("Sequence Done", "All waypoints executed (simulation mode)." if simulate else "Waypoints sent to hardware.")

root = tk.Tk()
gui = MotionSequenceGUI(root)
root.mainloop()
