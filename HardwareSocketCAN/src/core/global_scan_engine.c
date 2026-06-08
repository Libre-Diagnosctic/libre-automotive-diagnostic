/**
 * @file src/core/global_scan_engine.c
 * @brief Auto-Scan Engine (Health report за абсолютно всички ECU модули)
 * @details Изпълнява паралелно извеждане на топологията на автомобила, извличане на VIN и четене на DTC.
 * Стандарти: ISO 14229 (UDS), SAE J1979.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/iso_tp_stack.h"
#include "../../lib/uds_iso14229.h"

#define SCAN_START_ID 0x7E0
#define SCAN_END_ID   0x7EF
#define SCAN_TIMEOUT_US 20000 /* 20ms закъснение между заявките */

/**
 * @brief Структура за съхранение на открит възел (ECU)
 */
typedef struct {
    uint32_t tx_id;
    uint32_t rx_id;
    char     name[32];
    uint16_t dtc_count;
    bool     is_active;
} ecu_node_t;

static ecu_node_t ecu_inventory[16];
static uint8_t discovered_count = 0;

/**
 * @brief Автоматично сканиране на шината за активни контролери
 * @param shm Указател към споделената памет за обновяване на статуса
 */
void run_global_scan(automotive_data_t *shm) {
    printf("[SCAN] Starting Global Health Scan...\n");
    discovered_count = 0;
    shm->error_count = 0;

    for (uint32_t id = SCAN_START_ID; id <= SCAN_END_ID; id++) {
        uint32_t target_rx = id + 0x08;
        int fd = isotp_stack_init("can0", id, target_rx);
        
        if (fd < 0) continue;

        /* 1. Пинг през UDS Tester Present (Service 0x3E) */
        if (uds_tester_present(fd, false) > 0) {
            ecu_inventory[discovered_count].tx_id = id;
            ecu_inventory[discovered_count].rx_id = target_rx;
            ecu_inventory[discovered_count].is_active = true;

            /* 2. Четене на VIN (DID 0xF190) за идентификация */
            uds_read_data_by_id(fd, 0xF190);
            uint8_t rx_buf[256];
            int vin_len = isotp_stack_receive(fd, rx_buf, sizeof(rx_buf));
            if (vin_len > 0) {
                // Логика за запис на VIN в глобалната структура
            }

            /* 3. Четене на брой DTC (Service 0x19 0x01) */
            uint8_t dtc_req[] = {0x19, 0x01, 0x08}; // Report Number of DTC by Status Mask (Confirmed)
            isotp_stack_send(fd, dtc_req, 3);
            
            int dtc_res_len = isotp_stack_receive(fd, rx_buf, sizeof(rx_buf));
            if (dtc_res_len >= 6 && rx_buf[0] == 0x59) {
                uint16_t count = (rx_buf[4] << 8) | rx_buf[5];
                ecu_inventory[discovered_count].dtc_count = count;
                shm->error_count += count;
            }

            printf("[SCAN] Found ECU at 0x%03X | DTCs: %d\n", id, ecu_inventory[discovered_count].dtc_count);
            discovered_count++;
        }

        isotp_stack_close(fd);
        usleep(SCAN_TIMEOUT_US);
    }

    /* Обновяване на общия статус в SHM */
    shm->system_ticks++;
    printf("[SCAN] Global Scan Finished. Total ECU found: %d. Total DTCs: %d\n", 
           discovered_count, shm->error_count);
}

/**
 * @brief Wrapper нишка за периодичен Global Scan
 */
void *global_scan_engine_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;
    
    while (1) {
        /* Сканирането се тригерира при нужда или на големи интервали */
        run_global_scan(shm);
        sleep(60); /* Пълно сканиране на всяка минута */
    }
    return NULL;
}

/* Край на файл global_scan_engine.c */
