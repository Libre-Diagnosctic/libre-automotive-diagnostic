/**
 * @file src/core/health_monitor.c
 * @brief Bus-Load, Thermal Protection, Voltage Drop & Power Watchdog
 * @details Следи за физическото здраве на интерфейса и автомобилната шина.
 * Изпълнява превантивни действия при прегряване или пад на напрежението.
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/logging.h"
#include "../analysis/analysis_engine.h"
#include "../analysis/battery_health.h"

/* Дефиниции на критични прагове */
#define THERMAL_CRITICAL_TEMP 80.0f  /* Градуси Целзий */
#define VOLTAGE_CRITICAL_LOW  10.5f  /* V (Изтощен акумулатор) */
#define VOLTAGE_CRITICAL_HIGH 15.8f  /* V (Проблем с алтернатора) */
#define BUS_LOAD_HIGH_LIMIT   85     /* % натоварване на CAN */

/**
 * @brief Прочита текущата температура на SoC (System on Chip)
 */
static float get_system_temperature(void) {
    int fd = open("/sys/class/thermal/thermal_zone0/temp", O_RDONLY);
    if (fd < 0) return 0.0f;

    char buf[10];
    if (read(fd, buf, sizeof(buf)) > 0) {
        close(fd);
        return atof(buf) / 1000.0f;
    }
    close(fd);
    return 0.0f;
}

/**
 * @brief Основен цикъл за мониторинг на здравето
 */
void *health_monitor_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;
    LOG_INFO("HEALTH", "Monitoring Engine started.");

    while (1) {
        /* 0. Analytics tick: battery chemistry, VIN identification, uptime */
        battery_health_monitor_update(shm);
        analysis_tick(shm);

        /* 1. Мониторинг на захранването */
        if (shm->battery_voltage < VOLTAGE_CRITICAL_LOW) {
            LOG_ERROR("HEALTH", "Critical Low Voltage: %.2fV", shm->battery_voltage);
            shm->status_mask |= VCI_STAT_LOW_VOLTAGE;
            /* Възможна логика за безопасно заспиване */
        } else {
            shm->status_mask &= ~VCI_STAT_LOW_VOLTAGE;
        }
        if (shm->battery_voltage > VOLTAGE_CRITICAL_HIGH) {
            LOG_ERROR("HEALTH", "Overvoltage Detected: %.2fV", shm->battery_voltage);
        }

        /* 2. Термална защита */
        float cpu_temp = get_system_temperature();
        shm->cpu_temp = cpu_temp;
        if (cpu_temp > THERMAL_CRITICAL_TEMP) {
            LOG_ERROR("HEALTH", "System Overheating: %.1fC. Throttling commands...", cpu_temp);
            shm->status_mask |= VCI_STAT_OVERHEAT;
            /* Ограничаване на скоростта на запитване (Polling rate) */
        } else {
            shm->status_mask &= ~VCI_STAT_OVERHEAT;
        }

        /* 3. Мониторинг на шината (CAN Bus Health) */
        if (shm->bus_load_pct > BUS_LOAD_HIGH_LIMIT) {
            LOG_ERROR("HEALTH", "CAN Bus Overload: %d%%", shm->bus_load_pct);
            shm->mil_active = 1; // Визуализираме предупреждение на таблото
        }

        /* 4. Watchdog Tick */
        shm->system_ticks++;

        usleep(500000); /* Проверка на всеки 500ms */
    }
    return NULL;
}

/* Край на файл health_monitor.c */
