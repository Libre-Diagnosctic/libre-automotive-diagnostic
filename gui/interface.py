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

        try:
            img = Image.open(logo_path).convert("RGBA")
            bg = Image.new("RGBA", img.size, "#ffffff")
            img = Image.alpha_composite(bg, img).resize((220, 220), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            logo_label = tk.Label(self.main_frame, image=self.logo_img, bg="#ffffff", bd=0, highlightthickness=0)
            logo_label.pack(pady=(40, 10))
        except Exception as e:
            print("\u26a0\ufe0f Logo load failed:", e)

        self.status_label = tk.Label(
            self.main_frame,
            text="Welcome to Libre Diagnostic",
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 28, "bold")
        )
        self.status_label.pack(pady=(0, 20))

        button_style = {
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

        self.sim_button = tk.Button(self.main_frame, text="🎮 Enter Simulation Mode", command=self.enter_simulation_mode, **button_style)
        self.sim_button.pack(pady=(10, 2))

        self.scan_button = tk.Button(self.main_frame, text="🔍 Scan for ELM327", command=self.start_scan_thread, **button_style)
        self.scan_button.pack(pady=(10, 2))

        self.connect_button = tk.Button(self.main_frame, text="🔧 Connect to ELM327", command=self.start_bind_thread, **button_style)
        self.connect_button.pack(pady=10)
        self.connect_button.pack_forget()

        self.quit_button = tk.Button(self.main_frame, text="❌ Exit", command=self.root.quit, **button_style)
        self.quit_button.pack(side=tk.BOTTOM, pady=30)

        self.loading = False
        self.loading_label = tk.Label(self.main_frame, text="", font=("Helvetica", 12), fg="gray", bg="#ffffff")

    def enter_simulation_mode(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.status_label = tk.Label(self.main_frame, text="🧪 Simulation Mode (Placeholder)", fg="purple", font=("Arial", 28))
        self.status_label.pack(pady=30)

        back_button = tk.Button(self.main_frame, text="🔙 Back", font=("Arial", 16), command=self.build_main_screen)
        back_button.pack(pady=10)

        exit_button = tk.Button(self.main_frame, text="❌ Exit", font=("Arial", 16), command=self.root.quit)
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
            self.status_label.config(
                text=f"Found device: {mac}\n\nPress the Connect button.",
                fg="green",
                font=("Helvetica", 18, "bold")  # Font family, size, and weight
            )
            self.scan_button.pack_forget()
            self.connect_button.pack(pady=10)
        else:
            self.status_label.config(text="No device found", fg="red")
            messagebox.showerror("Connection Failed", "No ELM327 device found.")
            self.scan_button.config(state=tk.NORMAL)

    def start_bind_thread(self):
        if not connection.elm_mac:
            messagebox.showwarning("Not Connected", "Please scan and connect to a device first.")
            return

        sudo_pass = simpledialog.askstring("Sudo Password", "Enter your sudo password:", show='*')
        if sudo_pass:
            self.loading = True
            self.loading_label.pack(pady=5)
            threading.Thread(target=self.animate_loading, args=("Binding",)).start()
            threading.Thread(target=self.bind_device, args=(sudo_pass,)).start()
        else:
            messagebox.showwarning("Cancelled", "Binding cancelled. No password entered.")

    def bind_device(self, sudo_pass):
        getpass.getpass = lambda prompt='': sudo_pass
        success = initialization.run_rfcomm_binding(connection.elm_mac, sudo_pass)
        self.loading = False
        self.loading_label.pack_forget()

        if success:
            self.show_diagnostic_menu()
        else:
            self.status_label.config(text="Binding failed.", fg="red")
            messagebox.showerror("Binding Failed", "Could not bind the device. Wrong password.")

    def show_diagnostic_menu(self):
        button_style = {
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

        for widget in self.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(self.main_frame, text="Live Diagnostic Menu", fg="darkgreen", bg='#ffffff', font=("Helvetica", 28, "bold"))
        title.pack(pady=30)

        live_data_btn = tk.Button(self.main_frame, text="📊 Request Live Data", command=self.live_data_placeholder, **button_style)
        live_data_btn.pack(pady=10)

        dtc_btn = tk.Button(self.main_frame, text="🚨 Read and Clear DTCs", command=self.dtc_placeholder, **button_style)
        dtc_btn.pack(pady=10)

        brand_btn = tk.Button(self.main_frame, text="🔧 Brand Specific Diagnostic", command=self.brand_placeholder, **button_style)
        brand_btn.pack(pady=10)

        back_btn = tk.Button(self.main_frame, text="🔙 Back to Main Menu", command=self.build_main_screen, **button_style)
        back_btn.pack(pady=20)

        exit_btn = tk.Button(self.main_frame, text="❌ Exit", command=self.root.quit, **button_style)
        exit_btn.pack(pady=5)

    def live_data_placeholder(self):
        messagebox.showinfo("Live Data", "📊 Live Data Mode (placeholder)")

    def dtc_placeholder(self):
        messagebox.showinfo("DTC", "🚨 Diagnostic Trouble Codes (placeholder)")

    def brand_placeholder(self):
        messagebox.showinfo("Brand Specific", "🔧 Brand Specific Diagnostic Mode (placeholder)")


if __name__ == "__main__":
    root = tk.Tk()
    app = LibreDiagnosticGUI(root)
    root.mainloop()
