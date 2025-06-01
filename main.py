from adapter import connection, initialization

def main():
    print("🚗 Libre Diagnostic: ELM327 Bluetooth Setup\n")

    # Step 1: Scan and connect to ELM327 OBD2 device
    print("🔍 Step 1: Scanning and connecting to OBD2 device...")
    connection.run_bluetoothctl_and_connect_obd2()

    # Step 2: Check if MAC address was found
    if connection.elm_mac:
        print(f"✅ ELM327 device found at: {connection.elm_mac}")

        # Step 3: Bind the MAC address via rfcomm
        print("\n🔧 Step 2: Binding ELM327 to /dev/rfcomm0...")
        initialization.run_rfcomm_binding(connection.elm_mac)

        print("\n✅ Setup complete. You can now communicate with the device at /dev/rfcomm0.")
    else:
        print("❌ No ELM327 device was found. Please ensure it's powered on and try again.")

if __name__ == "__main__":
    main()
