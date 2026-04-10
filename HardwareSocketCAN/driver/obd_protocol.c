/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: obd_protocol.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 1.0.0
 */

#include <linux/types.h>
#include "obd_ioctl.h"

void scale_obd_data(int pid, u8 *data, obd_data_t *shared) {
    switch (pid) {
        case 0x0C: // RPM: ((A*256)+B)/4
            shared->rpm = ((data[3] << 8) | data[4]) / 4;
            break;
        case 0x0D: // Speed: A
            shared->speed = data[3];
            break;
        case 0x05: // Temp: A - 40
            shared->temp = (int)data[3] - 40;
            break;
    }
}

