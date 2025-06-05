import tkinter as tk
from tkinter import messagebox
from adapter import connection, initialization
import threading
import itertools
import time
import getpass
from PIL import Image, ImageTk
import os


class LibreDiagnosticGUI:
    def __init__(self, root):
        self.root = root
        self.root.configure(bg="#ffffff")
        self.root.title("Libre Diagnostic")

        root.withdraw()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.geometry(f"{screen_width}x{screen_height}+0+0")
        root.deiconify()

        self.main_frame = tk.Frame(self.root, bg="#ffffff", padx=40, pady=40)
        self.main_frame.pack(expand=True)

        self.build_main_screen()

    def build_main_screen(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logo_path = os.path.join(base_path, "assets", "icons", "librediagnostic-logo.png")

        self.status_label = tk.Label(
            self.main_frame,
            text="",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 18, "bold")
        )
        self.status_label.pack(pady=(0, 20))

        try:
            img = Image.open(logo_path).convert("RGBA")
            bg = Image.new("RGBA", img.size, "#ffffff")
            img = Image.alpha_composite(bg, img).resize((220, 220), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            logo_label = tk.Label(self.main_frame, image=self.logo_img, bg="#ffffff", bd=0, highlightthickness=0)
            logo_label.pack(pady=(40, 10))
        except Exception as e:
            print("⚠️ Logo load failed:", e)

        self.button_style = {
            "font": ("Helvetica", 16, "bold"),
            "width": 25,
            "height": 2,
            "bd": 0,
            "relief": tk.RAISED,
            "bg": "#ffffff",
            "fg": "#18353F",
            "activebackground": "#18353F",
            "activeforeground": "#E7B08D",
            "highlightthickness": 2,
            "highlightbackground": "#18353F",
            "cursor": "hand2"
        }

        self.sim_button = tk.Button(self.main_frame, text="Enter Simulation Mode", command=self.enter_simulation_mode, **self.button_style)
        self.sim_button.pack(pady=(10, 2))

        self.scan_button = tk.Button(self.main_frame, text="Scan for ELM327", command=self.start_scan_thread, **self.button_style)
        self.scan_button.pack(pady=(10, 2))

        self.connect_button = tk.Button(self.main_frame, text="Connect to ELM327", command=self.start_bind_thread, **self.button_style)
        self.connect_button.pack(pady=10)
        self.connect_button.pack_forget()

        self.quit_button = tk.Button(self.main_frame, text="Exit", command=self.root.quit, **self.button_style)
        self.quit_button.pack(side=tk.BOTTOM, pady=30)

        self.loading = False
        self.loading_label = tk.Label(self.main_frame, text="", font=("Helvetica", 12), fg="gray", bg="#ffffff")

    def enter_simulation_mode(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.status_label = tk.Label(self.main_frame, text="Simulation Mode (Placeholder)", fg="purple", font=("Arial", 28))
        self.status_label.pack(pady=30)

        back_button = tk.Button(self.main_frame, text="Back", font=("Arial", 16), command=self.build_main_screen)
        back_button.pack(pady=10)

        exit_button = tk.Button(self.main_frame, text="Exit", font=("Arial", 16), command=self.root.quit)
        exit_button.pack(pady=10)

    def start_scan_thread(self):
        self.scan_button.config(state=tk.DISABLED)
        self.loading = True
        self.loading_label.pack(pady=5)
        threading.Thread(target=self.animate_loading, args=("Scanning",)).start()
        threading.Thread(target=self.scan_and_connect).start()

    def animate_loading(self, task_name):
        for frame in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']):
            if not self.loading or not self.loading_label.winfo_exists():
                break
            try:
                self.loading_label.config(text=f"{task_name}... {frame}")
            except tk.TclError:
                break
            time.sleep(0.1)

    def scan_and_connect(self):
        mac = connection.run_bluetoothctl_and_connect_obd2()
        self.loading = False
        self.loading_label.pack_forget()

        if mac:
            popup = tk.Toplevel(self.root)
            popup.update_idletasks()
            w, h = 600, 200
            x = (popup.winfo_screenwidth() // 2) - (w // 2)
            y = (popup.winfo_screenheight() // 2) - (h // 2)
            popup.geometry(f"{w}x{h}+{x}+{y}")
            popup.title("Device Found")
            popup.configure(bg="white")

            msg = tk.Label(
                popup,
                text=f"Found device:\n{mac}\n\nPress OK to continue.",
                font=("Helvetica", 14),
                bg="white",
                justify="center",
                anchor="center"
            )
            msg.pack(pady=30)


            def on_ok():
                popup.destroy()
                self.sim_button.pack_forget()
                self.scan_button.pack_forget()
                self.connect_button.pack(pady=10)

                if not hasattr(self, 'back_button') or not self.back_button.winfo_exists():
                    self.back_button = tk.Button(self.main_frame, text="Back", command=self.build_main_screen, **self.button_style)
                    self.back_button.pack(pady=10)

            ok_btn = tk.Button(popup, text="OK", command=on_ok, font=("Helvetica", 12, "bold"), bg="#18353F", fg="white", cursor="hand2")
            ok_btn.pack(pady=5)

            popup.transient(self.root)
            popup.grab_set()
        else:
            messagebox.showerror("Connection Failed", "No ELM327 device found.")
            self.scan_button.config(state=tk.NORMAL)

    def start_bind_thread(self):
        sudo_pass = self.ask_sudo_password()

        if not connection.elm_mac:
            messagebox.showwarning("Not Connected", "Please scan and connect to a device first.")
            return

        if sudo_pass:
            self.loading = True
            self.loading_label.pack(pady=5)
            threading.Thread(target=self.animate_loading, args=("Binding",)).start()
            threading.Thread(target=self.bind_device, args=(sudo_pass,)).start()
        else:
            messagebox.showwarning("Cancelled", "Binding cancelled. No password entered.")

    def ask_sudo_password(self):
        popup = tk.Toplevel(self.root)
        popup.title("Device Found")
        popup.configure(bg="white")

        # Set fixed size
        popup_width = 600
        popup_height = 200
        popup.geometry(f"{popup_width}x{popup_height}")

        # Center it after window is drawn
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
        y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        label = tk.Label(popup, text="Enter your sudo password:", font=("Helvetica", 14), bg="white")
        label.pack(pady=(20, 5))

        entry = tk.Entry(popup, show="*", font=("Helvetica", 12), width=30, bd=2, relief=tk.GROOVE)
        entry.pack(pady=(0, 10))

        result = {"value": None}

        def submit():
            result["value"] = entry.get()
            popup.destroy()

        def cancel():
            popup.destroy()

        btn_frame = tk.Frame(popup, bg="white")
        btn_frame.pack()

        ok_btn = tk.Button(btn_frame, text="OK", command=submit, font=("Helvetica", 12, "bold"), bg="#18353F", fg="white", width=10)
        ok_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel, font=("Helvetica", 12), width=10)
        cancel_btn.pack(side=tk.LEFT, padx=10)

        popup.transient(self.root)
        popup.grab_set()
        self.root.wait_window(popup)

        return result["value"]

    def bind_device(self, sudo_pass):
        getpass.getpass = lambda prompt='': sudo_pass
        success = initialization.run_rfcomm_binding(connection.elm_mac, sudo_pass)
        self.loading = False
        self.loading_label.pack_forget()

        if success:
            self.show_diagnostic_menu()
        else:
            self.status_label.config(text="", fg="red")
            messagebox.showerror("Binding Failed", "Could not bind the device. Wrong password.")

    def show_diagnostic_menu(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(self.main_frame, text="Live Diagnostic Menu", fg="darkgreen", bg='#ffffff', font=("Helvetica", 28, "bold"))
        title.pack(pady=30)

        live_data_btn = tk.Button(self.main_frame, text="Request Live Data", command=self.show_live_data_menu, **self.button_style)
        live_data_btn.pack(pady=10)

        dtc_btn = tk.Button(self.main_frame, text="Read and Clear DTCs", command=self.dtc_placeholder, **self.button_style)
        dtc_btn.pack(pady=10)

        brand_btn = tk.Button(self.main_frame, text="Brand Specific Diagnostic", command=self.brand_placeholder, **self.button_style)
        brand_btn.pack(pady=10)

        back_btn = tk.Button(self.main_frame, text="Back to Main Menu", command=self.build_main_screen, **self.button_style)
        back_btn.pack(pady=20)

        exit_btn = tk.Button(self.main_frame, text="Exit", command=self.root.quit, **self.button_style)
        exit_btn.pack(pady=5)

    def show_live_data_menu(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(self.main_frame, text="Live Data", fg="darkgreen", bg='#ffffff', font=("Helvetica", 28, "bold"))
        title.pack(pady=30)

        left_frame = tk.Frame(self.main_frame, bg="#ffffff")
        left_frame.pack(side=tk.LEFT, padx=50)

        right_frame = tk.Frame(self.main_frame, bg="#ffffff")
        right_frame.pack(side=tk.LEFT, padx=50)

        self.live_data_label = tk.Label(right_frame, text="Select a data point to view", font=("Helvetica", 14), bg="#ffffff", wraplength=300)
        self.live_data_label.pack()

        data_points = {
            "Engine RPM": "3000 RPM",
            "Vehicle Speed": "75 km/h",
            "Coolant Temp": "90°C",
            "Throttle Position": "45%",
            "Intake Temp": "30°C",
            "MAF Rate": "12.5 g/s",
            "Fuel Pressure": "300 kPa",
            "O2 Sensor (Bank 1)": "0.85V"
        }

        for label, value in data_points.items():
            tk.Button(left_frame, text=label, command=lambda v=value: self.live_data_label.config(text=v), **self.button_style).pack(pady=5)

        back_btn = tk.Button(self.main_frame, text="Back", command=self.show_diagnostic_menu, **self.button_style)
        back_btn.pack(pady=30)

    def live_data_placeholder(self):
        messagebox.showinfo("Live Data", "Live Data Mode (placeholder)")

    def dtc_placeholder(self):
        messagebox.showinfo("DTC", "Diagnostic Trouble Codes (placeholder)")

    def brand_placeholder(self):
        messagebox.showinfo("Brand Specific", "Brand Specific Diagnostic Mode (placeholder)")


if __name__ == "__main__":
    root = tk.Tk()
    app = LibreDiagnosticGUI(root)
    root.mainloop()
