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
