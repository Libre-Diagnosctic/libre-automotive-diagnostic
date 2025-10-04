# gui/simulator_interface.py
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from simulator.simulator_brand_specific import (
    available_brands,
    simulate_read_brand_dtc,
    clear_brand_dtc,
    has_active_codes,
)

class SimulationInterface:
    """
    Mirrors the live 'Brand Specific Diagnostic' flow, but backed by simulator logic.
    Reuses styles from the main app instance to stay visually identical.
    """

    def __init__(self, root: tk.Tk, app):
        self.root = root
        self.app = app            # to reuse app.main_frame and app.button_style
        self.main_frame = app.main_frame
        self.button_style = app.button_style

        for w in self.main_frame.winfo_children():
            w.destroy()

        self._build_brand_picker()

    # ---------- Views ----------

    def _title(self, text: str):
        tk.Label(
            self.main_frame,
            text=text,
            fg="#18353F",
            bg="#ffffff",
            font=("Helvetica", 32, "bold"),
        ).pack(pady=30)

    def _build_brand_picker(self):
        self._title("Choose Brand")

        # scrollable list of brand buttons (to match your existing UX)
        container = tk.Frame(self.main_frame, bg="#ffffff")
        container.pack()

        canvas = tk.Canvas(container, width=420, height=300, bg="#ffffff", highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        list_frame = tk.Frame(canvas, bg="#ffffff")

        list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for brand in available_brands():
            tk.Button(list_frame, text=brand, command=lambda b=brand: self._show_brand_menu(b), **self.button_style) \
                .pack(pady=8, padx=12)

        # bottom buttons
        bottom = tk.Frame(self.main_frame, bg="#ffffff")
        bottom.pack(pady=20)
        tk.Button(bottom, text="Back", command=self.app.build_main_screen, **self.button_style).pack(side=tk.LEFT, padx=10)
        tk.Button(bottom, text="Exit", command=self.root.quit, **self.button_style).pack(side=tk.LEFT, padx=10)

    def _show_brand_menu(self, brand: str):
        for w in self.main_frame.winfo_children():
            w.destroy()

        self._title(f"Diagnosing {brand}")

        menu = tk.Frame(self.main_frame, bg="#ffffff")
        menu.pack()

        tk.Button(
            menu,
            text="Read Brand Trouble Codes",
            command=lambda b=brand: self._read_dtc_popup(b),
            **self.button_style
        ).pack(pady=10)

        # Clear button appears only if there are active codes (per requirements)
        self.clear_btn_container = tk.Frame(menu, bg="#ffffff")
        self.clear_btn_container.pack()
        self._render_clear_button(brand)

        # bottom buttons
        bottom = tk.Frame(self.main_frame, bg="#ffffff")
        bottom.pack(pady=30)
        tk.Button(bottom, text="Back", command=self._build_brand_picker, **self.button_style).pack(side=tk.LEFT, padx=10)
        tk.Button(bottom, text="Exit", command=self.root.quit, **self.button_style).pack(side=tk.LEFT, padx=10)

    def _render_clear_button(self, brand: str):
        # clear any prior button
        for w in self.clear_btn_container.winfo_children():
            w.destroy()

        if has_active_codes(brand):
            tk.Button(
                self.clear_btn_container,
                text="Clear Brand Trouble Codes",
                command=lambda b=brand: self._clear_codes(b),
                **self.button_style
            ).pack(pady=10)

    # ---------- Actions ----------

    def _read_dtc_popup(self, brand: str):
        codes = simulate_read_brand_dtc(brand)

        popup = tk.Toplevel(self.root)
        popup.title("Simulated DTCs")
        popup.configure(bg="white")

        # center
        x = (popup.winfo_screenwidth() // 2) - 300
        y = (popup.winfo_screenheight() // 2) - 150
        popup.geometry(f"600x300+{x}+{y}")

        tk.Label(
            popup,
            text=f"{brand} – Trouble Codes",
            font=("Helvetica", 18, "bold"),
            bg="white",
            fg="#18353F"
        ).pack(pady=(20, 10))

        body = tk.Frame(popup, bg="white")
        body.pack(padx=20, pady=5, fill="both", expand=True)

        if not codes:
            tk.Label(body, text="No trouble codes stored.", font=("Helvetica", 14), bg="white").pack(pady=20)
        else:
            # list the codes + descriptions
            for code, desc in codes:
                tk.Label(body, text=f"{code} – {desc}", font=("Helvetica", 14), bg="white", anchor="w", justify="left") \
                    .pack(fill="x", pady=4)

        btns = tk.Frame(popup, bg="white")
        btns.pack(pady=15)

        if codes:
            tk.Button(
                btns, text="Clear Codes",
                command=lambda b=brand, p=popup: self._clear_and_close(b, p),
                font=("Helvetica", 12, "bold"),
                bg="#18353F", fg="white", width=12
            ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btns, text="Close",
            command=popup.destroy,
            font=("Helvetica", 12),
            width=10
        ).pack(side=tk.LEFT, padx=8)

        popup.transient(self.root)
        popup.grab_set()

        # refresh the “Clear” button on brand screen after possibly generating codes
        self._render_clear_button(brand)

    def _clear_and_close(self, brand: str, popup: tk.Toplevel):
        clear_brand_dtc(brand)
        popup.destroy()
        messagebox.showinfo("Cleared", f"All {brand} DTCs cleared.")
        self._render_clear_button(brand)

    def _clear_codes(self, brand: str):
        clear_brand_dtc(brand)
        messagebox.showinfo("Cleared", f"All {brand} DTCs cleared.")
        self._render_clear_button(brand)
