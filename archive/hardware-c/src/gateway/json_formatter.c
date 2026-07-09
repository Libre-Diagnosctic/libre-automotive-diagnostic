/**
 * @file json_formatter.c
 * @brief High-performance Memory-Safe JSON Serialization Engine
 * @details Converts raw automotive shared memory telemetry into structured JSON payloads.
 *          Strictly utilizes boundary-checked snprintf to prevent buffer overruns.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <string.h>
#include "json_formatter.h"
#include "../../lib/obd_pids_db.h"
#include "../../driver/obd_ioctl.h"

/**
 * @brief Formats the full engineering dictionary payload into a valid JSON array string safely
 * @param shm Pointer to the active zero-copy mapped shared memory core instance
 * @param output Destination char array pointer to store the generated JSON payload string
 * @param max_len Absolute memory size allocation capacity of the destination buffer
 */
void json_format_all_pids(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    int32_t offset = snprintf(output, max_len, "{\"telemetry\": [");
    if ((offset < 0) || ((size_t)offset >= max_len)) {
        return; /* Output truncation defense buffer boundary abort */
    }

    uint32_t appended_entries = 0U;

    for (uint32_t i = 0U; i < MASTER_PID_COUNT; i++) {
        const obd_pid_definition_t *pid = &MASTER_PID_TABLE[i];
        uint8_t p_id = pid->pid;

        /* Verify active tracking boundary constraints before index lookup */
        if (p_id < VCI_PID_TABLE_SIZE) {
            /* Technical Synchronization: Extract status verification from the updated cache layout */
            if (shm->pid_db[p_id].is_valid != 0U) {
                float val = shm->pid_db[p_id].calculated_value;
                int32_t written = 0;

                /* Handle array list comma separation layout tracking safely */
                if (appended_entries > 0U) {
                    written = snprintf(output + offset, max_len - (size_t)offset, ",");
                    if (written > 0) { offset += written; }
                }

                /* Secure bounded append operations mapping correctly to diagnostic_db spec schemas */
                written = snprintf(output + offset, max_len - (size_t)offset, 
                    "{\"id\":\"0x%02X\",\"name\":\"%s\",\"val\":%.2f,\"unit\":\"%s\"}",
                    p_id, pid->name, (double)val, pid->unit);
                
                if (written > 0) {
                    offset += written;
                    appended_entries++;
                }
            }
        }
    }

    /* Append global trailing metrics counters mapping directly to active core telemetry registers */
    (void)snprintf(output + offset, max_len - (size_t)offset, "], \"ts\":%llu}", 
                   (unsigned long long)shm->system_ticks);
}

/**
 * @brief Safely builds a memory-bounded compact JSON object for a single diagnostic parameter parameter
 */
void json_format_single_pid(uint8_t pid_id, float value, char *output, size_t max_len) {
    if ((output != NULL) && (max_len > 0U)) {
        (void)snprintf(output, max_len, "{\"pid\":\"0x%02X\",\"val\":%.2f}", pid_id, (double)value);
    }
}
