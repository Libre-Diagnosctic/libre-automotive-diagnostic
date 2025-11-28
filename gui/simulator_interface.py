# The Simulation Graphical User Interface

import tkinter as tk
from simulator.simulator_data import SimulatedLiveData
from gui.simulator_interface_brand_specific import SimulationInterface as BrandSimInterface

class SimulationInterface:
    def __init__(self, root, main_app):
        self.root = root
        self.app = main_app
        self.data_generator = SimulatedLiveData()
        self.build_simulation_menu()

    def enter_brand_simulation_mode(self):
        """Opens the brand-specific simulator UI."""
        for widget in self.app.main_frame.winfo_children():
            widget.destroy()
        BrandSimInterface(self.root, self.app)

    def build_simulation_menu(self):
        for widget in self.app.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(
            self.app.main_frame,
            text="Simulation Menu",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 32, "bold"),
        )
        title.pack(pady=30)

        menu_frame = tk.Frame(self.app.main_frame, bg="#ffffff")
        menu_frame.pack()

        tk.Button(
            menu_frame,
            text="Request Simulated Data",
            command=self.show_simulated_data,
            **self.app.button_style
        ).pack(pady=10)

        tk.Button(
            menu_frame,
            text="Brand Specific Simulation",
            command=self.enter_brand_simulation_mode,
            **self.app.button_style
        ).pack(pady=10)

        tk.Button(
            menu_frame,
            text="Display RPM Graph",
            command=self.open_simulated_rpm_graph,
            **self.app.button_style
        ).pack(pady=10)

        # NEW: Battery voltage button
        tk.Button(
            menu_frame,
            text="Display Battery Voltage",
            command=self.open_simulated_battery_voltage,
            **self.app.button_style
        ).pack(pady=10)

        # Spacer
        tk.Label(menu_frame, text="", bg="#ffffff").pack(pady=20)

        tk.Button(
            menu_frame,
            text="Back to Main Menu",
            command=self.app.build_main_screen,
            **self.app.button_style
        ).pack(pady=(20, 5))
        tk.Button(
            menu_frame,
            text="Exit",
            command=self.root.quit,
            **self.app.button_style
        ).pack(pady=(5, 10))

    def show_simulated_data(self):
        for widget in self.app.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(
            self.app.main_frame,
            text="Simulated Data",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 32, "bold"),
        )
        title.pack(pady=30)

        content_frame = tk.Frame(self.app.main_frame, bg="#ffffff")
        content_frame.pack(expand=True)

        left_frame = tk.Frame(content_frame, bg="#ffffff")
        left_frame.pack(side=tk.LEFT, padx=50, pady=10)

        right_frame = tk.Frame(content_frame, bg="#ffffff", width=300, height=300)
        right_frame.pack(side=tk.LEFT, padx=50, pady=10)

        self.display_label = tk.Label(
            right_frame,
            text="Select a data point to view",
            font=("Helvetica", 16, "bold"),
            fg="#18353F",
            bg="#ffffff",
            wraplength=300,
            justify="center",
        )
        self.display_label.pack(expand=True)

        def update_display(label):
            value = self.data_generator.get_data().get(label, "N/A")
            self.display_label.config(text=f"{label}:\n{value}")

        data = self.data_generator.get_data()
        for label in data.keys():
            tk.Button(
                left_frame,
                text=label,
                command=lambda l=label: update_display(l),
                **self.app.button_style
            ).pack(pady=5)

        tk.Button(
            right_frame,
            text="Rerun",
            command=self.show_simulated_data,
            **self.app.button_style
        ).pack(pady=(20, 10))
        tk.Button(
            right_frame,
            text="Back",
            command=self.build_simulation_menu,
            **self.app.button_style
        ).pack(pady=(20, 10))
        tk.Button(
            right_frame,
            text="Exit",
            command=self.root.quit,
            **self.app.button_style
        ).pack()

    def open_simulated_rpm_graph(self):
        """Open a popup window that shows a live simulated RPM graph."""
        rpm_window = tk.Toplevel(self.root)
        rpm_window.title("RPM Graph")
        rpm_window.configure(bg="#ffffff")

        canvas_width = 600
        canvas_height = 300

        canvas = tk.Canvas(
            rpm_window,
            width=canvas_width,
            height=canvas_height,
            bg="white",
            highlightthickness=0,
        )
        canvas.pack(padx=20, pady=20)

        rpm_values = []

        def update_graph():
            # Stop updating if window is closed
            if not rpm_window.winfo_exists():
                return

            # 1) Get simulated RPM from the same generator
            data = self.data_generator.get_data()
            rpm_text = data.get("RPM", "0").split()[0]  # "1234 rpm" -> "1234"
            try:
                rpm = int(rpm_text)
            except ValueError:
                rpm = 0

            # 2) Store last N values
            rpm_values.append(rpm)
            if len(rpm_values) > 60:
                rpm_values.pop(0)

            # 3) Clear and redraw graph
            canvas.delete("all")

            margin = 20
            x0, y0 = margin, margin
            x1, y1 = canvas_width - margin, canvas_height - margin
            canvas.create_rectangle(x0, y0, x1, y1, outline="#cccccc")

            if rpm_values:
                max_rpm = max(1000, max(rpm_values))
                width = x1 - x0
                height = y1 - y0
                step_x = width / max(len(rpm_values) - 1, 1)

                points = []
                for i, value in enumerate(rpm_values):
                    x = x0 + i * step_x
                    y = y1 - (value / max_rpm) * height
                    points.extend([x, y])

                if len(points) >= 4:
                    canvas.create_line(points, fill="#005f73", width=2)

            # 4) Schedule next update
            canvas.after(500, update_graph)

        update_graph()

    def open_simulated_battery_voltage(self):
        """Open a popup window that shows simulated battery voltage."""
        voltage_window = tk.Toplevel(self.root)
        voltage_window.title("Battery Voltage")
        voltage_window.configure(bg="#ffffff")

        label = tk.Label(
            voltage_window,
            text="Battery Voltage: -- V",
            font=("Helvetica", 18, "bold"),
            bg="#ffffff",
            fg="#18353F",
        )
        label.pack(padx=20, pady=20)

        def update_voltage():
            if not voltage_window.winfo_exists():
                return

            data = self.data_generator.get_data()
            voltage = data.get("Battery Voltage", "--")
            label.config(text=f"Battery Voltage: {voltage}")
            label.after(1000, update_voltage)

        update_voltage()

