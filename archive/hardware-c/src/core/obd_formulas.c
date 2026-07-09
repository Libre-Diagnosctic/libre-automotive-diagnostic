/**
 * @file lib/obd_formulas.c
 * @brief Математически детерминистичен Engine за изчисление на PIDs.
 * @details Имплементация на всички формули съгласно SAE J1979 / Wikipedia.
 * Използва fixed-point аритметика, където е възможно, за максимална скорост.
 */

#include "obd_pids_db.h"
#include <stdint.h>

/* Дефиниции за байтове за по-лесно четене на формулите */
#define A (data[0])
#define B (data[1])
#define C (data[2])
#define D (data[3])

/**
 * @brief Engine Load: 100/255 * A
 */
float parse_engine_load(uint8_t *data, uint8_t len) {
    return (100.0f / 255.0f) * A;
}

/**
 * @brief Coolant/Intake/Oil Temp: A - 40
 */
float parse_coolant_temp(uint8_t *data, uint8_t len) {
    return (float)A - 40.0f;
}

float parse_intake_temp(uint8_t *data, uint8_t len) {
    return (float)A - 40.0f;
}

float parse_ambient_temp(uint8_t *data, uint8_t len) {
    return (float)A - 40.0f;
}

float parse_oil_temp(uint8_t *data, uint8_t len) {
    return (float)A - 40.0f;
}

/**
 * @brief Fuel Trim: (100/128 * A) - 100
 */
float parse_fuel_trim(uint8_t *data, uint8_t len) {
    return ((100.0f / 128.0f) * A) - 100.0f;
}

/**
 * @brief Fuel Pressure: A * 3
 */
float parse_fuel_pressure(uint8_t *data, uint8_t len) {
    return (float)A * 3.0f;
}

/**
 * @brief MAP: A
 */
float parse_intake_pressure(uint8_t *data, uint8_t len) {
    return (float)A;
}

/**
 * @brief Engine RPM: ((A*256)+B)/4
 */
float parse_rpm(uint8_t *data, uint8_t len) {
    return ((256.0f * A) + B) / 4.0f;
}

/**
 * @brief Speed: A
 */
float parse_speed(uint8_t *data, uint8_t len) {
    return (float)A;
}

/**
 * @brief Timing Advance: (A/2) - 64
 */
float parse_timing_advance(uint8_t *data, uint8_t len) {
    return ((float)A / 2.0f) - 64.0f;
}

/**
 * @brief MAF: ((A*256)+B)/100
 */
float parse_maf(uint8_t *data, uint8_t len) {
    return ((256.0f * A) + B) / 100.0f;
}

/**
 * @brief Throttle/Fuel Level: 100/255 * A
 */
float parse_throttle_pos(uint8_t *data, uint8_t len) {
    return (100.0f / 255.0f) * A;
}

float parse_fuel_level(uint8_t *data, uint8_t len) {
    return (100.0f / 255.0f) * A;
}

/**
 * @brief Runtime/Distance: (A*256)+B
 */
float parse_engine_runtime(uint8_t *data, uint8_t len) {
    return (float)((256 * A) + B);
}

float parse_mil_distance(uint8_t *data, uint8_t len) {
    return (float)((256 * A) + B);
}

/**
 * @brief Module Voltage: ((A*256)+B)/1000
 */
float parse_module_voltage(uint8_t *data, uint8_t len) {
    return ((256.0f * A) + B) / 1000.0f;
}

/**
 * @brief Fuel Rate: ((A*256)+B)/20
 */
float parse_fuel_rate(uint8_t *data, uint8_t len) {
    return ((256.0f * A) + B) / 20.0f;
}

/**
 * @brief Torque: A - 125
 */
float parse_actual_torque(uint8_t *data, uint8_t len) {
    return (float)A - 125.0f;
}
