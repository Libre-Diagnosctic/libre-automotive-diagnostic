/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: main.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 2.0.0
 * UPDATE: Migrated to lib/iso_tp_stack + lib/uds_iso14229 (ISO 15765-2 / 14229-1)
 */

#include <stdio.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <stdlib.h>
#include <string.h>
#include "driver/obd_ioctl.h"
#include "lib/iso_tp_stack.h"
#include "lib/uds_iso14229.h"

/**
 * @brief Formats a 2-byte Mode 03 DTC code into "P0xxx" style string
 */
static void format_dtc(uint8_t hi, uint8_t lo, char *out, size_t cap) {
    char cls = 'P';
    switch (hi >> 6) {
        case 1: cls = 'C'; break;
        case 2: cls = 'B'; break;
        case 3: cls = 'U'; break;
        default: cls = 'P'; break;
    }
    (void)snprintf(out, cap, "%c%02X%02X", cls, hi & 0x3FU, lo);
}

int main(void) {
    int drv_fd = open("/dev/obd_data", O_RDWR);
    if (drv_fd < 0) { perror("Driver missing"); return 1; }

    int32_t iso_fd = isotp_stack_init("can0", 0x7DF, 0x7E8);
    if (iso_fd < 0) {
        fprintf(stderr, "ISO-TP channel init failed.\n");
        close(drv_fd);
        return 2;
    }
    obd_data_t live;

    /* 1. Поиск на RPM през драйвера */
    int pid = 0x0C;
    (void)ioctl(drv_fd, SET_PID, &pid);
    if (read(drv_fd, &live, sizeof(live)) > 0) {
        printf("{\n  \"rpm\": %d,\n", live.rpm);
    }

    /* 2. Четене на грешки през ISO-TP (Mode 03) */
    uint8_t req[] = {0x03};
    uint8_t res[64];
    int len = 0;
    if (isotp_stack_send(iso_fd, req, (uint16_t)sizeof(req)) > 0) {
        len = isotp_stack_receive(iso_fd, res, (uint16_t)sizeof(res));
    }

    printf("  \"errors\": [");
    for (int i = 1; (i + 1) < len; i += 2) {
        char code[16];
        format_dtc(res[i], res[i + 1], code, sizeof(code));
        printf("\"%s\"%s", code, ((i + 3) < len) ? "," : "");
    }
    printf("]\n}\n");

    /* 3. Проверка за UDS отрицателен отговор на директна заявка (Mode 01 PID 0) */
    uint8_t pids_req[2] = {0x01, 0x00};
    if (isotp_stack_send(iso_fd, pids_req, 2) > 0) {
        int rlen = isotp_stack_receive(iso_fd, res, (uint16_t)sizeof(res));
        if (rlen >= 3 && res[0] == 0x41 && res[1] == 0x00) {
            printf("  \"supported_pids\": \"0x%02X%02X%02X%02X\"\n",
                   res[2], res[3], res[4], res[5]);
        }
    }

    isotp_stack_close(iso_fd);
    close(drv_fd);
    return 0;
}
