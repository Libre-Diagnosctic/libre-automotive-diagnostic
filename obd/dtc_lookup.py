"""
==============================================================================
Project:        Libre Diagnostic Tool
File:           obd_interface.py
Author:         Tayana Mileva
Created:        2025-07-02
Last Updated:   2025-07-02
Description:
    This module handles the core communication logic between the Python
    diagnostic GUI and the ELM327 OBD2 Bluetooth adapter. It is responsible
    for initializing the connection, negotiating protocols, sending AT and
    OBD-II commands, and parsing the raw responses into meaningful
    automotive telemetry data.

    The supported features include:
        - Protocol detection (e.g., ISO 9141-2, CAN, etc.)
        - Real-time data reading (RPM, speed, throttle position, etc.)
        - Trouble code reading and clearing (mode 03 and 04)
        - Support for simulation mode and custom test datasets
        - Error detection and failover handling
        - Debug logging for development use

Usage:
    This file is meant to be imported as a module. Do not run directly.
    To integrate it into the GUI application, instantiate the `OBDInterface`
    class and use its methods to retrieve data or send commands.

    Example:
        from obd_interface import OBDInterface

        obd = OBDInterface(port="/dev/rfcomm0")
        rpm = obd.get_rpm()
        print("Current RPM:", rpm)

Notes:
    - Ensure Bluetooth permissions are correctly set on the host OS.
    - Some vehicles (e.g., pre-2000) may have limited PID support.
    - For simulation mode, refer to `simulator/simulator_data.py`.

License:
    MIT License

    Copyright (c) 2025 Tayana Mileva

    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject
    to the following conditions:

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
==============================================================================
"""
