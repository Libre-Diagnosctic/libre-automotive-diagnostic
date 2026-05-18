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
#include "../../driver/obd_ioctl.h" /* Required for vci_shared_mem_t definition */

/* Master PID Registry Bound (Synchronized with api/diagnostic_db.csv constraints) */
#define MASTER_PID_COUNT    4U

/**
 * @struct obd_pid_definition_t
 * @brief Layout architecture definition for programmatic database tracking items
 */
typedef struct {
    uint8_t     pid_id;              /**< Physical parameter identifier matching J1979 specs */
    const char *description;         /**< Alphanumeric human-readable label reference context */
    const char *unit;                /**< Standardized scientific metric system symbol label */
} obd_pid_definition_t;

/* Global reference array exported from the mathematical compilation layout mapping stack */
extern const obd_pid_definition_t MASTER_PID_TABLE[MASTER_PID_COUNT];

/**
 * @brief Memory-bounded formatting engine parsing whole structures into JSON arrays
 * @param shm Strict const pointer referencing the zero-copy kernel shared memory block
 * @param output Target character pointer memory coordinate for text stream expansion
 * @param max_len Pre-allocated static size boundary limit to prevent memory overruns
 */
void json_format_all_pids(const vci_shared_mem_t *shm, char *output, size_t max_len);

#endif /* JSON_FORMATTER_H */
