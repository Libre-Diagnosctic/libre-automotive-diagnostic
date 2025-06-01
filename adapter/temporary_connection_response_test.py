#This is for temporary tests to check if we get any responses at all after the connection and initialization

import serial
import time
import re

def parse_supported_pids(hex_string):
    match = re.search(r'4100([0-9A-Fa-f]{8})', hex_string)
    if not match:
        print("⚠️ No valid '4100' response found.")
        return []
    bitfield = match.group(1)
    bin_string = bin(int(bitfield, 16))[2:].zfill(32)

    supported_pids = []
    for i, bit in enumerate(bin_string):
        if bit == '1':
            pid = f"01{(i + 1):02X}"
            supported_pids.append(pid)
    return supported_pids

def parse_rpm_response(text):
    match = re.search(r'41\s?0C\s?([0-9A-Fa-f]{2})\s?([0-9A-Fa-f]{2})', text)
    if match:
        A = int(match.group(1), 16)
        B = int(match.group(2), 16)
        return ((A * 256) + B) // 4
    else:
        print("⚠️ No valid RPM response found.")
        return None

def send_obd_command(port):
    try:
        print(f"🔌 Connecting to {port}...")
        ser = serial.Serial(port, baudrate=38400, timeout=3)
        time.sleep(2)
        ser.reset_input_buffer()

        # Adapter ID
        ser.write(b'ATI\r')
        time.sleep(0.5)
        print("📟 Adapter ID:", ser.read_until(b'>').decode(errors="ignore").strip())

        # Init commands
        init_cmds = ["ATE0", "ATL0", "ATS0", "ATH1", "ATSP3"]
        for cmd in init_cmds:
            ser.write((cmd + '\r').encode())
            time.sleep(0.4)
            print(f"> {cmd} →", ser.read_until(b'>').decode(errors="ignore").strip())

        # Request supported PIDs
        ser.write(b'0100\r')
        time.sleep(0.5)
        raw = ser.read_until(b'>').decode(errors="ignore")
        print(f"\n🧾 Raw Response to 0100:\n{raw.strip()}")

        pids = parse_supported_pids(raw)
        print(f"\n✅ Supported PIDs:\n{pids}")

        # If RPM supported
        if "010C" in pids:
            ser.write(b'010C\r')
            time.sleep(0.5)
            buffer = ser.read_until(b'>')
            print(f"\n🌀 Raw RPM Response Bytes:\n{buffer}")
            decoded = buffer.decode(errors="ignore")
            print(f"\n🌀 Decoded RPM Response:\n{decoded.strip()}")

            rpm = parse_rpm_response(decoded)
            if rpm is not None:
                print(f"\n✅ Parsed RPM: {rpm} RPM")
        else:
            print("❌ RPM PID (010C) not supported.")

        ser.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_obd_command("/dev/rfcomm0")