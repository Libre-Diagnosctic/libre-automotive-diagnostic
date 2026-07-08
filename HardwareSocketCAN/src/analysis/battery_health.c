/**
 * @file src/analysis/battery_health.c
 * @brief Battery/Alternator Analysis (Ripple, Cold-cranking, State-of-Health)
 * @details Реализира алгоритми за анализ на електрохимичното състояние на акумулатора 
 * и диагностика на изправителния блок на алтернатора чрез анализ на пулсациите.
 * Стандарти: ASIL-B Ready, ISO 16750-2.
 */

#include <stdio.h>
#include <stdint.h>
#include <math.h>
#include "../../driver/obd_ioctl.h"

/* Константи за диагностика на оловно-киселинни и AGM батерии */
#define BATT_V_FULL          12.70f
#define BATT_V_EMPTY         11.80f
#define ALTERNATOR_MIN_V     13.20f
#define ALTERNATOR_MAX_V     15.20f
#define RIPPLE_THRESHOLD_MV  150.0f  /* Праг за дефектен диод в алтернатора */

/**
 * @brief Пресмята State of Charge (SOC) в проценти на база напрежение при покой
 */
float battery_calculate_soc(float voltage) {
    if (voltage >= BATT_V_FULL) return 100.0f;
    if (voltage <= BATT_V_EMPTY) return 0.0f;
    return ((voltage - BATT_V_EMPTY) / (BATT_V_FULL - BATT_V_EMPTY)) * 100.0f;
}

/**
 * @brief Анализ на пулсациите (Ripple Analysis) за детекция на изгорял диод
 * @param samples Масив от високочестотни измервания на напрежението
 * @param count Брой проби
 * @return true ако пулсациите са над допустимия праг
 */
bool battery_check_alternator_ripple(const float *samples, uint32_t count) {
    float v_min = 20.0f;
    float v_max = 0.0f;

    for (uint32_t i = 0; i < count; i++) {
        if (samples[i] < v_min) v_min = samples[i];
        if (samples[i] > v_max) v_max = samples[i];
    }

    float ripple_mv = (v_max - v_min) * 1000.0f;
    return (ripple_mv > RIPPLE_THRESHOLD_MV);
}

/**
 * @brief Оценка на Cold Cranking Amps (CCA) чрез пад на напрежението при старт
 * @param v_static Напрежение преди старт
 * @param v_crank Минимално напрежение по време на въртене на стартера
 */
float battery_estimate_soh(float v_static, float v_crank) {
    /* Опростен модел за State of Health (SOH) */
    float voltage_drop = v_static - v_crank;
    
    if (v_crank < 9.6f) return 40.0f;  /* Критично състояние */
    if (voltage_drop > 2.5f) return 60.0f; /* Високо вътрешно съпротивление */
    
    return 95.0f; /* Здрава батерия */
}

/**
 * @brief Основна диагностична логика, извиквана от главния цикъл
 */
void battery_health_monitor_update(automotive_data_t *shm) {
    /* Използваме PID 0x42 (Control Module Voltage) за прецизно измерване */
    uint8_t *raw_volt = shm->raw_pids[0x42].bytes;
    float v_batt = ((raw_volt[0] * 256.0f) + raw_volt[1]) / 1000.0f;

    shm->battery_voltage = v_batt;

    /* Детекция на състоянието на алтернатора */
    if (shm->ignition_on && v_batt < ALTERNATOR_MIN_V) {
        shm->error_count++; /* Low charging system output */
    }
}

/* Край на файл battery_health.c */
