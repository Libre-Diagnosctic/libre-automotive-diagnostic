/**
 * @file src/analysis/trip_statistics.c
 * @brief Trip statistics aggregation implementation.
 * @details Speed histogram buckets: <10, <30, <50, <70, <90, <110, <130,
 *          >=130 km/h. A speed below 1 km/h counts as idle/stop time.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include "trip_statistics.h"

#include <stdio.h>
#include <string.h>

void trip_statistics_begin(trip_statistics_t *stat, uint32_t unix_time) {
    if (stat == NULL) {
        return;
    }
    (void)memset(stat, 0, sizeof(*stat));
    stat->active = true;
    stat->started_unix = unix_time;
}

void trip_statistics_sample(trip_statistics_t *stat, double speed_kph,
                            double rpm, double fuel_rate_lph, double delta_s) {
    if ((stat == NULL) || (!stat->active) || (delta_s <= 0.0)) {
        return;
    }

    double hours = delta_s / 3600.0;

    /* Idle/stop accounting */
    if (speed_kph < 1.0) {
        stat->stop_count++;
        stat->idle_time_s += delta_s;
    }

    /* Distance */
    stat->distance_km += speed_kph * hours;

    /* Fuel integration */
    stat->fuel_l += fuel_rate_lph * hours;

    /* Speed stats */
    if (speed_kph > stat->max_speed_kph) {
        stat->max_speed_kph = speed_kph;
    }
    stat->running_total_speed += speed_kph;
    stat->speed_samples++;
    stat->avg_speed_kph = stat->running_total_speed /
                          (double)stat->speed_samples;

    stat->elapsed_s += (uint32_t)delta_s;

    /* Histogram */
    uint32_t bucket = 0U;
    if (speed_kph >= 130.0)      { bucket = 7U; }
    else if (speed_kph >= 110.0) { bucket = 6U; }
    else if (speed_kph >= 90.0)  { bucket = 5U; }
    else if (speed_kph >= 70.0)  { bucket = 4U; }
    else if (speed_kph >= 50.0)  { bucket = 3U; }
    else if (speed_kph >= 30.0)  { bucket = 2U; }
    else if (speed_kph >= 10.0)  { bucket = 1U; }
    else                         { bucket = 0U; }
    stat->histogram[bucket]++;

    (void)rpm;   /* Reserved for future driver-workload metrics */
}

void trip_statistics_end(trip_statistics_t *stat) {
    if (stat == NULL) {
        return;
    }
    stat->active = false;
    if (stat->speed_samples > 0U) {
        stat->avg_speed_kph = stat->running_total_speed /
                              (double)stat->speed_samples;
    }
}

double trip_statistics_economy(const trip_statistics_t *stat) {
    if ((stat == NULL) || (stat->distance_km <= 0.0001)) {
        return 0.0;
    }
    return (stat->fuel_l / stat->distance_km) * 100.0;
}

int32_t trip_statistics_summary(const trip_statistics_t *stat,
                                char *buf, uint32_t capacity) {
    if ((stat == NULL) || (buf == NULL)) {
        return -1;
    }
    int32_t n = snprintf(buf, capacity,
        "Trip %us | %.2f km | %.2f l | %.2f l/100km | avg %.1f km/h | "
        "max %.1f km/h | idle %.0fs | stops %u",
        stat->elapsed_s,
        stat->distance_km,
        stat->fuel_l,
        trip_statistics_economy(stat),
        stat->avg_speed_kph,
        stat->max_speed_kph,
        stat->idle_time_s,
        stat->stop_count);
    return (n < 0) ? -2 : n;
}

/* End of file trip_statistics.c */
