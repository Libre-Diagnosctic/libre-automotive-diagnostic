#This module gets the MAC from connection.py and binds it to a serial port rfcomm0

import subprocess
import getpass
import shutil

def get_terminal():
    for term in ['gnome-terminal', 'x-terminal-emulator', 'xterm', 'konsole']:
        if shutil.which(term):
            return term
    return None

def run_rfcomm_binding(elm_mac):
    if not elm_mac:
        print("❌ No MAC address provided. Did you run the scan first?")
        return

    terminal = get_terminal()
    if not terminal:
        print("❌ No compatible terminal emulator found.")
        return

    sudo_pass = getpass.getpass("🔐 Enter your sudo password: ")

    cmd = (
        f"echo '{sudo_pass}' | sudo -S rfcomm release all && "
        f"echo '{sudo_pass}' | sudo -S rfcomm bind 0 {elm_mac}"
    )

    print(f"🔧 Binding rfcomm to {elm_mac}...")

    try:
        subprocess.run([terminal, '--', 'bash', '-c', cmd])
    except Exception as e:
        print(f"⚠️ Error: {e}")
