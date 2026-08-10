/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: obd_ioctl.h
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: Unified shared-memory + IOCTL interface between the kernel
 *              driver (/dev/obd_vci, /dev/obd_data) and all user-space modules.
 * REVISION: 2.0.0
 *
 * This header is intentionally self-contained so that it can be consumed by
 * both kernel-space (LKM) and user-space (POSIX) build units.
 */

#ifndef OBD_IOCTL_H
#define OBD_IOCTL_H

#include <linux/types.h>
#include <linux/ioctl.h>

/* ---------------------------------------------------------------------------
 * Legacy simple frame data structure (backwards compatible with obd_data)
 * ------------------------------------------------------------------------- */
typedef struct {
    int rpm;
    int speed;
    int temp;
    unsigned long timestamp;
} obd_data_t;

/* ---------------------------------------------------------------------------
 * System-wide architectural bound configuration
 * ------------------------------------------------------------------------- */
#define VCI_MAX_CHANNELS          8U    /* J2534 concurrent channel limit     */
#define VCI_BUFFER_SIZE           256U  /* RX ring buffer frame capacity      */
#define VCI_PID_TABLE_SIZE        256U  /* Maximum indexed PID cache entries  */
#define VCI_MAX_ECU_NODES         16U   /* Global scan inventory capacity     */
#define VCI_DTC_MAX               64U   /* DTC records per ECU node           */
#define VCI_VIN_LEN               18U   /* 17 chars + NUL                     */
#define VCI_NAME_LEN              32U   /* Node / PID label length            */
#define VCI_PAYLOAD_MAX           64U   /* CAN-FD payload capability          */
#define VCI_ISO_TP_MAX_LEN        4096U /* Maximum reassembled ISO-TP payload */

/* ---------------------------------------------------------------------------
 * Status flag bitmask definitions (status_mask register)
 * ------------------------------------------------------------------------- */
#define VCI_STAT_IGNITION_ON      0x00000001U
#define VCI_STAT_MIL_ON           0x00000002U
#define VCI_STAT_BUS_OFF          0x00000004U
#define VCI_STAT_BUS_ERROR        0x00000008U
#define VCI_STAT_LOW_VOLTAGE      0x00000010U
#define VCI_STAT_OVERHEAT         0x00000020U
#define VCI_STAT_SCANNING         0x00000040U
#define VCI_STAT_CONNECTED        0x00000080U
#define VCI_STAT_FAILSAFE         0x00000100U
#define VCI_STAT_SECURE_BOOT      0x00000200U
#define VCI_STAT_MMAP_READY       0x00000400U

/* ---------------------------------------------------------------------------
 * CAN frame abstraction (supports both classic CAN and CAN-FD)
 * ------------------------------------------------------------------------- */
typedef struct {
    uint32_t can_id;          /* 11-bit or 29-bit identifier                */
    uint8_t  dlc;             /* Data length code (0..64 for FD)            */
    uint8_t  data[VCI_PAYLOAD_MAX];
    uint8_t  is_fd;           /* 1 = CAN-FD frame                           */
    uint8_t  is_extended;     /* 1 = Extended 29-bit identifier             */
    uint8_t  is_error;        /* 1 = Error frame                            */
    uint8_t  is_rtr;          /* 1 = Remote transmission request            */
    uint32_t timestamp_ms;    /* Monotonic timestamp in milliseconds        */
} vci_frame_t;

/* ---------------------------------------------------------------------------
 * PID cache entry - raw bytes + pre-calculated engineering value
 * ------------------------------------------------------------------------- */
typedef struct {
    uint8_t  bytes[VCI_PAYLOAD_MAX];
    uint8_t  len;
    uint64_t timestamp;       /* Unix epoch at acquisition time              */
    float    calculated_value;/* Engineering unit value (already scaled)     */
    uint8_t  is_valid;
    uint8_t  reserved[3];
} vci_pid_cache_t;

/* ---------------------------------------------------------------------------
 * Discovered ECU inventory node (global scan engine result)
 * ------------------------------------------------------------------------- */
