/**
 * @file src/analysis/analysis_engine.h
 * @brief Vehicle analytics engine.
 * @details Fuel economy regression, power estimation, peak detection and
 *          VIN-based vehicle identification. Consumes the shared memory
 *          PID cache and produces derived engineering metrics.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef ANALYSIS_ENGINE_H
#define ANALYSIS_ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/vin_decoder.h"

/**
 * @brief Derives instantaneous fuel consumption (L/100km)
 * @param speed_kmh Vehicle speed
 * @param maf_gs    Mass air flow in g/s
 * @return Litres per 100 km, or -1 if speed is too low
 */
float analysis_fuel_economy(float speed_kmh, float maf_gs);

/**
 * @brief Estimates engine power output (kW) from RPM and MAF
 * @param rpm Engine speed
 * @param maf_gs Mass air flow
 * @param afr   Air/fuel ratio (14.7 stoichiometric, 12.5 WOT)
 * @param lambda Sensor reading (1.0 = stoichiometric)
 * @return Estimated power in kW
 */
float analysis_power_estimate(float rpm, float maf_gs, float afr, float lambda);

/**
 * @brief Computes the absolute fuel consumption rate (L/h)
 */
float analysis_fuel_rate(float maf_gs);

/**
 * @brief Rolling peak tracker
 */
typedef struct {
    float   current_peak;
    bool    armed;
    float   trigger_level;
} analysis_peak_t;

/**
 * @brief Updates a peak tracker and reports the instantaneous peak value
 */
float analysis_peak_update(analysis_peak_t *peak, float sample);

/**
 * @brief Identifies the vehicle from the first discovered ECU VIN
 * @param shm Shared memory with the global scan inventory
 * @param info Output decoded VIN info
 * @return true if a valid VIN was decoded
 */
bool analysis_identify_vehicle(const automotive_data_t *shm, vin_info_t *info);

/**
 * @brief Selects the active vehicle profile (fuel density) from a VIN
 */
void analysis_profile_select(const char *vin);

/**
 * @brief Updates the derived battery chemistry registers from PID 0x42
 */
void analysis_update_battery(automotive_data_t *shm);

/**
 * @brief Master analytics tick - called periodically from the main loop
 */
void analysis_tick(automotive_data_t *shm);

#endif /* ANALYSIS_ENGINE_H */
