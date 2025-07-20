# Live Data Fetcher for GUI Integration
import serial
import time
import re
from utils.log_manager import save_session, logging

#PID Parsing Helpers

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
    return None

def parse_speed_response(text):
    match = re.search(r'41\s?0D\s?([0-9A-Fa-f]{2})', text)
    if match:
        return int(match.group(1), 16)
    return None

def parse_temp_response(text):
    match = re.search(r'41\s?[0-5][0-9A-Fa-f]\s?([0-9A-Fa-f]{2})', text)
    if match:
        return int(match.group(1), 16) - 40
    return None

def parse_throttle_response(text):
    match = re.search(r'41\s?11\s?([0-9A-Fa-f]{2})', text)
    if match:
        return (int(match.group(1), 16) * 100) / 255
    return None

def parse_maf_response(text):
    match = re.search(r'41\s?10\s?([0-9A-Fa-f]{2})\s?([0-9A-Fa-f]{2})', text)
    if match:
        A = int(match.group(1), 16)
        B = int(match.group(2), 16)
        return ((A * 256) + B) / 100.0
    return None

def parse_fuel_pressure_response(text):
    match = re.search(r'41\s?0A\s?([0-9A-Fa-f]{2})', text)
    if match:
        return int(match.group(1), 16) * 3
    return None

def parse_o2_sensor_response(text):
    match = re.search(r'41\s?14\s?([0-9A-Fa-f]{2})', text)
    if match:
        return int(match.group(1), 16) / 200.0
    return None

# --- Main Function ---

def fetch_live_data(port):
    data = {
        "RPM": None,
        "Vehicle Speed": None,
        "Coolant Temp": None,
        "Throttle Position": None,
        "Intake Temp": None,
        "MAF Rate": None,
        "Fuel Pressure": None,
        "O2 Sensor (Bank 1)": None
    }

    try:
        print(f"🔌 Connecting to {port}...")
        ser = serial.Serial(port, baudrate=38400, timeout=3)
        time.sleep(2)
        ser.reset_input_buffer()

        # Init commands
        init_cmds = ["ATE0", "ATL0", "ATS0", "ATH1", "ATSP3"]
        for cmd in init_cmds:
            ser.write((cmd + '\r').encode())
            time.sleep(0.4)
            ser.read_until(b'>')

        # Check supported PIDs
        ser.write(b'0100\r')
        time.sleep(0.5)
        raw = ser.read_until(b'>').decode(errors="ignore")
        supported_pids = parse_supported_pids(raw)
        print(f"✅ Supported PIDs: {supported_pids}")

        # Define PID map
        pid_map = {
            "RPM": ("010C", parse_rpm_response),
            "Vehicle Speed": ("010D", parse_speed_response),
            "Coolant Temp": ("0105", parse_temp_response),
            "Throttle Position": ("0111", parse_throttle_response),
            "Intake Temp": ("010F", parse_temp_response),
            "MAF Rate": ("0110", parse_maf_response),
            "Fuel Pressure": ("010A", parse_fuel_pressure_response),
            "O2 Sensor (Bank 1)": ("0114", parse_o2_sensor_response)
        }

        # Request each data point
        for label, (pid_cmd, parser) in pid_map.items():
            if pid_cmd in supported_pids:
                print(f"\n➡️ Requesting {label} ({pid_cmd})...")
                ser.write((pid_cmd + '\r').encode())
                time.sleep(0.5)
                raw_response = ser.read_until(b'>').decode(errors="ignore")
                print(f"🔍 Raw response for {label}:\n{raw_response.strip()}")

                value = parser(raw_response)
                if value is not None:
                    print(f"✅ {label}: {value}")
                    data[label] = value
                else:
                    print(f"⚠️ Car does not support this or invalid response: {label}")
            else:
                print(f"❌ {label} ({pid_cmd}) not supported.")

        ser.close()

    except Exception as e:
        print(f"❌ Error: {e}")

    save_session(data, None)
    return data

# Example run
if __name__ == "__main__":
    result = fetch_live_data("/dev/rfcomm0")
    print("\n=== Final Results ===")
    for key, val in result.items():
        print(f"{key}: {val}")
