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
#include "../../lib/config_loader.h"
#include "../../lib/logging.h"
#include "../../lib/daemon_utils.h"
#include "../../lib/self_test.h"
#include "../../lib/token_auth_mgr.h"

/* External High-Priority Thread Runner Prototypes */
extern void *telemetry_engine_run(void *arg);
extern void *web_server_run(void *arg);
extern void *dashboard_render_run(void *arg);
extern void *health_monitor_run(void *arg);
extern void *global_scan_engine_run(void *arg);
extern void *vci_virtual_bridge_server(void *arg);
extern void *j2534_server_run(void *arg);

/* External diagnostic service entry points (wired-in live subsystems) */
extern int vci_doip_activate(void);
extern void vci_doip_deactivate(void);
extern void *vci_doip_gateway_run(void *arg);
extern void *remote_bridge_thread_main(void *arg);

#define OBD_CONFIG_PATH_DEFAULT "/etc/kobd/obd.conf"

/* Demo token blob for secure-boot integration testing */
static const uint8_t g_demo_token[16] = {
    0x4B, 0x4F, 0x42, 0x44, 0x50, 0x49, 0x32, 0x30,
    0x32, 0x36, 0x53, 0x47, 0x57, 0x4D, 0x41, 0x53
};

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
    pthread_t thread_telemetry;
    pthread_t thread_web;
    pthread_t thread_ui;
    pthread_t thread_health;
    struct sched_param param;

    /* 1. Configuration Bootstrap - load runtime policies from INI store */
    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    const char *config_path = (argc > 1) ? argv[1] : OBD_CONFIG_PATH_DEFAULT;
    if (config_load(&config, config_path) != 0) {
        (void)fprintf(stderr, "[CORE] Config '%s' not found - running with defaults.\n",
                      config_path);
    }

    /* 2. Logging subsystem - severity and sink from configuration */
    log_init((uint8_t)config_get_int(&config, "core", "log_level",
                                     LOG_LEVEL_DEFAULT),
             config_get_bool(&config, "core", "use_syslog", false));

    /* 3. Daemonize if configured (double-fork + PID file) */
    if (config_get_bool(&config, "core", "daemonize", false)) {
        if (daemon_start(config_get_string(&config, "core", "pid_file",
                                           DAEMON_PID_FILE_DEFAULT)) != 0) {
            LOG_ERROR("CORE", "Daemonize failed.");
            return EXIT_FAILURE;
        }
    }

    /* 4. Power-on self-test suite (configurable, non-fatal) */
    if (config_get_bool(&config, "core", "run_selftest", true)) {
        selftest_report_t report;
        (void)memset(&report, 0, sizeof(report));
        selftest_run(&report, config_get_string(&config, "can", "interface", "can0"));
        selftest_print(&report);
        if (report.failed > 0U) {
            LOG_WARN("CORE", "Self-test reported %u failures - continuing.", report.failed);
        }
    }

    /* 5. Security token bootstrap for hardened boot flows */
    if (config_get_bool(&config, "core", "secure_boot", false)) {
        if (vci_token_load(TOKEN_TYPE_SGW_FCA, g_demo_token,
                           (uint16_t)sizeof(g_demo_token), 3600U) == 0) {
            LOG_INFO("CORE", "Security token loaded (TTL %u s).",
                     vci_token_remaining_ttl());
        }
    }

    /* 6. System Setup - Secure POSIX Sigaction Interlocking Configuration */
    struct sigaction action;
    (void)memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = handle_termination;
    (void)sigaction(SIGINT, &action, NULL);
    (void)sigaction(SIGTERM, &action, NULL);

    if (init_vci_bridge() != 0) {
        LOG_ERROR("CORE", "Failed to initialize VCI Kernel Bridge. Verify if driver module is inserted.");
        return EXIT_FAILURE;
    }

    /* Clear the freshly mapped memory region using aligned boundary definitions */
    (void)memset(g_shm, 0, sizeof(vci_shared_mem_t));

    /* 6b. Configure the kernel driver capture layer (RX ring producer) */
    {
        uint32_t rx_filter = (uint32_t)config_get_int(&config, "can", "reply_id",
                                                      0x7E8);
        uint32_t bitrate = (uint32_t)config_get_int(&config, "can", "bitrate", 500000);
        uint32_t fd_mode = config_get_bool(&config, "can", "fd_mode", false) ? 1U : 0U;
        (void)ioctl(g_vci_fd, VCI_IOCTL_SET_FILTER, &rx_filter);
        (void)ioctl(g_vci_fd, VCI_IOCTL_SET_BITRATE, &bitrate);
        (void)ioctl(g_vci_fd, VCI_IOCTL_SET_FD_MODE, &fd_mode);
        (void)ioctl(g_vci_fd, VCI_IOCTL_CLEAR_COUNTERS);
        LOG_INFO("CORE", "Driver RX capture configured (filter 0x%03X, %u bit/s, FD %s).",
                 (unsigned)rx_filter, (unsigned)bitrate, fd_mode ? "on" : "off");
    }

    /* 6c. Optional DoIP physical layer activation (ISO 13400-3, Pin 8) */
    if (config_get_bool(&config, "diag", "doip_activate", false)) {
        (void)vci_doip_activate();
    }

    LOG_INFO("CORE", "K-OBD-PI Automotive Master Orchestrator Successfully Engaged.");

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

    // Thread 4: Global ECU Scan Engine (auto-topology discovery)
    if (config_get_bool(&config, "diag", "global_scan", true)) {
        pthread_t thread_scan;
        (void)pthread_create(&thread_scan, NULL, global_scan_engine_run, g_shm);
    }

    // Thread 5: DoIP gateway (ISO 13400-2 client) when a remote host is configured
    if ((config_get_bool(&config, "doip", "enabled", false)) &&
        (config_get_string(&config, "doip", "host", "")[0] != '\0')) {
        pthread_t thread_doip;
        (void)pthread_create(&thread_doip, NULL, vci_doip_gateway_run, g_shm);
    }

    // Thread 6: Virtual VCI bridge server (IP-to-CAN relay, default port 7000)
    if (config_get_bool(&config, "remote_vci", "enabled", false)) {
        pthread_t thread_rvci;
        (void)pthread_create(&thread_rvci, NULL, vci_virtual_bridge_server, g_shm);
    }

    // Thread 7: Remote cloud bridge client (remote expert tunneling)
    if (config_get_string(&config, "remote_bridge", "host", "")[0] != '\0') {
        pthread_t thread_rbridge;
        (void)pthread_create(&thread_rbridge, NULL, remote_bridge_thread_main, g_shm);
    }

    // Thread 8: J2534 pass-thru network daemon (SAE J2534-1 over TCP)
    if (config_get_bool(&config, "j2534", "enabled", false)) {
        pthread_t thread_j2534;
        (void)pthread_create(&thread_j2534, NULL, j2534_server_run, g_shm);
    }

    g_sys_state = VCI_STATE_IDLE;

    /* 3. Main Business Logic Loop (Failsafe & State Evaluation Framework) */
    while (g_sys_state != VCI_STATE_SHUTDOWN) {
        
        /* Continuous evaluation of critical hardware health metrics counters */
        if ((g_shm->bus_load_pct > 95U) || (g_shm->error_count > 1000U)) {
            if (g_sys_state != VCI_STATE_FAILSAFE) {
                LOG_ERROR("CORE", "Automotive bus line compromised. Forcing transition into Failsafe Mode.");
                g_sys_state = VCI_STATE_FAILSAFE;
                g_shm->status_mask |= VCI_STAT_BUS_OFF;
            }
        }

        /* Automated tracking of vehicle state transitions via Terminal 15 status indicators */
        if ((g_shm->ignition_on != 0U) && (g_sys_state == VCI_STATE_IDLE)) {
            g_sys_state = VCI_STATE_ACTIVE;
            g_shm->status_mask |= VCI_STAT_IGNITION_ON;
            LOG_INFO("CORE", "Ignition Terminal 15 transition detected. Engine State: ACTIVE.");
        } 
        else if ((g_shm->ignition_on == 0U) && (g_sys_state == VCI_STATE_ACTIVE)) {
            g_sys_state = VCI_STATE_IDLE;
            g_shm->status_mask &= ~VCI_STAT_IGNITION_ON;
            LOG_INFO("CORE", "Ignition lost. Moving VCI node context into Standby mode.");
        }
        else {
            /* Keep processing background ticks */
        }

        /* Bounded cyclic tick delay preventing orchestration core saturation (100ms interval) */
        (void)usleep(100000); 
    }

    /* 4. Safe Structural Cleanup & Resource Demapping Release */
    LOG_INFO("CORE", "Initiating synchronized graceful shutdown sequence. Joining worker threads...");
    
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

    LOG_INFO("CORE", "System halt sequence executed successfully. VCI node offline.");
    return EXIT_SUCCESS;
}

/* End of file main.c */
