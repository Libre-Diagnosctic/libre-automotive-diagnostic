/**
 * @file main.c
 * @brief System Master Orchestrator (State Machine / Failsafe logic)
 * @details Allocates core POSIX real-time threads and orchestrates shared memory lifecycle.
 *          Strictly utilizes thread joins to ensure graceful hardware shutdown.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <signal.h>
#include <unistd.h>
#include <sys/mman.h>
#include <fcntl.h>
#include "../../driver/obd_ioctl.h"

/* External High-Priority Thread Runner Prototypes */
extern void *telemetry_engine_run(void *arg);
extern void *web_server_run(void *arg);
extern void *dashboard_render_run(void *arg);
extern void *health_monitor_run(void *arg);

/* Finite State Machine (FSM) Configuration Definition */
typedef enum {
    VCI_STATE_INIT       = 0,
    VCI_STATE_IDLE       = 1,
    VCI_STATE_ACTIVE     = 2,
    VCI_STATE_DIAGNOSTIC = 3,
    VCI_STATE_FAILSAFE   = 4,
    VCI_STATE_SHUTDOWN   = 5
} vci_system_state_t;

static volatile vci_system_state_t g_sys_state = VCI_STATE_INIT;
static vci_shared_mem_t *g_shm = NULL;
static int32_t g_vci_fd = -1;

/**
 * @brief Thread-safe signal handler managing runtime lifecycle termination flags
 */
static void handle_termination(int32_t sig) {
    (void)sig; /* Suppress unused parameter compilation warning under -Werror */
    g_sys_state = VCI_STATE_SHUTDOWN;
}

/**
 * @brief Configures memory-mapped zero-copy interface with the custom VCI kernel driver
 * @return 0 on success, or a negative verification code on failure path
 */
static int32_t init_vci_bridge(void) {
    g_vci_fd = open("/dev/obd_vci", O_RDWR);
    if (g_vci_fd < 0) {
        return -1;
    }

    /* Technical Synchronization: Explicitly map using the core hardware-aligned shared architecture */
    g_shm = (vci_shared_mem_t *)mmap(NULL, sizeof(vci_shared_mem_t), 
                                     PROT_READ | PROT_WRITE, MAP_SHARED, g_vci_fd, 0);
    
    if (g_shm == MAP_FAILED) {
        (void)close(g_vci_fd);
        g_vci_fd = -1;
        return -2;
    }
    return 0;
}

/**
 * @brief Master Orchestrator Main Entry Execution Path
 */
int main(int argc, char *argv[]) {
    (void)argc; 
    (void)argv;
    
    pthread_t thread_telemetry;
    pthread_t thread_web;
    pthread_t thread_ui;
    pthread_t thread_health;
    struct sched_param param;

    /* 1. System Setup - Secure POSIX Sigaction Interlocking Configuration */
    struct sigaction action;
    (void)memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = handle_termination;
    (void)sigaction(SIGINT, &action, NULL);
    (void)sigaction(SIGTERM, &action, NULL);

    if (init_vci_bridge() != 0) {
        fprintf(stderr, "[FATAL] Failed to initialize VCI Kernel Bridge. Verify if driver module is inserted.\n");
        return EXIT_FAILURE;
    }

    /* Clear the freshly mapped memory region using aligned boundary definitions */
    (void)memset(g_shm, 0, sizeof(vci_shared_mem_t));

    printf("[CORE] K-OBD-PI Automotive Master Orchestrator Successfully Engaged.\n");

    /* 2. Thread Launch (Real-time FIFO Deterministic Scheduling Assignments) */
    
    // Thread 0: Health Monitor (Highest Priority ASIL Watchdog Subsystem)
    param.sched_priority = 95;
    if (pthread_create(&thread_health, NULL, health_monitor_run, g_shm) == 0) {
        (void)pthread_setschedparam(thread_health, SCHED_FIFO, &param);
    }

    // Thread 1: Telemetry Engine (High Priority Fast Polling Loop)
    param.sched_priority = 90;
    if (pthread_create(&thread_telemetry, NULL, telemetry_engine_run, g_shm) == 0) {
        (void)pthread_setschedparam(thread_telemetry, SCHED_FIFO, &param);
    }

    // Thread 2: Web Server Gateway (Normal Priority REST API Daemon)
    (void)pthread_create(&thread_web, NULL, web_server_run, g_shm);

    // Thread 3: Local Dashboard UI Framebuffer Layer (Raylib Interface Renderer)
    (void)pthread_create(&thread_ui, NULL, dashboard_render_run, g_shm);

    g_sys_state = VCI_STATE_IDLE;

    /* 3. Main Business Logic Loop (Failsafe & State Evaluation Framework) */
    while (g_sys_state != VCI_STATE_SHUTDOWN) {
        
        /* Continuous evaluation of critical hardware health metrics counters */
        if ((g_shm->bus_load_pct > 95U) || (g_shm->error_count > 1000U)) {
            if (g_sys_state != VCI_STATE_FAILSAFE) {
                fprintf(stderr, "[CRITICAL] Automotive bus line compromised. Forcing transition into Failsafe Mode.\n");
                g_sys_state = VCI_STATE_FAILSAFE;
                g_shm->status_mask |= VCI_STAT_BUS_OFF;
            }
        }

        /* Automated tracking of vehicle state transitions via Terminal 15 status indicators */
        if ((g_shm->ignition_on != 0U) && (g_sys_state == VCI_STATE_IDLE)) {
            g_sys_state = VCI_STATE_ACTIVE;
            g_shm->status_mask |= VCI_STAT_IGNITION_ON;
            printf("[CORE] Ignition Terminal 15 transition detected. Engine State: ACTIVE.\n");
        } 
        else if ((g_shm->ignition_on == 0U) && (g_sys_state == VCI_STATE_ACTIVE)) {
            g_sys_state = VCI_STATE_IDLE;
            g_shm->status_mask &= ~VCI_STAT_IGNITION_ON;
            printf("[CORE] Ignition lost. Moving VCI node context into Standby mode.\n");
        }
        else {
            /* Keep processing background ticks */
        }

        /* Bounded cyclic tick delay preventing orchestration core saturation (100ms interval) */
        (void)usleep(100000); 
    }

    /* 4. Safe Structural Cleanup & Resource Demapping Release */
    printf("[CORE] Initiating synchronized graceful shutdown sequence. Joining worker threads...\n");
    
    /* Technical Synchronization Fix: Standard-compliant pthread_join execution loops 
     * ensure memory locks and hardware buffers dissolve cleanly without leaks */
    (void)pthread_join(thread_telemetry, NULL);
    (void)pthread_join(thread_web, NULL);
    (void)pthread_join(thread_ui, NULL);
    (void)pthread_join(thread_health, NULL);

    /* Safely release file interfaces and unmap shared RAM descriptors */
    (void)munmap(g_shm, sizeof(vci_shared_mem_t));
    if (g_vci_fd >= 0) {
        (void)close(g_vci_fd);
    }

    printf("[CORE] System halt sequence executed successfully. VCI node offline.\n");
    return EXIT_SUCCESS;
}

/* End of file main.c */
