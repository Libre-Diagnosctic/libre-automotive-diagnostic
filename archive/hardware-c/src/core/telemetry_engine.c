/**
 * @file src/core/telemetry_engine.c
 * @brief High-priority Polling Engine (Fixed-cycle real-time scheduling)
 * @details Осигурява постоянен поток от данни чрез циклично запитване на OBD-II PIDs.
 * Използва SCHED_FIFO за гарантиране на детерминистично поведение и минимален jitter.
 */

#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/obd_pids_db.h"
#include "../../lib/iso_tp_stack.h"

#define TELEMETRY_CYCLE_MS 20  /* 50Hz честота на опресняване */
#define CAN_TARGET_ID      0x7E0 /* Standard Engine ECU Request */
#define CAN_REPLY_ID       0x7E8 /* Standard Engine ECU Response */

/**
 * @brief Основна работна нишка на телеметричния енджин
 */
void *telemetry_engine_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;
    struct timespec next_cycle;
    uint8_t current_pid_idx = 0;
    int isotp_fd;

    /* 1. Инициализация на ISO-TP сокета за телеметрия */
    isotp_fd = isotp_stack_init("can0", CAN_TARGET_ID, CAN_REPLY_ID);
    if (isotp_fd < 0) {
        fprintf(stderr, "[TELEMETRY] Failed to open ISO-TP channel.\n");
        return NULL;
    }

    /* 2. Конфигуриране на Real-time тайминг */
    clock_gettime(CLOCK_MONOTONIC, &next_cycle);

    printf("[TELEMETRY] Engine started (Cycle: %dms).\n", TELEMETRY_CYCLE_MS);

    while (1) {
        /* Изчисляване на времето за следващия цикъл */
        next_cycle.tv_nsec += TELEMETRY_CYCLE_MS * 1000000L;
        if (next_cycle.tv_nsec >= 1000000000L) {
            next_cycle.tv_sec++;
            next_cycle.tv_nsec -= 1000000000L;
        }

        /* 3. Изпращане на заявка за конкретен PID (Mode 01) */
        const obd_pid_definition_t *pid = &MASTER_PID_TABLE[current_pid_idx];
        uint8_t tx_msg[2] = {0x01, pid->pid_id};

        if (isotp_stack_send(isotp_fd, tx_msg, 2) > 0) {
            uint8_t rx_buf[8];
            /* 4. Неблоково четене на отговора */
            int len = isotp_stack_receive(isotp_fd, rx_buf, sizeof(rx_buf));
            
            if (len >= 3 && rx_buf[0] == 0x41 && rx_buf[1] == pid->pid_id) {
                /* Директен запис в Zero-Copy региона */
                uint8_t pid_id = rx_buf[1];
                memcpy(shm->raw_pids[pid_id].bytes, &rx_buf[2], len - 2);
                shm->raw_pids[pid_id].timestamp = (uint64_t)time(NULL);
                shm->raw_pids[pid_id].valid = 1;
                
                /* Системна статистика */
                shm->system_ticks++;
            }
        }

        /* 5. Итериране към следващия PID от речника */
        current_pid_idx = (current_pid_idx + 1) % MASTER_PID_COUNT;

        /* Прецизно изчакване до следващия цикъл */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next_cycle, NULL);
    }

    isotp_stack_close(isotp_fd);
    return NULL;
}

/* Край на файл telemetry_engine.c */