typedef struct {
    uint32_t tx_id;
    uint32_t rx_id;
    char     name[VCI_NAME_LEN];
    char     vin[VCI_VIN_LEN];
    char     calibration_id[VCI_NAME_LEN];
    uint16_t dtc_count;
    uint16_t freeze_frame_count;
    uint32_t last_seen_ms;
    uint8_t  is_active;
    uint8_t  session_type;    /* 0x01 default / 0x03 extended / 0x02 prog   */
    uint8_t  security_level;  /* Highest unlocked UDS security access level */
    uint8_t  protocol_flags;  /* Bit0 = UDS, Bit1 = WWH-OBD, Bit2 = J1939   */
    uint8_t  dtc[VCI_DTC_MAX * 3U];
} vci_ecu_node_t;

/* ---------------------------------------------------------------------------
 * Master automotive shared memory structure - mapped via /dev/obd_vci mmap
 * This is the zero-copy exchange region between the kernel driver and every
 * user-space telemetry / gateway / UI module.
 * ------------------------------------------------------------------------- */
typedef struct {
    /* System core tracking registers */
    uint32_t system_ticks;
    uint32_t status_mask;
    uint32_t error_count;
    uint32_t bus_load_pct;
    uint32_t tx_count;
    uint32_t rx_count;
    uint32_t bus_error_count;
    uint32_t overrun_count;
    uint32_t filter_hit_count;

    /* Vehicle state / physics snapshot */
    float    battery_voltage;
    float    cpu_temp;
    float    uptime_sec;
    uint32_t ignition_on;
    uint32_t mil_active;

    /* RX frame ring buffer (producer: kernel, consumer: user-space) */
    vci_frame_t rx_ring_buffer[VCI_BUFFER_SIZE];
    uint32_t head;
    uint32_t tail;

    /* Scaled PID telemetry cache indexed by PID byte */
    vci_pid_cache_t pid_db[VCI_PID_TABLE_SIZE];

    /* Freeze frame snapshot storage */
    uint8_t  freezeframe_pid;
    uint8_t  freezeframe_dtc[3];
    uint8_t  freezeframe_data[VCI_PAYLOAD_MAX];
    uint8_t  freezeframe_valid;

    /* Global scan inventory */
    vci_ecu_node_t ecu_nodes[VCI_MAX_ECU_NODES];
    uint8_t  ecu_count;

    /* Trip / statistics rolling registers */
    uint32_t trip_distance_m;
    uint32_t trip_duration_s;
    uint32_t trip_avg_speed;
    uint32_t trip_max_speed;
    uint32_t trip_fuel_ml;
    uint32_t trip_count;

    uint8_t  reserved[96U];   /* Future expansion headroom                 */
} automotive_data_t;

/* Alias used by the web/gateway/ui layer */
typedef automotive_data_t vci_shared_mem_t;

/* ---------------------------------------------------------------------------
 * IOCTL command definitions (legacy obd_data device)
 * ------------------------------------------------------------------------- */
#define OBD_MAGIC   'k'
#define SET_PID      _IOW(OBD_MAGIC, 1, int)
#define GET_ALL_DATA _IOR(OBD_MAGIC, 2, obd_data_t)

/* ---------------------------------------------------------------------------
 * VCI device command definitions (/dev/obd_vci)
 * ------------------------------------------------------------------------- */
#define VCI_MAGIC        'V'
#define VCI_IOCTL_SEND_FRAME     _IOW(VCI_MAGIC, 1, vci_frame_t)
#define VCI_IOCTL_RECV_FRAME     _IOR(VCI_MAGIC, 2, vci_frame_t)
#define VCI_IOCTL_SET_FILTER     _IOW(VCI_MAGIC, 3, uint32_t)
#define VCI_IOCTL_CLEAR_FILTERS  _IO(VCI_MAGIC, 4)
#define VCI_IOCTL_SET_BITRATE    _IOW(VCI_MAGIC, 5, uint32_t)
#define VCI_IOCTL_GET_STATS      _IOR(VCI_MAGIC, 6, automotive_data_t)
#define VCI_IOCTL_RESET_BUS      _IO(VCI_MAGIC, 7)
#define VCI_IOCTL_SET_FD_MODE    _IOW(VCI_MAGIC, 8, uint32_t)
#define VCI_IOCTL_CLEAR_COUNTERS _IO(VCI_MAGIC, 9)
#define VCI_IOCTL_SET_PID_SOURCE _IOW(VCI_MAGIC, 10, uint32_t)

#endif /* OBD_IOCTL_H */
