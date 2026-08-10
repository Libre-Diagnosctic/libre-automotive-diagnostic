/**
 * @file src/analysis/battery_health.h
 * @brief Battery / alternator health analysis interface.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef BATTERY_HEALTH_H
#define BATTERY_HEALTH_H

#include <stdint.h>
#include <stdbool.h>
#include "../../driver/obd_ioctl.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief State-of-Charge estimate from resting voltage
 */
float battery_calculate_soc(float voltage);

/**
 * @brief Detects a failed alternator diode via voltage ripple analysis
 */
bool battery_check_alternator_ripple(const float *samples, uint32_t count);

/**
 * @brief State-of-Health estimate from static vs cranking voltage
 */
float battery_estimate_soh(float v_static, float v_crank);

/**
 * @brief Master battery diagnostic update (reads PID 0x42)
 */
void battery_health_monitor_update(automotive_data_t *shm);

#ifdef __cplusplus
}
#endif

#endif /* BATTERY_HEALTH_H */
