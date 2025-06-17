#This module finds the MAC of the ELM327 device and establishes the bluetooth connection

import subprocess
import time
import re

# Global variable to store ELM327 MAC address.
elm_mac = None

# Common OBD2 device name patterns
OBD2_NAMES = [
    # Core ELM327/OBD2 terms
    'OBDII', 'OBD-II', 'OBD2', 'OBD', 'ELM327',

    # Popular and widely compatible brands
    'OBDLink', 'OBDLink MX+', 'OBDLink LX', 'OBDLink EX', 'OBDLink SX',

    # Vgate series
    'Vgate', 'Vgate iCar Pro', 'Vgate vLinker', 'vLinker FS', 'vLinker MC+', 'vLinker FD',

    # Veepeak series
    'Veepeak', 'Veepeak OBDCheck BLE', 'Veepeak Mini',

    # Other notable brands
    'BAFX', 'Panlong', 'OBDMONSTER', 'RACOONA', 'Car2LS ScanX', 'ELS27', 'STN1110', 'STN1170', 'STN2120',

    # Generic or less reliable names
    'Micro Mechanic', 'THINMI.COM', 'KUULAA', 'xTool', 'KONNWEI', 'Mini OBD2', 'ELMconfig', 'VINT-TT55502'
]

def run_bluetoothctl_and_connect_obd2(timeout=7):
    """
    Scans for a Bluetooth OBD2 device, pairs, trusts, connects to it,
    and stores its MAC address in the global elm_mac variable.
    """
    global elm_mac

    try:
        process = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        def send(cmd, wait=0.5):
            print(f"> {cmd}")
            process.stdin.write(cmd + '\n')
            process.stdin.flush()
            time.sleep(wait)

        send('agent on')
        send('power on')
        send('default-agent')
        send('scan on')
        print("🔍 Scanning for OBD2 devices...")

        start_time = time.time()
        found_mac = None

        while time.time() - start_time < timeout:
            line = process.stdout.readline()
            if not line:
                continue

            print(line.strip())

            match = re.search(r'Device ([0-9A-F:]{17}) (.+)', line.strip(), re.I)
            if match:
                mac, name = match.groups()
                if any(obd_name.lower() in name.lower() for obd_name in OBD2_NAMES):
                    print(f"✅ Found OBD2 device: {name} at {mac}")
                    found_mac = mac
                    break

        send('scan off')

        if not found_mac:
            print("🔄 Trying 'devices' command to check known list...")
            send('devices')
            time.sleep(1)
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                print(line.strip())
                match = re.search(r'Device ([0-9A-F:]{17}) (.+)', line.strip(), re.I)
                if match:
                    mac, name = match.groups()
                    if any(obd_name.lower() in name.lower() for obd_name in OBD2_NAMES):
                        print(f"✅ Found OBD2 in saved devices: {name} at {mac}")
                        found_mac = mac
                        break

        if not found_mac:
            print("❌ No OBD2 device found.")
            process.stdin.close()
            process.terminate()
            return None

        send(f'pair {found_mac}', wait=2)
        send(f'trust {found_mac}')
        send(f'connect {found_mac}', wait=2)

        print(f"✅ OBD2 device {found_mac} paired, trusted, and connected.")

        # Save to global variable
        elm_mac = found_mac

        process.stdin.close()
        process.terminate()
        return found_mac

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    run_bluetoothctl_and_connect_obd2()
    if elm_mac:
        print(f"🔁 Ready to bind: {elm_mac}")