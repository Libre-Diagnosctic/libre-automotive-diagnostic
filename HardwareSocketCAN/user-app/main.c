/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: main.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 2.0.0
 * UPDATE: User-space reference application demonstrating the full stack:
 *         raw SocketCAN -> ISO-TP (15765-2) -> UDS (14229-1) -> PID cache
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../lib/iso_tp_stack.h"
#include "../lib/uds_iso14229.h"
#include "../lib/obd_pids_db.h"
#include "../driver/obd_ioctl.h"

#define OBD_ENGINE_ECU_TX 0x7E0U
#define OBD_ENGINE_ECU_RX 0x7E8U

/**
 * @brief Polls a Mode 01 PID through the ISO-TP/UDS stack and prints the value
 */
static int32_t user_app_poll_pid(int32_t handle, uint8_t pid) {
    uint8_t request[2] = { 0x01U, pid };
    uint8_t response[32];

    if (isotp_stack_send(handle, request, (uint16_t)sizeof(request)) <= 0) {
        return -1;
    }

    int32_t len = isotp_stack_receive(handle, response, (uint16_t)sizeof(response));
    if (len <= 0) {
        return -2;
    }
    if (response[0] == 0x7FU) {
        fprintf(stderr, "[USER-APP] Negative response NRC=0x%02X for PID 0x%02X\n",
                response[2], pid);
        return -3;
    }
    if ((response[0] != 0x41U) || (response[1] != pid)) {
        return -4;
    }

    const obd_pid_definition_t *def = obd_pid_find(0x01U, pid);
    if (def == NULL) {
        printf("  PID 0x%02X: raw bytes [", pid);
        for (int i = 2; i < len; i++) printf("%02X ", response[i]);
        printf("]\n");
        return 0;
    }

    float value = 0.0f;
    if (def->formula != NULL) {
        value = def->formula(&response[2], (uint8_t)(len - 2));
    }
    printf("  %s: %.2f %s\n", def->name, (double)value,
           (def->unit != NULL) ? def->unit : "");
    return 0;
}

int main(void) {
    printf("K-OBD-PI User Application v2.0.0\n");

    int32_t handle = isotp_stack_init("can0", OBD_ENGINE_ECU_TX, OBD_ENGINE_ECU_RX);
    if (handle < 0) {
        fprintf(stderr, "[USER-APP] Cannot open ISO-TP channel. Is can0 up?\n");
        return EXIT_FAILURE;
    }

    printf("[USER-APP] ISO-TP channel active. Entering Extended Session...\n");
    if (uds_set_session(handle, UDS_SESSION_EXTENDED) < 0) {
        fprintf(stderr, "[USER-APP] Extended session rejected - continuing anyway.\n");
    }

    printf("[USER-APP] Live sensor snapshot:\n");
    static const uint8_t demo_pids[] = { 0x0CU, 0x0DU, 0x05U, 0x11U, 0x0FU, 0x42U };
    for (uint32_t i = 0U; i < sizeof(demo_pids); i++) {
        (void)user_app_poll_pid(handle, demo_pids[i]);
    }

    /* Diagnostic Trouble Codes snapshot (Mode 03) */
    uint8_t dtc_req[1] = { 0x03U };
    uint8_t dtc_res[64];
    if (isotp_stack_send(handle, dtc_req, 1U) > 0) {
        int32_t len = isotp_stack_receive(handle, dtc_res, (uint16_t)sizeof(dtc_res));
        if ((len >= 2) && (dtc_res[0] == 0x43U)) {
            uint32_t count = (len - 2) / 2U;
            printf("[USER-APP] DTCs: %u\n", count);
        } else {
            printf("[USER-APP] No DTCs stored.\n");
        }
    }

    isotp_stack_close(handle);
    printf("[USER-APP] Session closed. Bye.\n");
    return EXIT_SUCCESS;
}
