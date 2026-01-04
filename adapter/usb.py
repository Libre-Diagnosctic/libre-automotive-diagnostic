import errno
import pyudev
import serial

KNOW_USB_OBD2_READERS = {
    "Prolific Technology Inc PL2303": {
            "udev_attrs": {"subsystem": "tty", "ID_VENDOR_ID":"067b", "ID_MODEL_ID": "2303"},
            "baud_rate": 9600
        }
    }

def search_compatible_usb_device():
    print("🔍 Scanning for USB connected OBD2 devices...")
    result = None, None
    for name,v in KNOW_USB_OBD2_READERS.items():
        for device in pyudev.Context().list_devices(**v["udev_attrs"]):
            print(f"✅ Found USB OBD2 device '{name}' at {device.device_node}")
            result = (device.device_node, v["baud_rate"])

    if result[0] is None:
        msg = "No supported USB OBD2 device found."
    else:
        try:
            serial.Serial(port=result[0], baudrate=result[1], timeout=1)
            return result
        except serial.SerialException as e:
            msg = f"Could not open serial port '{result[0]}': {e}"
            if e.errno == errno.EBUSY:
                msg = f"Device is busy! Make sure no other application is blocking port: {result[0]}"
        except Exception as e:
            msg = f"{e}"
    print("❌ Error:", msg)
    return None, msg

if __name__ == "__main__":
    search_compatible_usb_device()
