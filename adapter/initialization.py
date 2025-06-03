# This module gets the MAC from connection.py and binds it to a serial port rfcomm0

import subprocess

def run_rfcomm_binding(elm_mac, sudo_pass):
    if not elm_mac:
        print("❌ No MAC address provided. Did you run the scan first?")
        return False

    cmd = (
        f"echo '{sudo_pass}' | sudo -S rfcomm release all && "
        f"echo '{sudo_pass}' | sudo -S rfcomm bind 0 {elm_mac}"
    )

    print(f"🔧 Binding rfcomm to {elm_mac}...")

    try:
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            print("✅ Binding successful.")
            return True
        else:
            print(f"❌ Binding failed:\n{result.stderr}")
            return False
    except Exception as e:
        print(f"⚠️ Error during binding: {e}")
        return False
