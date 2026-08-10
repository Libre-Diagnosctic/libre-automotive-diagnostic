/**
 * @file trip_statistics.h
 * @brief Trip statistics aggregation engine.
 * @details Continuously accumulates distance, fuel, economy and speed
 *          histograms during a trip session and produces a final report.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef TRIP_STATISTICS_H
#define TRIP_STATISTICS_H

#include <stdint.h>
#include <stdbool.h>

#define TRIP_HISTOGRAM_BUCKETS  8U

/**
 * @brief Single trip aggregation state
 */
typedef struct {
    bool     active;
    uint32_t started_unix;

    double   distance_km;
    double   fuel_l;
    double   max_speed_kph;
    double   avg_speed_kph;
    double   running_total_speed;
    uint32_t speed_samples;

    uint32_t elapsed_s;
    uint32_t stop_count;
    double   idle_time_s;

    uint32_t histogram[TRIP_HISTOGRAM_BUCKETS];
} trip_statistics_t;

/**
 * @brief Resets and starts a new trip aggregation
 */
void trip_statistics_begin(trip_statistics_t *stat, uint32_t unix_time);

/**
 * @brief Feeds a single telemetry sample
 * @param speed_kph Current vehicle speed
 * @param rpm       Current engine speed
 * @param fuel_rate_lph Instantaneous fuel rate in l/h
 * @param delta_s   Elapsed seconds since the previous sample
 */
void trip_statistics_sample(trip_statistics_t *stat, double speed_kph,
                            double rpm, double fuel_rate_lph, double delta_s);

/**
 * @brief Finalizes the trip
 */
void trip_statistics_end(trip_statistics_t *stat);

/**
 * @brief Fills the "overall economy" of the trip (l/100km)
 */
double trip_statistics_economy(const trip_statistics_t *stat);

/**
 * @brief Formats a one-line human readable summary into buf
 */
int32_t trip_statistics_summary(const trip_statistics_t *stat,
                                char *buf, uint32_t capacity);

#endif /* TRIP_STATISTICS_H */
