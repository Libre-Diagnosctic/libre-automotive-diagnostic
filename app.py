import tkinter as tk
from gui.main_interface import LibreDiagnosticGUI


def main():
    root = tk.Tk()
    app = LibreDiagnosticGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
