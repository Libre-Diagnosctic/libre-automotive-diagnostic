/**
 * @file src/gateway/json_formatter.h
 * @brief Header specification for the memory-safe JSON serialization engine.
 * @details Declares boundaries and interfaces for converting raw binary cache
 *          structures into compliant JSON schemas.
 * Standards: MISRA-C:2012, ASIL-D Safe Memory Tracking
 */

#ifndef JSON_FORMATTER_H
#define JSON_FORMATTER_H

#include <stdint.h>
#include <stddef.h>
#include "../../driver/obd_ioctl.h"   /* Required for vci_shared_mem_t definition */
#include "../../lib/obd_pids_db.h"    /* Master PID registry + obd_pid_definition_t */
#include "../../lib/obd_dtc_decoder.h"/* DTC decode helpers                        */

/**
 * @brief Formats the full engineering dictionary payload as a JSON array
 */
void json_format_all_pids(const vci_shared_mem_t *shm, char *output, size_t max_len);

/**
 * @brief Compact JSON object for a single diagnostic parameter
 */
void json_format_single_pid(uint8_t pid_id, float value, char *output, size_t max_len);

/**
 * @brief Full system status object (voltage, bus load, errors, trip registers)
 */
void json_format_status(const vci_shared_mem_t *shm, char *output, size_t max_len);

/**
 * @brief Discovered ECU inventory array
 */
void json_format_ecu_scan(const vci_shared_mem_t *shm, char *output, size_t max_len);

/**
 * @brief First ECU VIN / calibration identification object
 */
void json_format_vehicle_info(const vci_shared_mem_t *shm, char *output, size_t max_len);

/**
 * @brief Trip aggregate registers object
 */
void json_format_trip(const vci_shared_mem_t *shm, char *output, size_t max_len);

#endif /* JSON_FORMATTER_H */
