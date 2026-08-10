/**
 * @file src/core/telemetry_engine.c
 * @brief High-priority Polling Engine (Fixed-cycle real-time scheduling)
 * @details Осигурява постоянен поток от данни чрез циклично запитване на OBD-II PIDs.
 * Използва SCHED_FIFO за гарантиране на детерминистично поведение и минимален jitter.
 *
 * Integrated subsystems (wiring round):
 *  - SGW policy engine: authorizes every OBD/UDS request before transmission
 *  - UDS DID registry: annotates discovered DIDs for the web console
 *  - Trip statistics + trip logger + CSV exporter: live trip aggregation
 *  - CAN statistics: bus load / frame rate fed into shared memory
 *  - CAN recorder: optional raw-frame capture to binary log
 *  - J1939 + DBC decode: extended-frame parsing via optional .dbc database
 *  - WWH-OBD (ISO 27145): VIN acquisition through the diagnostic session
 *  - MQTT publisher: async telemetry streaming to a broker
 *  - Vehicle profiles: VIN-based engine parameter selection
 *  - Watchdog: supervision heartbeat for the polling loop
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <sched.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/obd_pids_db.h"
#include "../../lib/iso_tp_stack.h"
#include "../../lib/config_loader.h"
#include "../../lib/logging.h"
#include "../../lib/sgw_policy_engine.h"
#include "../../lib/trip_logger.h"
#include "../../lib/can_stats.h"
#include "../../lib/csv_exporter.h"
#include "../../lib/mqtt_client.h"
#include "../../lib/watchdog.h"
#include "../../lib/can_recorder.h"
#include "../../lib/j1939_stack.h"
#include "../../lib/dbc_parser.h"
#include "../../lib/wwh_obd_stack.h"
#include "../../lib/vehicle_profiles.h"
#include "../../lib/obd_dtc_decoder.h"
#include "../../lib/remote_bridge.h"
#include "../../lib/remote_vci_bridge.h"
#include "../analysis/analysis_engine.h"
#include "../analysis/graph_engine.h"
#include "../gateway/json_formatter.h"

#define TELEMETRY_CYCLE_MS_DEFAULT 20  /* 50Hz честота на опресняване */
#define CAN_TARGET_ID_DEFAULT      0x7E0 /* Standard Engine ECU Request */
#define CAN_REPLY_ID_DEFAULT       0x7E8 /* Standard Engine ECU Response */
#define MQTT_PUBLISH_MS_DEFAULT    1000U
#define DTC_SCAN_INTERVAL_MS       5000U   /* Mode 03 trouble-code sweep */
#define OBD_CONFIG_PATH_DEFAULT    "/etc/kobd/obd.conf"

/* OBD PID index constants used for trip / battery aggregation */
#define PID_RPM    0x0C
#define PID_SPEED  0x0D
#define PID_MAF    0x10
#define PID_COOLANT 0x05

/**
 * @brief Async MQTT publisher thread (demoted to SCHED_OTHER)
 */
