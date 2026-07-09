/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: main.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 1.0.0
 */

#include <stdio.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <stdlib.h>
#include "obd_ioctl.h"
#include "custom_isotp.h"

int main() {
    int drv_fd = open("/dev/obd_data", O_RDWR);
    if (drv_fd < 0) { perror("Driver missing"); return 1; }

    int iso_fd = isotp_open("can0", 0x7DF, 0x7E8);
    obd_data_t live;

    // 1. Поиск на RPM през драйвера
    int pid = 0x0C;
    ioctl(drv_fd, SET_PID, &pid);
    if (read(drv_fd, &live, sizeof(live)) > 0) {
        printf("{\n  \"rpm\": %d,\n", live.rpm);
    }

    // 2. Четене на грешки през ISO-TP (Mode 03)
    uint8_t req[] = {0x03};
    write(iso_fd, req, 1);
    uint8_t res[64];
    int len = read(iso_fd, res, sizeof(res));

    printf("  \"errors\": [");
    for (int i = 1; i + 1 < len; i += 2) {
        printf("\"P%02X%02X\"%s", res[i], res[i+1], (i+3 < len) ? "," : "");
    }
    printf("]\n}\n");

    close(iso_fd); close(drv_fd);
    return 0;
}
