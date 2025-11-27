# libre-automotive-diagnostic

## An open-source automotive diagnostic tool using ELM327, supporting OBD2, DTCs, and brand-specific commands.

## 🔧 Linux installation (standalone binary)

Libre Diagnostic can be run as a standalone executable on Linux without installing Python or extra dependencies.

1. Go to the **Releases** section of this repository and download  
   `libre-diagnostic-linux-x86_64.tar.gz`.

2. Extract the archive:

   ```bash
   tar xzf libre-diagnostic-linux-x86_64-v0.2.0.tar.gz

3. Make sure the binary is executable

   ```bash
   chmod +x libre-diagnostic

4. Run it

   ```bash
   ./libre-diagnostic

### ⚠️ Disclaimer of Liability

Libre Diagnostic is provided as an open-source software project intended for educational and diagnostic purposes only. While we aim to ensure the reliability and safety of this tool, use of this software is at your own risk.

By using this application, you acknowledge and agree that:

- The developers, contributors, or maintainers of Libre Diagnostic are not responsible for any direct or indirect damage, including but not limited to malfunction, data corruption, ECU issues, or physical damage caused to your vehicle or connected devices.
- This tool interacts with sensitive automotive systems. Improper use or unsupported diagnostic commands may lead to unintended consequences.
- You should never use this tool while driving or in a hazardous environment.
- You are solely responsible for verifying the compatibility of this tool with your vehicle, adapter, and operating system before use.

If you are unsure about any diagnostic command or result, consult with a professional mechanic before taking further action.

### 🔐 Privacy & GDPR Compliance

Libre Diagnostic is built with user privacy and data minimisation in mind:

- The application does not collect, transmit, or store any personal data.
- No telemetry, analytics, or background reporting tools are implemented.
- Diagnostic session data (such as vehicle PIDs, DTCs, and logs) is only available locally and temporarily within your current session.
- Users may choose to export logs manually as plain text files, which are not stored or transmitted by the application.
- No VIN, ECU ID, or any identifier is retained or shared beyond your local machine.

In accordance with the principles of the General Data Protection Regulation (GDPR), this tool does not process any personal data unless voluntarily and explicitly exported by the user for their own use.

### 🔄 Contributions and Third-Party Code

Libre Diagnostic may incorporate third-party open-source components or libraries where necessary. Each component remains subject to its own license, and attribution is provided where required. Use of any third-party library does not imply endorsement or liability from its respective author(s).

## Useful Links for Project Background

- [Project Website]()
- [Technical Feasibility Report](https://librediagnostic.com/wp-content/uploads/2025/04/Libre-Diagnostic-Technical-Feasibility-Report.pdf)
- [DTC & Diagnostic Standards Report](https://librediagnostic.com/wp-content/uploads/2025/04/Libre-Diagnostic-DTC-Diagnostic-Standards-Report.pdf)
- [Requirements & System Design](https://librediagnostic.com/wp-content/uploads/2025/05/Libre-Diagnostic-Requirements-and-System-Design.pdf)

## System Limitations and Future Improvements
### Current System Limitations
Protocol and Vehicle Coverage Limitations

Libre Diagnostic communicates through standard OBD2 protocols using ELM327 hardware. Current limitations include:

- Limited support for non standard manufacturer protocols
- Partial support for vehicles requiring proprietary Mode 22 PIDs
- Timing adjustments for older European vehicles not automated yet
- Some ELM327 clones return incomplete or malformed responses
- CAN based vehicles expose only standard PIDs without extended brand specific data

Hardware Limitations

- Strong dependency on ELM327 Bluetooth devices
- Variable clone quality affects stability
- Unstable or delayed communication due to inconsistent baud rates
- No support yet for USB or Wi Fi adapters
- No validation or compatibility checks for STN based devices

Software Architecture Constraints

- GUI operations are single threaded which affects responsiveness
- Serial communication uses synchronous operations
- Linux is the primary supported system
- Some modules need refactoring for improved modularity and maintainability

Diagnostic Capability Limitations

- Limited Mode 22 brand specific PID libraries
- Freeze frame decoding not implemented
- Readiness monitor reporting not currently supported

GUI Limitations

- Limited styling and theming
- No dark or light mode
- Layout responsiveness is limited

Session and Data Logging Limitations

- Session logs contain minimal metadata
- No encryption or protection for saved sessions
- No long term vehicle profile storage
- Export options are basic and require manual file handling

Repository and Code Quality Limitations

- Limited automated testing

### Known Edge Cases

- Bluetooth connection drop on low quality adapters
- Protocol auto detection may select the wrong protocol in rare cases
- Mode 22 behaviour is inconsistent between manufacturers
- Vehicles with multiple ECUs may need custom initialisation sequences

### Security Considerations

- Clone adapters may use outdated or insecure firmware
- Diagnostic logs may include identifiable information
- No encryption for local saved data
- Future IoT server components will require secure authentication and encryption

## Future Improvements
### Adapter and Protocol Enhancements

- Complete refactor of the ELM327 driver
- Automatic baud rate negotiation
- More stable reconnection and fallback logic
- Adaptive polling frequency
- Broader support for manufacturer specific protocols
- Optional support for STN based adapters

### Diagnostic Feature Expansion

- Freeze frame analysis
- OBD readiness monitor reporting
- Expanded PID libraries for BMW, Volkswagen, Renault, Toyota and others
- Enhanced real time graphs and dashboard widgets
- Advanced DTC metadata

### Performance Improvements

- Multi threaded polling and data handling
- Improved buffering and error recovery
- Better handling of malformed adapter responses

### GUI Improvements

- Theme support including dark and light mode
- Improved layout scaling
- Better accessibility
- Custom user dashboards and dynamic widgets

### Data Handling and Logging

- Encrypted log files
- Vehicle profiles with VIN decoding and stored history
- Standardised diagnostic report format

### Documentation and Developer Experience

- Code examples and tutorials
- Expanded automated test coverage

## Platform Expansion

(Planned improvements depending on funding and further development)

- A dedicated Android app is planned. It will support diagnostics without a laptop, real time graphing, enhanced PIDs, session saving and synchronisation with the IoT server.
- A standalone IoT server is planned. It will enable:
   - Remote diagnostics
   - Real time vehicle data streaming
   - Secure storage of diagnostic sessions
   - Fleet monitoring features
   - Reduced dependency on ELM327 devices
   - Support for modern automotive hardware

The long term goal is to allow Libre Diagnostic to run with advanced IoT hardware rather than relying solely on consumer grade adapters.

## Long Term Vision

Libre Diagnostic aims to evolve into a complete diagnostic ecosystem.

- Community maintained Mode 22 and PID expansions
- Modular plugin architecture
- IoT enabled fleet diagnostics
- Strong documentation and contributor focused development
- Support for advanced automotive hardware

## Conclusion

Libre Diagnostic is a stable and actively developed diagnostic tool. This section outlines current limitations and the roadmap for future enhancements. The project continues to grow with the goal of becoming an accessible, reliable and fully open diagnostic platform for both everyday users and developers. Contributions and ideas are welcome through the GitHub repository.
