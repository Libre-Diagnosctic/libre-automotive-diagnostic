import tkinter as tk
from tkinter import messagebox
from obd.dtc_lookup import DTCHandler
import threading
import time
import itertools

class DTCInterface:
    def __init__(self, root, parent_gui):
        self.root = root
        self.parent_gui = parent_gui
        self.main_frame = parent_gui.main_frame
        self.button_style = parent_gui.button_style
        self.loading = False

        self.build_screen()

    def build_screen(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        tk.Label(self.main_frame, text="Read & Clear DTCs", font=("Helvetica", 28, "bold"),
                 fg="#18353F", bg="#ffffff").pack(pady=30)

        button_frame = tk.Frame(self.main_frame, bg="#ffffff")
        button_frame.pack()

        self.read_button = tk.Button(button_frame, text="Read Trouble Codes", command=self.read_dtc, **self.button_style)
        self.read_button.pack(pady=10)

        self.clear_button = tk.Button(button_frame, text="Clear Trouble Codes", command=self.clear_dtc, **self.button_style)
        self.clear_button.pack(pady=10)
        self.clear_button.config(state=tk.DISABLED)  # initially disabled

        self.result_label = tk.Label(self.main_frame, text="", font=("Helvetica", 14),
                                     fg="#18353F", bg="#ffffff", wraplength=700, justify="center")
        self.result_label.pack(pady=20)

        self.loading_label = tk.Label(self.main_frame, text="", font=("Helvetica", 12),
                                      fg="gray", bg="#ffffff")
        self.loading_label.pack(pady=5)

        tk.Button(self.main_frame, text="Back", command=self.parent_gui.show_diagnostic_menu,
                  **self.button_style).pack(pady=10)

        tk.Button(self.main_frame, text="Exit", command=self.root.quit,
                  **self.button_style).pack(pady=10)

    def animate_loader(self, task_name):
        for frame in itertools.cycle(['|', '/', '-', '\\']):
            if not self.loading or not self.loading_label.winfo_exists():
                break
            try:
                self.loading_label.config(text=f"{task_name}... {frame}")
            except tk.TclError:
                break
            time.sleep(0.1)

    def read_dtc(self):
        self.clear_button.config(state=tk.DISABLED)
        self.result_label.config(text="")
        self.loading = True
        threading.Thread(target=self.animate_loader, args=("Reading",)).start()
        threading.Thread(target=self._read_dtc_logic).start()

    def _read_dtc_logic(self):
        try:
            port, baudrate ="/dev/rfcomm0", 38400
            if self.parent_gui.usb_device:
                port, baudrate = self.parent_gui.usb_device
            handler = DTCHandler(port, baudrate)
            if handler.connect():
                codes = handler.read_dtc()
                handler.disconnect()
                if codes:
                    self.result_label.config(text="\n".join(codes))
                    self.clear_button.config(state=tk.NORMAL)
                else:
                    self.result_label.config(text="✅ No trouble codes found.")
                    self.clear_button.config(state=tk.DISABLED)
            else:
                messagebox.showerror("Connection Failed", "Unable to connect to OBD device.")
        except Exception as e:
            self.result_label.config(text=f"Error: {e}")
        finally:
            self.loading = False
            self.loading_label.config(text="")

    def clear_dtc(self):
        self.result_label.config(text="")
        try:
            handler = DTCHandler()
            if handler.connect():
                cleared = handler.clear_dtc()
                handler.disconnect()
                if cleared:
                    self.result_label.config(text="✅ Trouble codes cleared.")
                    self.clear_button.config(state=tk.DISABLED)
                else:
                    self.result_label.config(text="⚠️ Failed to clear codes.")
        except Exception as e:
            self.result_label.config(text=f"Error: {e}")
