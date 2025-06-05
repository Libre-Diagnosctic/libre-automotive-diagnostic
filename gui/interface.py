import tkinter as tk
from tkinter import messagebox, simpledialog
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
        self.root.title("Libre Diagnostic")

        root.withdraw()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.geometry(f"{screen_width}x{screen_height}+0+0")
        root.deiconify()

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        bg_path = os.path.join(base_path, "assets", "icons", "background.png")
        self.bg_pil_image = Image.open(bg_path)
        self.bg_image = ImageTk.PhotoImage(self.bg_pil_image)

        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_bg = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_image)
        self.canvas.bind("<Configure>", self.resize_background)

        # Outer frame for border effect sized to 90% of window
        self.border_frame = tk.Frame(self.canvas, bg="#E7B08D", padx=4, pady=4)
        self.canvas_frame_id = self.canvas.create_window(
            screen_width // 2,
            screen_height // 2,
            window=self.border_frame,
            anchor="center",
            width=int(screen_width * 0.9),
            height=int(screen_height * 0.9)
        )

        # Inner white frame
        self.main_frame = tk.Frame(self.border_frame, bg="#ffffff", padx=40, pady=40)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.build_main_screen()

    def resize_background(self, event):
        if event.width < 2 or event.height < 2:
            return
        resized = self.bg_pil_image.resize((event.width, event.height), Image.Resampling.LANCZOS)
        self.bg_image = ImageTk.PhotoImage(resized)
        self.canvas.itemconfig(self.canvas_bg, image=self.bg_image)
        self.canvas.coords(self.canvas_frame_id, event.width // 2, event.height // 2)
        self.canvas.itemconfig(self.canvas_frame_id, width=int(event.width * 0.9), height=int(event.height * 0.9))


    def build_main_screen(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logo_path = os.path.join(base_path, "assets", "icons", "librediagnostic-logo.png")

        self.status_label = tk.Label(self.main_frame, text="", fg="#18353F", bg="#ffffff", font=("Helvetica", 18, "bold"))
        self.status_label.pack(pady=(0, 20))

        try:
            img = Image.open(logo_path).convert("RGBA")
            bg = Image.new("RGBA", img.size, "#ffffff")
            img = Image.alpha_composite(bg, img).resize((220, 220), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            logo_label = tk.Label(self.main_frame, image=self.logo_img, bg="#ffffff", bd=0, highlightthickness=0)
            logo_label.pack(pady=(40, 10))
        except Exception as e:
            print("\u26a0\ufe0f Logo load failed:", e)

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
        tk.Label(self.main_frame, text="Simulation Mode (Placeholder)", fg="purple", font=("Arial", 28)).pack(pady=30)
        tk.Button(self.main_frame, text="Back", font=("Arial", 16), command=self.build_main_screen).pack(pady=10)
        tk.Button(self.main_frame, text="Exit", font=("Arial", 16), command=self.root.quit).pack(pady=10)

    def start_scan_thread(self):
        self.scan_button.config(state=tk.DISABLED)
        self.loading = True
        self.loading_label.pack(pady=5)
        threading.Thread(target=self.animate_loading, args=("Scanning",)).start()
        threading.Thread(target=self.scan_and_connect).start()

    def animate_loading(self, task_name):
        for frame in itertools.cycle(['\u280b','\u2819','\u2839','\u2838','\u283c','\u2834','\u2826','\u2827','\u2807','\u280f']):
            if not self.loading or not self.loading_label.winfo_exists(): break
            try: self.loading_label.config(text=f"{task_name}... {frame}")
            except tk.TclError: break
            time.sleep(0.1)

    def scan_and_connect(self):
        mac = connection.run_bluetoothctl_and_connect_obd2()
        self.loading = False
        self.loading_label.pack_forget()
        if mac:
            popup = tk.Toplevel(self.root)
            popup.title("Device Found")
            self.center_popup(popup)
            x = (popup.winfo_screenwidth() // 2) - 300
            y = (popup.winfo_screenheight() // 2) - 100
            popup.geometry(f"600x200+{x}+{y}")
            popup.configure(bg="white")
            tk.Label(popup, text=f"Found device:\n{mac}\n\nPress OK to continue.", font=("Helvetica", 14), bg="white").pack(pady=30)
            def on_ok():
                popup.destroy()
                self.sim_button.pack_forget()
                self.scan_button.pack_forget()
                self.connect_button.pack(pady=10)
                if not hasattr(self, 'back_button') or not self.back_button.winfo_exists():
                    self.back_button = tk.Button(self.main_frame, text="Back", command=self.build_main_screen, **self.button_style)
                    self.back_button.pack(pady=10)
            tk.Button(popup, text="OK", command=on_ok, font=("Helvetica", 12, "bold"), bg="#18353F", fg="white").pack(pady=5)
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

    def ask_sudo_password(self):
        popup = tk.Toplevel(self.root)
        popup.title("Device Found")
        popup.geometry("600x200")
        x = (popup.winfo_screenwidth() // 2) - 300
        y = (popup.winfo_screenheight() // 2) - 100
        popup.geometry(f"600x200+{x}+{y}")
        popup.configure(bg="white")
        tk.Label(popup, text="Enter your sudo password:", font=("Helvetica", 14), bg="white").pack(pady=(20, 5))
        entry = tk.Entry(popup, show="*", font=("Helvetica", 12), width=30, bd=2, relief=tk.GROOVE)
        entry.pack(pady=(0, 10))
        result = {"value": None}
        def submit(): result["value"] = entry.get(); popup.destroy()
        def cancel(): popup.destroy()
        btn_frame = tk.Frame(popup, bg="white")
        btn_frame.pack()
        tk.Button(btn_frame, text="OK", command=submit, font=("Helvetica", 12, "bold"), bg="#18353F", fg="white", width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Cancel", command=cancel, font=("Helvetica", 12), width=10).pack(side=tk.LEFT, padx=10)
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

        title = tk.Label(
            self.main_frame,
            text="Live Diagnostic Menu",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 32, "bold")
        )
        title.pack(pady=30)

        menu_frame = tk.Frame(self.main_frame, bg="#ffffff")
        menu_frame.pack()

        tk.Button(menu_frame, text="Request Live Data", command=self.show_live_data_menu, **self.button_style).pack(pady=10)
        tk.Button(menu_frame, text="Read and Clear DTCs", command=self.dtc_placeholder, **self.button_style).pack(pady=10)
        tk.Button(menu_frame, text="Brand Specific Diagnostic", command=self.brand_placeholder, **self.button_style).pack(pady=10)

        spacer = tk.Label(menu_frame, text="", bg="#ffffff")
        spacer.pack(pady=10)

        tk.Button(menu_frame, text="Back to Main Menu", command=self.build_main_screen, **self.button_style).pack(pady=(10, 5))
        tk.Button(menu_frame, text="Exit", command=self.root.quit, **self.button_style).pack(pady=(5, 10))

    def dtc_placeholder(self):
        messagebox.showinfo("DTC", "Diagnostic Trouble Codes (placeholder)")

    def brand_placeholder(self):
        messagebox.showinfo("Brand Specific", "Brand Specific Diagnostic Mode (placeholder)")


    def show_live_data_menu(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(
            self.main_frame,
            text="Live Data",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 32, "bold")
        )
        title.pack(pady=30)

        content_frame = tk.Frame(self.main_frame, bg="#ffffff")
        content_frame.pack(expand=True)

        left_frame = tk.Frame(content_frame, bg="#ffffff")
        left_frame.pack(side=tk.LEFT, padx=50, pady=10)

        right_frame = tk.Frame(content_frame, bg="#ffffff", width=300, height=300)
        right_frame.pack_propagate(False)
        right_frame.pack(side=tk.LEFT, padx=50, pady=10)

        self.live_data_label = tk.Label(
            right_frame,
            text="Select a data point to view",
            font=("Helvetica", 16, "bold"),
            fg="#18353F",
            bg="#ffffff",
            wraplength=300,
            anchor="center",
            justify="center"
        )
        self.live_data_label.pack(expand=True)

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

        back_button = tk.Button(right_frame, text="Back", command=self.show_diagnostic_menu, **self.button_style)
        back_button.pack(pady=(20, 10))

        exit_button = tk.Button(right_frame, text="Exit", command=self.root.quit, **self.button_style)
        exit_button.pack()


    def live_data_placeholder(self):
        messagebox.showinfo("Live Data", "Live Data Mode (placeholder)")

    def dtc_placeholder(self):
        messagebox.showinfo("DTC", "Diagnostic Trouble Codes (placeholder)")

    def brand_placeholder(self):
        messagebox.showinfo("Brand Specific", "Brand Specific Diagnostic Mode (placeholder)")

    def center_popup(self, popup, width=600, height=200):
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LibreDiagnosticGUI(root)
    root.mainloop()