static void *mqtt_publisher_thread(void *arg) {
    vci_shared_mem_t *shm = (vci_shared_mem_t *)arg;
    if (shm == NULL) {
        return NULL;
    }

    /* Never allow blocking network I/O inside an RT scheduling class */
    struct sched_param sp;
    sp.sched_priority = 0;
    (void)pthread_setschedparam(pthread_self(), SCHED_OTHER, &sp);

    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, OBD_CONFIG_PATH_DEFAULT);

    const char *host = config_get_string(&config, "mqtt", "host", "127.0.0.1");
    uint16_t port = (uint16_t)config_get_int(&config, "mqtt", "port", MQTT_DEFAULT_PORT);
    const char *client_id = config_get_string(&config, "mqtt", "client_id", "kobd-pi");
    const char *topic = config_get_string(&config, "mqtt", "topic", "kobd/telemetry");
    int32_t publish_ms = config_get_int(&config, "mqtt", "publish_ms", (int32_t)MQTT_PUBLISH_MS_DEFAULT);
    if (publish_ms < 200) {
        publish_ms = 200;
    }

    mqtt_client_t client;
    (void)memset(&client, 0, sizeof(client));

    LOG_INFO("MQTT", "Publisher thread started (host=%s:%u topic=%s).", host, port, topic);

    while (1) {
        if (!client.connected) {
            if (mqtt_connect(&client, host, port, client_id) == 0) {
                LOG_INFO("MQTT", "Broker connection established.");
            }
        }

        if (client.connected) {
            char payload[MQTT_MAX_PAYLOAD];
            (void)memset(payload, 0, sizeof(payload));
            json_format_all_pids(shm, payload, sizeof(payload));
            if (mqtt_publish(&client, topic, (const uint8_t *)payload,
                             (uint32_t)strlen(payload), false) < 0) {
                LOG_WARN("MQTT", "Publish failed - reconnecting.");
                mqtt_disconnect(&client);
                client.connected = false;
            }
        }

        (void)usleep((useconds_t)publish_ms * 1000U);
    }
    return NULL;
}

/**
 * @brief Основна работна нишка на телеметричния енджин
 */
