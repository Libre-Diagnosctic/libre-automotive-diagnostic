/**
 * @file src/analysis/analysis_engine.c
 * @brief Vehicle analytics engine implementation.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include "analysis_engine.h"

#include <math.h>
#include <string.h>
#include <time.h>
#include "../../lib/vehicle_profiles.h"

#define AIR_DENSITY_G_PER_L   1.225f
#define FUEL_DENSITY_G_PER_ML 0.82f
#define MAX_ECONOMY_RETURN    300.0f

/* Fuel density selected from the active vehicle profile (kg/l == g/ml) */
static float g_fuel_density_g_per_ml = FUEL_DENSITY_G_PER_ML;

/**
 * @brief Selects the active profile density once the VIN is available
 */
void analysis_profile_select(const char *vin) {
    if ((vin == NULL) || (vin[0] == '\0')) {
        return;
    }
    if (vehicle_profile_select(vin)) {
        const vehicle_profile_t *p = vehicle_profile_selected();
        g_fuel_density_g_per_ml = (float)p->fuel_density;
    }
}

float analysis_fuel_economy(float speed_kmh, float maf_gs) {
    if (speed_kmh < 5.0f) {
        return -1.0f;
    }
    /* maf_gs / (air density) = airflow L/s; / AF ratio => fuel g/s */
    float fuel_gs = maf_gs / AIR_DENSITY_G_PER_L;
    float fuel_ml_s = fuel_gs / g_fuel_density_g_per_ml;

    float distance_m_per_h = speed_kmh * 1000.0f;
    float seconds_per_100km = (100.0f * 3600.0f) / speed_kmh;

    float litres_per_100km = (fuel_ml_s / 1000.0f) * seconds_per_100km;
    if (litres_per_100km > MAX_ECONOMY_RETURN) {
        litres_per_100km = MAX_ECONOMY_RETURN;
    }
    return litres_per_100km;
}

float analysis_fuel_rate(float maf_gs) {
    if (maf_gs < 0.0f) {
        maf_gs = 0.0f;
    }
    float fuel_gs = maf_gs / AIR_DENSITY_G_PER_L;
    float fuel_ml_s = fuel_gs / g_fuel_density_g_per_ml;
    return fuel_ml_s * 3.6f;   /* L/h */
}

float analysis_power_estimate(float rpm, float maf_gs, float afr, float lambda) {
    if ((rpm < 100.0f) || (maf_gs <= 0.0f)) {
        return 0.0f;
    }
    /* Fuel energy: gasoline ~ 44.4 MJ/kg; engine efficiency ~ 0.25 */
    float maf_kg_s = maf_gs / 1000.0f;
    float fuel_kg_s = maf_kg_s / (afr * ((lambda > 0.5f) ? lambda : 1.0f));
    float thermal_power_kw = fuel_kg_s * 44400.0f;
    float shaft_power_kw = thermal_power_kw * 0.25f;
    if (shaft_power_kw < 0.0f) {
        shaft_power_kw = 0.0f;
    }
    return shaft_power_kw;
}

float analysis_peak_update(analysis_peak_t *peak, float sample) {
    if ((peak == NULL) || (!peak->armed)) {
        return 0.0f;
    }
    if (sample > peak->current_peak) {
        peak->current_peak = sample;
    }
    return peak->current_peak;
}

bool analysis_identify_vehicle(const automotive_data_t *shm, vin_info_t *info) {
    if ((shm == NULL) || (info == NULL) || (shm->ecu_count == 0U)) {
        return false;
    }
    const char *vin = shm->ecu_nodes[0].vin;
    if ((vin == NULL) || (vin[0] == '\0') || (strlen(vin) < 17U)) {
        return false;
    }
    vin_decode(vin, info);
    return info->checksum_valid;
}

void analysis_update_battery(automotive_data_t *shm) {
    if (shm == NULL) {
        return;
    }
    if ((shm->pid_db[0x42].is_valid != 0U) && (shm->pid_db[0x42].len >= 2U)) {
        const uint8_t *raw = shm->pid_db[0x42].bytes;
        shm->battery_voltage = ((float)((raw[0] << 8) | raw[1])) / 1000.0f;
    }
}

void analysis_tick(automotive_data_t *shm) {
    if (shm == NULL) {
        return;
    }

    analysis_update_battery(shm);

    /* Vehicle identification on first successful scan */
    if ((shm->ecu_count > 0U) && (shm->status_mask & VCI_STAT_SCANNING) == 0U) {
        vin_info_t info;
        if (analysis_identify_vehicle(shm, &info)) {
            analysis_profile_select(shm->ecu_nodes[0].vin);
        }
    }

    /* System uptime tracking */
    static uint64_t boot_epoch = 0U;
    if (boot_epoch == 0U) {
        boot_epoch = (uint64_t)time(NULL);
    }
    shm->uptime_sec = (float)((uint64_t)time(NULL) - boot_epoch);
}

/* End of file analysis_engine.c */
