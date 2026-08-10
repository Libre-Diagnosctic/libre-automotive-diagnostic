/**
 * @file src/core/global_scan_engine.c
 * @brief Auto-Scan Engine (Health report за абсолютно всички ECU модули)
 * @details Изпълнява паралелно извеждане на топологията на автомобила, извличане на VIN и четене на DTC.
 * Стандарти: ISO 14229 (UDS), SAE J1979.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/iso_tp_stack.h"
#include "../../lib/uds_iso14229.h"
#include "../../lib/logging.h"
#include "../../lib/config_loader.h"
#include "global_scan_engine.h"

#define SCAN_START_ID 0x7E0
#define SCAN_END_ID   0x7EF
#define SCAN_TIMEOUT_US 20000 /* 20ms закъснение между заявките */
#define SCAN_CONFIG_PATH_DEFAULT "/etc/kobd/obd.conf"

/**
 * @brief Автоматично сканиране на шината за активни контролери
 * @param shm Указател към споделената памет за обновяване на статуса
 */
void run_global_scan(automotive_data_t *shm) {
    if (shm == NULL) {
        return;
    }

    LOG_INFO("SCAN", "Starting Global Health Scan...");
    shm->status_mask |= VCI_STAT_SCANNING;
    shm->error_count = 0U;

    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, SCAN_CONFIG_PATH_DEFAULT);
    const char *iface = config_get_string(&config, "can", "interface", "can0");

    uint8_t discovered_count = 0U;
    /* Index 0 is owned by the telemetry engine (primary engine ECU + WWH VIN). */
    const uint8_t scan_base = 1U;

    for (uint32_t id = SCAN_START_ID; id <= SCAN_END_ID; id++) {
        if (id == 0x7E0U) {
            /* Reserved for the telemetry engine's primary channel */
            continue;
        }
        uint32_t target_rx = id + 0x08;
        int fd = isotp_stack_init(iface, id, target_rx);

        if (fd < 0) {
            continue;
        }

        /* 1. Пинг през UDS Tester Present (Service 0x3E) */
        if (uds_tester_present(fd, false) >= 0) {
            if ((scan_base + discovered_count) >= VCI_MAX_ECU_NODES) {
                isotp_stack_close(fd);
                break;
            }

            vci_ecu_node_t *node = &shm->ecu_nodes[scan_base + discovered_count];
            (void)memset(node, 0, sizeof(vci_ecu_node_t));
            node->tx_id = id;
            node->rx_id = target_rx;
            node->is_active = 1U;
            node->protocol_flags |= 0x01U; /* Bit0 = UDS */
            (void)snprintf(node->name, sizeof(node->name), "ECU @ 0x%03X", (unsigned)id);

            /* 2. Четене на VIN (DID 0xF190) за идентификация */
            uint8_t rx_buf[256];
            int vin_len = uds_read_data_by_id(fd, 0xF190, rx_buf, (uint16_t)sizeof(rx_buf));
            if (vin_len >= 4) {
                uint16_t vlen = (uint16_t)(vin_len - 3);
                if (vlen > (VCI_VIN_LEN - 1U)) {
                    vlen = VCI_VIN_LEN - 1U;
                }
                (void)memcpy(node->vin, &rx_buf[3], vlen);
                node->vin[vlen] = '\0';
            }

            /* 3. Четене на брой DTC (Service 0x19 0x01) */
            uint8_t dtc_req[] = {0x19U, 0x01U, 0x08U}; /* Report DTC count (Confirmed) */
            (void)isotp_stack_send(fd, dtc_req, (uint16_t)sizeof(dtc_req));

            int dtc_res_len = isotp_stack_receive(fd, rx_buf, (uint16_t)sizeof(rx_buf));
            if ((dtc_res_len >= 6) && (rx_buf[0] == 0x59U)) {
                uint16_t count = (uint16_t)((rx_buf[4] << 8) | rx_buf[5]);
                node->dtc_count = count;
                shm->error_count += count;
            }

            LOG_INFO("SCAN", "Found ECU at 0x%03X | DTCs: %u", (unsigned)id,
                     (unsigned)node->dtc_count);
            discovered_count++;
        }

        isotp_stack_close(fd);
        usleep(SCAN_TIMEOUT_US);
    }

    shm->ecu_count = (uint8_t)(scan_base + discovered_count);
    shm->status_mask &= ~VCI_STAT_SCANNING;
    shm->system_ticks++;
    LOG_INFO("SCAN", "Global Scan Finished. Total ECU found: %u. Total DTCs: %u",
             (unsigned)discovered_count, (unsigned)shm->error_count);
}

/**
 * @brief Wrapper нишка за периодичен Global Scan
 */
void *global_scan_engine_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;

    /* Initial topology sweep on startup */
    run_global_scan(shm);

    while (1) {
        sleep(60); /* Пълно сканиране на всяка минута */
        run_global_scan(shm);
    }
    return NULL;
}

/* Край на файл global_scan_engine.c */