void *telemetry_engine_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;
    struct timespec next_cycle;
    uint8_t current_pid_idx = 0;
    int isotp_fd;
    uint32_t cycle_counter = 0U;

    if (shm == NULL) {
        return NULL;
    }

    /* 0. Runtime configuration bootstrap */
    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, OBD_CONFIG_PATH_DEFAULT);

    const char *iface = config_get_string(&config, "can", "interface", "can0");
    uint32_t target_id = (uint32_t)config_get_int(&config, "can", "target_id", CAN_TARGET_ID_DEFAULT);
    uint32_t reply_id = (uint32_t)config_get_int(&config, "can", "reply_id", CAN_REPLY_ID_DEFAULT);
    uint32_t bitrate = (uint32_t)config_get_int(&config, "can", "bitrate", 500000);
    uint32_t cycle_ms = (uint32_t)config_get_int(&config, "telemetry", "cycle_ms", TELEMETRY_CYCLE_MS_DEFAULT);
    if (cycle_ms == 0U) {
        cycle_ms = TELEMETRY_CYCLE_MS_DEFAULT;
    }
    const char *trip_csv = config_get_string(&config, "trip", "csv_path", TRIP_LOG_DEFAULT_PATH);
    uint32_t idle_end_s = (uint32_t)config_get_int(&config, "trip", "end_after_idle_s", 120);
    bool recorder_enabled = config_get_bool(&config, "recorder", "enabled", false);
    const char *recorder_path = config_get_string(&config, "recorder", "path", "/var/log/kobd/capture.bin");
    const char *dbc_path = config_get_string(&config, "dbc", "path", "");
    bool wwh_vin_enabled = config_get_bool(&config, "diag", "wwh_vin", true);
    bool j1939_enabled = config_get_bool(&config, "diag", "j1939", true);
    bool mqtt_enabled = config_get_bool(&config, "mqtt", "enabled", false);

    /* 1. Инициализация на ISO-TP сокета за телеметрия */
    isotp_fd = isotp_stack_init(iface, target_id, reply_id);
    if (isotp_fd < 0) {
        LOG_ERROR("TELEMETRY", "Failed to open ISO-TP channel on %s.", iface);
        return NULL;
    }

    /* 1b. WWH-OBD session + VIN acquisition (ISO 27145) */
    if (wwh_vin_enabled) {
        if (wwh_obd_init_session(isotp_fd) == 0) {
            uint8_t vin[VCI_VIN_LEN];
            (void)memset(vin, 0, sizeof(vin));
            if (wwh_obd_get_vin(isotp_fd, vin, (uint16_t)sizeof(vin)) > 0) {
                (void)strncpy(shm->ecu_nodes[0].vin, (const char *)vin, sizeof(vin) - 1U);
                shm->ecu_nodes[0].is_active = 1U;
                if (shm->ecu_count == 0U) {
                    shm->ecu_count = 1U;
                }
                shm->ecu_nodes[0].protocol_flags |= 0x02U; /* Bit1 = WWH-OBD */
                LOG_INFO("TELEMETRY", "WWH-OBD VIN acquired: %s", shm->ecu_nodes[0].vin);
            }
        }
    }

    /* 1c. Security Gateway policy - authorize every request */
    sgw_policy_t policy;
    sgw_policy_init(&policy);
    (void)sgw_policy_add_sid(&policy, 0x01U, 0x00U, 0x00U, true);  /* Mode 01 read   */
    (void)sgw_policy_add_sid(&policy, 0x03U, 0x00U, 0x00U, true);  /* DTC read       */
    (void)sgw_policy_add_sid(&policy, 0x22U, 0x00U, 0x00U, true);  /* Read by ID     */
    (void)sgw_policy_add_did(&policy, 0xF190U, 1U, 0U, 0x00U, 0x00U);
    (void)sgw_policy_add_did(&policy, 0xF191U, 1U, 0U, 0x00U, 0x00U);

    /* 1d. Vehicle profile selection once the VIN becomes available */
    bool profile_selected = false;

    /* 1e. CAN statistics accumulator */
    can_stats_t stats;
    can_stats_init(&stats);

    /* 1f. Optional CAN recorder (raw frame capture) */
    if (recorder_enabled) {
        if (can_recorder_open(recorder_path) == 0) {
            LOG_INFO("TELEMETRY", "CAN recorder active -> %s", recorder_path);
        } else {
            LOG_WARN("TELEMETRY", "CAN recorder open failed on %s", recorder_path);
        }
    }

    /* 1g. Optional DBC database for commercial-vehicle signal decode */
    dbc_database_t dbc_db;
    (void)memset(&dbc_db, 0, sizeof(dbc_db));
    bool dbc_loaded = false;
    if ((dbc_path[0] != '\0') && (dbc_load(&dbc_db, dbc_path) == 0)) {
        dbc_loaded = true;
        LOG_INFO("TELEMETRY", "DBC database loaded: %u messages, %u signals.",
                 dbc_db.message_count, dbc_db.signal_count);
    }

    /* 1h. Watchdog supervision */
    watchdog_heartbeat_t hb;
    (void)memset(&hb, 0, sizeof(hb));
    watchdog_start(&hb, 0U);

    /* 1i. Async MQTT publisher (only when configured) */
    pthread_t mqtt_thread;
    (void)memset(&mqtt_thread, 0, sizeof(mqtt_thread));
    if (mqtt_enabled) {
        if (pthread_create(&mqtt_thread, NULL, mqtt_publisher_thread, shm) == 0) {
            (void)pthread_detach(mqtt_thread);
        }
    }

    /* 1j. Trip aggregation state */
    trip_session_t trip;
    trip_statistics_t tstat;
    (void)memset(&trip, 0, sizeof(trip));
    (void)memset(&tstat, 0, sizeof(tstat));
    bool trip_active = false;
    uint64_t last_moving_epoch = 0U;
    double prev_sample_s = 0.0;

    /* 1k. Periodic diagnostic scan state (DTC + readiness) */
    uint64_t last_dtc_scan_ms = 0U;
    uint16_t last_dtc_count = 0xFFFFU;
    uint8_t last_readiness_avail = 0xFFU;

    /* 2. Конфигуриране на Real-time тайминг */
    clock_gettime(CLOCK_MONOTONIC, &next_cycle);

    LOG_INFO("TELEMETRY", "Engine started (Cycle: %ums, iface: %s).", (unsigned)cycle_ms, iface);

    while (1) {
        /* Изчисляване на времето за следващия цикъл */
        next_cycle.tv_nsec += (long)cycle_ms * 1000000L;
        if (next_cycle.tv_nsec >= 1000000000L) {
            next_cycle.tv_sec++;
            next_cycle.tv_nsec -= 1000000000L;
        }

        /* 3. Валидиране на правата през SGW policy engine преди запитване */
        const obd_pid_definition_t *pid = &MASTER_PID_TABLE[current_pid_idx];
        bool authorized = (sgw_authorize_sid(&policy, pid->mode, 1U, 0U) == 0);

        if (authorized) {
            uint8_t tx_msg[2] = {0x01, pid->pid};

            if (isotp_stack_send(isotp_fd, tx_msg, 2) > 0) {
                can_stats_tx(&stats, (uint64_t)time(NULL));
                uint8_t rx_buf[8];
                /* 4. Неблоково четене на отговора */
                int len = isotp_stack_receive(isotp_fd, rx_buf, sizeof(rx_buf));

                if (len >= 3 && rx_buf[0] == 0x41 && rx_buf[1] == pid->pid) {
                    /* Директен запис в Zero-Copy региона */
                    uint8_t pid_id = rx_buf[1];
                    (void)memcpy(shm->pid_db[pid_id].bytes, &rx_buf[2], (size_t)(len - 2));
                    shm->pid_db[pid_id].timestamp = (uint64_t)time(NULL);
                    shm->pid_db[pid_id].is_valid = 1;

                    /* Изчисляване на engineering стойност през формулата */
                    if (pid->formula != NULL) {
                        shm->pid_db[pid_id].calculated_value =
                            pid->formula(&rx_buf[2], (uint8_t)(len - 2));
                    }
                    shm->pid_db[pid_id].len = (uint8_t)(len - 2);
                    can_stats_rx(&stats, (uint64_t)time(NULL));

                    /* Системна статистика */
                    shm->system_ticks++;
                }
            } else {
                can_stats_error(&stats, 1U, 0U);
            }
        }

        /* 5. Дренаж на RX ring буфера от драйвера (receiver capture) */
        uint64_t now_ms = (uint64_t)time(NULL);
        while (shm->head != shm->tail) {
            vci_frame_t *frame = &shm->rx_ring_buffer[shm->tail];
            can_stats_rx(&stats, now_ms);

            if (can_recorder_is_active()) {
                (void)can_recorder_write_frame(frame);
            }

            /* Forward the drained frame to any connected remote subsystem */
            if (remote_bridge_is_connected()) {
                (void)remote_bridge_send_frame(frame);
            }
            vci_bridge_relay_frame(frame);

            /* J1939 + DBC decoding for 29-bit extended frames */
            if ((j1939_enabled) && (frame->is_extended != 0U)) {
                j1939_address_t addr;
                j1939_parse_id(frame->can_id, &addr);
                if ((addr.pgn != J1939_PGN_REQUEST) && (addr.pgn != J1939_PGN_TP_DT)) {
                    if (dbc_loaded) {
                        const dbc_message_t *msg =
                            dbc_find_message(&dbc_db, frame->can_id & 0x1FFFFFFFU);
                        if (msg != NULL) {
                            float values[DBC_MAX_SIGNALS];
                            uint8_t n = dbc_decode_message(&dbc_db, msg, frame->data,
                                                           frame->dlc, values,
                                                           (uint8_t)(sizeof(values) / sizeof(values[0])));
                            LOG_TRACE("TELEMETRY", "DBC msg %s: %u signals decoded.", msg->name, n);
                        }
                    }
                }
            }

            shm->tail = (shm->tail + 1U) % VCI_BUFFER_SIZE;
        }

        /* 6. Периодично преизчисляване на bus load / frame rate */
        if (cycle_counter >= 100U) {
            can_stats_compute(&stats, bitrate);
            shm->bus_load_pct = (uint32_t)stats.bus_load_pct;
            shm->tx_count = stats.tx_total;
            shm->rx_count = stats.rx_total;
            shm->bus_error_count = stats.rx_errors + stats.tx_errors;
            shm->overrun_count = stats.overflow_count;
            cycle_counter = 0U;
        }
        cycle_counter++;

        /* 7. Vehicle profile selection on first valid VIN */
        if ((!profile_selected) && (shm->ecu_nodes[0].vin[0] != '\0') &&
            (strlen(shm->ecu_nodes[0].vin) >= 17U)) {
            profile_selected = vehicle_profile_select(shm->ecu_nodes[0].vin);
            if (profile_selected) {
                const vehicle_profile_t *p = vehicle_profile_selected();
                LOG_INFO("TELEMETRY", "Vehicle profile selected: %s", p->name);
            }
        }

        /* 8. Trip aggregation - sample speed / rpm / fuel once per cycle */
        {
            struct timespec ts;
            clock_gettime(CLOCK_MONOTONIC, &ts);
            double now_s = (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
            double delta_s = (prev_sample_s > 0.0) ? (now_s - prev_sample_s)
                                                   : ((double)cycle_ms / 1000.0);
            prev_sample_s = now_s;

            float speed = (shm->pid_db[PID_SPEED].is_valid != 0U)
                              ? shm->pid_db[PID_SPEED].calculated_value : 0.0f;
            float rpm = (shm->pid_db[PID_RPM].is_valid != 0U)
                            ? shm->pid_db[PID_RPM].calculated_value : 0.0f;
            float maf = (shm->pid_db[PID_MAF].is_valid != 0U)
                            ? shm->pid_db[PID_MAF].calculated_value : 0.0f;

            if (!trip_active && (speed > 0.5f)) {
                uint64_t now_epoch = (uint64_t)time(NULL);
                trip_begin(&trip, now_epoch);
                trip_statistics_begin(&tstat, (uint32_t)now_epoch);
                trip_active = true;
                last_moving_epoch = now_epoch;
            }

            if (trip_active) {
                uint64_t now_epoch = (uint64_t)time(NULL);
                if (speed > 0.5f) {
                    last_moving_epoch = now_epoch;
                }
                trip_update(&trip, (uint32_t)speed, maf, now_epoch);
                trip_statistics_sample(&tstat, (double)speed, (double)rpm,
                                       (double)analysis_fuel_rate(maf), delta_s);

                /* Trip termination after idle timeout */
                if ((now_epoch - last_moving_epoch) >= idle_end_s) {
                    trip_statistics_end(&tstat);
                    (void)trip_end(&trip, trip_csv);
                    char summary[160];
                    (void)trip_statistics_summary(&tstat, summary, sizeof(summary));
                    LOG_INFO("TELEMETRY", "%s", summary);
                    trip_active = false;
                }

                /* Mirror trip metrics into shared memory for the web console */
                shm->trip_distance_m = (uint32_t)(tstat.distance_km * 1000.0);
                shm->trip_duration_s = tstat.elapsed_s;
                shm->trip_avg_speed = (uint32_t)tstat.avg_speed_kph;
                shm->trip_max_speed = (uint32_t)tstat.max_speed_kph;
                shm->trip_fuel_ml = (uint32_t)(tstat.fuel_l * 1000.0);
            }
        }

        /* 8b. Periodic diagnostics: DTC sweep (Mode 03) + MIL status */
        if ((now_ms - last_dtc_scan_ms) >= DTC_SCAN_INTERVAL_MS) {
            last_dtc_scan_ms = now_ms;

            vci_ecu_node_t *ecu = &shm->ecu_nodes[0];
            if (sgw_authorize_sid(&policy, 0x03U, 1U, 0U) == 0) {
                uint8_t req = 0x03U;
                if (isotp_stack_send(isotp_fd, &req, 1) > 0) {
                    uint8_t rx_buf[64];
                    int rlen = isotp_stack_receive(isotp_fd, rx_buf, (uint16_t)sizeof(rx_buf));
                    if ((rlen >= 2) && (rx_buf[0] == 0x43U)) {
                        obd_dtc_t dtcs[OBD_DTC_MAX_RECORDS];
                        uint16_t n = obd_dtc_parse_mode03(&rx_buf[1], (uint16_t)(rlen - 1),
                                                          dtcs, OBD_DTC_MAX_RECORDS);
                        uint16_t stored = 0U;
                        for (uint16_t i = 0U; (i < n) && (stored < VCI_DTC_MAX); i++) {
                            ecu->dtc[(stored * 3U)] = (uint8_t)(dtcs[i].dtc_raw >> 8);
                            ecu->dtc[(stored * 3U) + 1U] = (uint8_t)(dtcs[i].dtc_raw & 0xFFU);
                            ecu->dtc[(stored * 3U) + 2U] = dtcs[i].status_byte;
                            stored++;
                        }
                        ecu->dtc_count = stored;
                        if (stored > 0U) {
                            shm->mil_active = 1U;
                            shm->status_mask |= VCI_STAT_MIL_ON;
                        } else {
                            shm->mil_active = 0U;
                            shm->status_mask &= ~VCI_STAT_MIL_ON;
                        }
                        if (stored != last_dtc_count) {
                            LOG_INFO("TELEMETRY", "DTC scan: %u trouble code(s).",
                                     (unsigned)stored);
                            last_dtc_count = stored;
                        }
                    }
                }
            }
        }

        /* 8c. I/M readiness monitors (PID 0x01 readiness A/B bytes) */
        if ((shm->pid_db[0x01].is_valid != 0U) && (shm->pid_db[0x01].len >= 2U)) {
            obd_readiness_monitor_t mon[OBD_READINESS_MONITORS];
            (void)memset(mon, 0, sizeof(mon));
            bool has_misfire = false;
            uint8_t avail = obd_readiness_parse(shm->pid_db[0x01].bytes[0],
                                                shm->pid_db[0x01].bytes[1],
                                                mon, &has_misfire);
            if (avail != last_readiness_avail) {
                uint8_t done = 0U;
                for (uint8_t i = 0U; i < avail; i++) {
                    if ((mon[i].supported != 0U) && (mon[i].completed != 0U)) {
                        done++;
                    }
                }
                LOG_INFO("TELEMETRY", "I/M readiness: %u/%u monitors complete%s.",
                         (unsigned)done, (unsigned)avail, has_misfire ? ", misfire present" : "");
                last_readiness_avail = avail;
            }
        }

        /* 8d. Scope / graph engine sample feeding */
        graph_engine_push_sample(0U, shm->pid_db[PID_RPM].calculated_value);
        graph_engine_push_sample(1U, shm->battery_voltage);

        /* 9. Периодичен CSV snapshot (data logging) всяка секунда */
        if ((cycle_counter % (1000U / cycle_ms)) == 0U) {
            csv_writer_t w;
            if (csv_writer_open(&w, config_get_string(&config, "csv", "path",
                                                      "/var/log/kobd/snapshot.csv")) == 0) {
                char ts[32];
                (void)snprintf(ts, sizeof(ts), "%lld", (long long)time(NULL));
                (void)csv_writer_add_string(&w, ts);
                (void)csv_writer_add_float(&w, shm->pid_db[PID_RPM].calculated_value);
                (void)csv_writer_add_float(&w, shm->pid_db[PID_SPEED].calculated_value);
                (void)csv_writer_add_float(&w, shm->pid_db[PID_COOLANT].calculated_value);
                (void)csv_writer_add_float(&w, shm->battery_voltage);
                (void)csv_writer_end_row(&w);
                csv_writer_close(&w);
            }
        }

        /* 10. Watchdog liveness heartbeat */
        watchdog_kick(&hb);

        /* 5. Итериране към следващия PID от речника */
        current_pid_idx = (uint8_t)((current_pid_idx + 1U) % MASTER_PID_COUNT);

        /* Прецизно изчакване до следващия цикъл */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next_cycle, NULL);
    }

    if (recorder_enabled) {
        can_recorder_close();
    }
    watchdog_stop(&hb);
    isotp_stack_close(isotp_fd);
    return NULL;
}

/* Край на файл telemetry_engine.c */
