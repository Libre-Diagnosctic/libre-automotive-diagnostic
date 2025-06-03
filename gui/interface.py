#This is the main module that starts the whole GUI app

import tkinter as tk
from tkinter import messagebox, simpledialog
from adapter import connection, initialization
import threading
import itertools
import time
import getpass

class LibreDiagnosticGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Libre Diagnostic")
        self.root.after(0, lambda: self.root.attributes('-zoomed', True))

        self.main_frame = tk.Frame(root, padx=40, pady=40)
        self.main_frame.pack(expand=True)

        self.build_main_screen()

    def build_main_screen(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.status_label = tk.Label(self.main_frame, text="Welcome to Libre Diagnostic", fg="blue", font=("Arial", 30))
        self.status_label.pack(pady=20)

        self.sim_button = tk.Button(self.main_frame, text="🎮 Enter Simulation Mode", font=("Arial", 14), command=self.enter_simulation_mode)
        self.sim_button.pack(pady=10)

        self.scan_button = tk.Button(self.main_frame, text="🔍 Scan for ELM327", font=("Arial", 14), command=self.start_scan_thread)
        self.scan_button.pack(pady=10)

        self.connect_button = tk.Button(self.main_frame, text="🔧 Connect to ELM327", font=("Arial", 20), command=self.start_bind_thread)
        self.connect_button.pack(pady=10)
        self.connect_button.pack_forget()

        self.quit_button = tk.Button(self.main_frame, text="❌ Exit", font=("Arial", 15), command=self.root.quit)
        self.quit_button.pack(side=tk.BOTTOM, pady=30)

        self.loading = False
        self.loading_label = tk.Label(self.main_frame, text="", font=("Arial", 15), fg="gray")

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
        if mac:
            self.status_label.config(text=f"✅ Found device: {mac}", fg="green")
            self.scan_button.pack_forget()
            self.connect_button.pack(pady=10)
        else:
            self.status_label.config(text="❌ No device found", fg="red")
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
        if success:
            self.show_diagnostic_menu()
        else:
            self.status_label.config(text="❌ Binding failed.", fg="red")
            messagebox.showerror("Binding Failed", "Could not bind the device. Wrong password.")

    def show_diagnostic_menu(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        title = tk.Label(self.main_frame, text="🔍 Diagnostic Menu", fg="darkgreen", font=("Arial", 28))
        title.pack(pady=30)

        live_data_btn = tk.Button(self.main_frame, text="📊 Live Data", font=("Arial", 16), command=self.live_data_placeholder)
        live_data_btn.pack(pady=10)

        dtc_btn = tk.Button(self.main_frame, text="🚨 Diagnostic Trouble Codes", font=("Arial", 16), command=self.dtc_placeholder)
        dtc_btn.pack(pady=10)

        brand_btn = tk.Button(self.main_frame, text="🔧 Brand Specific Diagnostic", font=("Arial", 16), command=self.brand_placeholder)
        brand_btn.pack(pady=10)

        back_btn = tk.Button(self.main_frame, text="🔙 Back to Main Menu", font=("Arial", 14), command=self.build_main_screen)
        back_btn.pack(pady=20)

        exit_btn = tk.Button(self.main_frame, text="❌ Exit", font=("Arial", 14), command=self.root.quit)
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
