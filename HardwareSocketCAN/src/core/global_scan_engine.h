/**
 * @file src/core/global_scan_engine.h
 * @brief Global ECU scan engine interface (auto-topology discovery).
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef GLOBAL_SCAN_ENGINE_H
#define GLOBAL_SCAN_ENGINE_H

#include "../../driver/obd_ioctl.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Executes one full bus sweep (UDS Tester Present over 0x7E0-0x7EF).
 * @param shm Shared memory region whose ECU inventory is populated
 */
void run_global_scan(automotive_data_t *shm);

/**
 * @brief Background scan thread entry point
 */
void *global_scan_engine_run(void *arg);

#ifdef __cplusplus
}
#endif

#endif /* GLOBAL_SCAN_ENGINE_H */
