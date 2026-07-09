import tkinter as tk
from obd.dtc_lookup import DTCHandler
from utils.ui_worker import run_async, TkSpinner

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

    def _stop_spinner(self):
        spinner = getattr(self, "_spinner", None)
        if spinner is not None:
            spinner.stop()

    def read_dtc(self):
        self.clear_button.config(state=tk.DISABLED)
        self.result_label.config(text="")
        self._spinner = TkSpinner(self.root, self.loading_label, "Reading")
        self._spinner.start()
        run_async(
            self.root,
            work=self._do_read_dtc,
            on_success=self._on_dtc_read,
            on_error=lambda e: self.result_label.config(text=f"Error: {e}"),
            on_done=self._stop_spinner,
        )

    def _do_read_dtc(self):
        handler = DTCHandler()
        if not handler.connect():
            raise ConnectionError("Unable to connect to OBD device.")
        try:
            return handler.read_dtc()
        finally:
            handler.disconnect()

    def _on_dtc_read(self, codes):
        # Runs on the Tk main thread. codes is a list of {"code", "desc"} dicts.
        if codes:
            lines = [f"{c['code']} – {c['desc']}" for c in codes]
            self.result_label.config(text="\n".join(lines))
            self.clear_button.config(state=tk.NORMAL)
        else:
            self.result_label.config(text="✅ No trouble codes found.")
            self.clear_button.config(state=tk.DISABLED)

    def clear_dtc(self):
        self.result_label.config(text="")
        self._spinner = TkSpinner(self.root, self.loading_label, "Clearing")
        self._spinner.start()
        run_async(
            self.root,
            work=self._do_clear_dtc,
            on_success=self._on_dtc_cleared,
            on_error=lambda e: self.result_label.config(text=f"Error: {e}"),
            on_done=self._stop_spinner,
        )

    def _do_clear_dtc(self):
        handler = DTCHandler()
        if not handler.connect():
            raise ConnectionError("Unable to connect to OBD device.")
        try:
            return handler.clear_dtc()
        finally:
            handler.disconnect()

    def _on_dtc_cleared(self, cleared):
        if cleared:
            self.result_label.config(text="✅ Trouble codes cleared.")
            self.clear_button.config(state=tk.DISABLED)
        else:
            self.result_label.config(text="⚠️ Failed to clear codes.")
