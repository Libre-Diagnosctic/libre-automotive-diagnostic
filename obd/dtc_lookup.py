import serial
import time
import re
import json
import pathlib
from typing import List, Dict

# -----------------------------------------------------------
#  Load the generic DTC lookup table once at import‑time
# -----------------------------------------------------------
ASSET_FILE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "dtc_db.json"
try:
    with ASSET_FILE.open(encoding="utf-8") as f:
        DTC_DB = json.load(f)
except FileNotFoundError:
    print(f"Warning: DTC database file not found: {ASSET_FILE}")
    DTC_DB = {}

# -----------------------------------------------------------
#  Main handler class
# -----------------------------------------------------------
class DTCHandler:
    def __init__(self, port: str = "/dev/rfcomm0", baudrate: int = 38400, timeout: int = 3):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    # ---------------- Serial helpers ----------------
    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout)
            time.sleep(2)
            self.ser.reset_input_buffer()
            for cmd in ("ATE0", "ATL0", "ATS0", "ATH1", "ATSP3"):
                self.send_command(cmd)
            return True
        except Exception as exc:
            print(f"Connection failed: {exc}")
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_command(self, cmd: str) -> str:
        if not self.ser:
            return ""
        self.ser.write((cmd + "\r").encode())
        time.sleep(0.4)
        return self.ser.read_until(b">").decode(errors="ignore")

    # ---------------- Public API ----------------
    def read_dtc(self) -> List[Dict[str, str]]:
        raw = self.send_command("03")
        return self._parse_dtcs(raw)

    def clear_dtc(self) -> bool:
        raw = self.send_command("04")
        return "Cleared" in raw or "OK" in raw

    # ---------------- Internal helpers ----------------
    def _parse_dtcs(self, response: str) -> List[Dict[str, str]]:
        """Return list like [{'code': 'P0301', 'desc': 'Cylinder 1 Misfire Detected'}, …]"""
        dtc_list = []
        hex_stream = "".join(
            ln.strip().replace(" ", "") for ln in response.replace("\r", "").split("\n") if ln.startswith("43")
        )
        if not hex_stream:
            return []

        payload = hex_stream[2:]  # drop 43
        for i in range(0, len(payload), 4):
            chunk = payload[i : i + 4]
            if len(chunk) < 4 or chunk == "0000":
                continue
            code = self._decode_dtc(chunk)
            if code:
                dtc_list.append(
                    {
                        "code": code,
                        "desc": DTC_DB.get(code, "Manufacturer‑specific or undocumented")
                    }
                )
        return dtc_list

    @staticmethod
    def _decode_dtc(nibbles: str) -> str:
        if len(nibbles) != 4:
            return ""
        first = int(nibbles[0], 16)
        prefix = ["P", "C", "B", "U"][(first & 0xC) >> 2]
        return f"{prefix}{first & 0x3}{nibbles[1:]}"

# -----------------------------------------------------------
#  Quick CLI test
# -----------------------------------------------------------
if __name__ == "__main__":
    handler = DTCHandler()
    if handler.connect():
        results = handler.read_dtc()
        if results:
            print("\nStored DTCs:")
            for item in results:
                print(f"  {item['code']}: {item['desc']}")
        else:
            print("\nNo DTCs found.")
        handler.disconnect()
