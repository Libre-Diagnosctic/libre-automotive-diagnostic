# This module gets the MAC from connection.py and binds it to a serial port rfcomm0.
#
# Security note: the sudo password is passed to `sudo -S` via stdin, never
# interpolated into a shell command line. `shell=True` is not used, and the MAC
# address is validated before it reaches the command, so neither the password nor
# the MAC can inject shell metacharacters or leak into the process list (`ps`).

import re
import subprocess

# Canonical Bluetooth MAC: six colon-separated hex octets, e.g. AA:BB:CC:DD:EE:FF
_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")


def run_rfcomm_binding(elm_mac, sudo_pass):
    if not elm_mac:
        print("❌ No MAC address provided. Did you run the scan first?")
        return False

    if not _MAC_RE.match(elm_mac):
        print(f"❌ Refusing to bind: {elm_mac!r} is not a valid Bluetooth MAC address.")
        return False

    def _sudo(args):
        # Feed the password on stdin (sudo -S reads it there) so it never appears
        # in argv. No shell, so `args` is executed verbatim with no interpretation.
        return subprocess.run(
            ["sudo", "-S", *args],
            input=(sudo_pass or "") + "\n",
            capture_output=True,
            text=True,
        )

    print(f"🔧 Binding rfcomm to {elm_mac}...")

    try:
        _sudo(["rfcomm", "release", "all"])
        result = _sudo(["rfcomm", "bind", "0", elm_mac])

        if result.returncode == 0:
            print("✅ Binding successful.")
            return True

        print(f"❌ Binding failed:\n{result.stderr.strip()}")
        return False
    except Exception as e:
        print(f"⚠️ Error during binding: {e}")
        return False
