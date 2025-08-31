import tkinter as tk

CAR_BRANDS = [
    "Audi", "BMW", "Ford", "Honda", "Hyundai",
    "Kia", "Mazda", "Nissan", "Toyota", "Volkswagen"
]

class BrandInterface:
    def __init__(self, root, parent_gui):
        self.root   = root
        self.parent = parent_gui
        self.frame  = parent_gui.main_frame
        self.style  = parent_gui.button_style
        self.build_brand_picker()

    # ------------------------------------------------------------------ #
    # 1.  Brand‑selection view                                           #
    # ------------------------------------------------------------------ #
    def build_brand_picker(self):
        self._clear()

        tk.Label(self.frame, text="Choose Brand",
                 font=("Helvetica", 32, "bold"),
                 fg="#18353F", bg="#ffffff").pack(pady=30)

        box = tk.Frame(self.frame, bg="#ffffff")
        canvas = tk.Canvas(box, bg="#ffffff", highlightthickness=0,
                           width=400, height=300)
        vsb = tk.Scrollbar(box, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ffffff")

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        box.pack()
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for brand in CAR_BRANDS:
            tk.Button(inner, text=brand,
                      command=lambda b=brand: self.select_brand(b),
                      **self.style).pack(fill="x", pady=4)

        # ⇢  extra space before nav buttons
        tk.Label(self.frame, bg="#ffffff").pack(pady=20)

        nav = tk.Frame(self.frame, bg="#ffffff")
        nav.pack(pady=10)
        tk.Button(nav, text="Back",
                  command=self.parent.show_diagnostic_menu,
                  **self.style).pack(side="left", padx=10)
        tk.Button(nav, text="Exit",
                  command=self.root.quit,
                  **self.style).pack(side="left", padx=10)

    # ------------------------------------------------------------------ #
    # 2.  After a brand is chosen                                        #
    # ------------------------------------------------------------------ #
    def select_brand(self, brand):
        self.parent.selected_brand = brand    # store for backend later
        self.build_brand_actions(brand)

    def build_brand_actions(self, brand):
        self._clear()

        tk.Label(self.frame,
                 text=f"Diagnosing {brand}",
                 font=("Helvetica", 28, "bold"),
                 fg="#18353F", bg="#ffffff").pack(pady=40)

        tk.Button(self.frame, text="Read Brand Trouble Codes",
                  command=lambda: self.read_brand_dtcs(brand),
                  **self.style).pack(pady=10)

        tk.Button(self.frame, text="Clear Brand Trouble Codes",
                  command=lambda: self.clear_brand_dtcs(brand),
                  **self.style).pack(pady=10)

        # ⇢  bigger gap before nav
        tk.Label(self.frame, bg="#ffffff").pack(pady=40)

        nav = tk.Frame(self.frame, bg="#ffffff")
        nav.pack()
        tk.Button(nav, text="Back",
                  command=self.build_brand_picker,
                  **self.style).pack(side="left", padx=10)
        tk.Button(nav, text="Exit",
                  command=self.root.quit,
                  **self.style).pack(side="left", padx=10)

    # ------------------------------------------------------------------ #
    # 3.  Placeholder actions                                            #
    # ------------------------------------------------------------------ #
    def read_brand_dtcs(self, brand):
        tk.messagebox.showinfo(
            "Coming soon",
            f"Read‑DTC routine for {brand} will be wired to the backend."
        )

    def clear_brand_dtcs(self, brand):
        tk.messagebox.showinfo(
            "Coming soon",
            f"Clear‑DTC routine for {brand} will be wired to the backend."
        )

    # ------------------------------------------------------------------ #
    def _clear(self):
        for w in self.frame.winfo_children():
            w.destroy()
