/**
 * @file src/gateway/json_formatter.c
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

void json_format_all_pids(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    int32_t offset = snprintf(output, max_len, "{\"telemetry\": [");
    if ((offset < 0) || ((size_t)offset >= max_len)) {
        return;
    }

    uint32_t appended_entries = 0U;

    for (uint32_t i = 0U; i < MASTER_PID_COUNT; i++) {
        const obd_pid_definition_t *pid = &MASTER_PID_TABLE[i];
        uint8_t p_id = pid->pid;

        if (p_id < VCI_PID_TABLE_SIZE) {
            if (shm->pid_db[p_id].is_valid != 0U) {
                float val = shm->pid_db[p_id].calculated_value;
                int32_t written = 0;

                if (appended_entries > 0U) {
                    written = snprintf(output + offset, max_len - (size_t)offset, ",");
                    if (written > 0) { offset += written; }
                }

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

    (void)snprintf(output + offset, max_len - (size_t)offset, "], \"ts\":%llu}",
                   (unsigned long long)shm->system_ticks);
}

void json_format_single_pid(uint8_t pid_id, float value, char *output, size_t max_len) {
    if ((output != NULL) && (max_len > 0U)) {
        (void)snprintf(output, max_len, "{\"pid\":\"0x%02X\",\"val\":%.2f}", pid_id, (double)value);
    }
}

void json_format_status(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    (void)snprintf(output, max_len,
        "{\"voltage\":%.2f,\"cpu_temp\":%.2f,\"bus_load\":%u,\"errors\":%u,"
        "\"rx\":%u,\"tx\":%u,\"bus_errors\":%u,\"ignition\":%s,\"mil\":%s,"
        "\"ecu_count\":%u,\"trip_distance_m\":%u,\"trip_duration_s\":%u,"
        "\"trip_max_speed\":%u,\"trip_fuel_ml\":%u,\"ts\":%llu}",
        (double)shm->battery_voltage,
        (double)shm->cpu_temp,
        (unsigned int)shm->bus_load_pct,
        (unsigned int)shm->error_count,
        (unsigned int)shm->rx_count,
        (unsigned int)shm->tx_count,
        (unsigned int)shm->bus_error_count,
        (shm->ignition_on != 0U) ? "true" : "false",
        (shm->mil_active != 0U) ? "true" : "false",
        (unsigned int)shm->ecu_count,
        (unsigned int)shm->trip_distance_m,
        (unsigned int)shm->trip_duration_s,
        (unsigned int)shm->trip_max_speed,
        (unsigned int)shm->trip_fuel_ml,
        (unsigned long long)shm->system_ticks);
}

void json_format_ecu_scan(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    int32_t offset = snprintf(output, max_len, "{\"ecus\":[");
    if ((offset < 0) || ((size_t)offset >= max_len)) {
        return;
    }

    uint8_t count = shm->ecu_count;
    if (count > VCI_MAX_ECU_NODES) {
        count = VCI_MAX_ECU_NODES;
    }

    for (uint8_t i = 0U; i < count; i++) {
        const vci_ecu_node_t *node = &shm->ecu_nodes[i];
        int32_t written;
        if (i > 0U) {
            written = snprintf(output + offset, max_len - (size_t)offset, ",");
            if (written > 0) { offset += written; }
        }

        written = snprintf(output + offset, max_len - (size_t)offset,
            "{\"tx\":\"0x%03X\",\"rx\":\"0x%03X\",\"name\":\"%s\",\"dtc_count\":%u,"
            "\"session\":\"0x%02X\",\"sec_level\":%u}",
            (unsigned int)node->tx_id, (unsigned int)node->rx_id,
            node->name, (unsigned int)node->dtc_count,
            (unsigned int)node->session_type,
            (unsigned int)node->security_level);
        if (written > 0) { offset += written; }
    }

    (void)snprintf(output + offset, max_len - (size_t)offset, "],\"count\":%u}", count);
}

void json_format_vehicle_info(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    const vci_ecu_node_t *node = (shm->ecu_count > 0U) ? &shm->ecu_nodes[0] : NULL;

    (void)snprintf(output, max_len,
        "{\"vin\":\"%s\",\"calibration_id\":\"%s\",\"serial\":\"%s\"}",
        (node != NULL) ? node->vin : "",
        (node != NULL) ? node->calibration_id : "",
        (node != NULL) ? node->name : "");
}

void json_format_trip(const vci_shared_mem_t *shm, char *output, size_t max_len) {
    if ((shm == NULL) || (output == NULL) || (max_len == 0U)) {
        return;
    }

    (void)snprintf(output, max_len,
        "{\"trip_distance_m\":%u,\"trip_duration_s\":%u,\"trip_avg_speed\":%u,"
        "\"trip_max_speed\":%u,\"trip_fuel_ml\":%u,\"trip_count\":%u}",
        (unsigned int)shm->trip_distance_m,
        (unsigned int)shm->trip_duration_s,
        (unsigned int)shm->trip_avg_speed,
        (unsigned int)shm->trip_max_speed,
        (unsigned int)shm->trip_fuel_ml,
        (unsigned int)shm->trip_count);
}

/* End of file json_formatter.c */
