/**
 * @file src/gateway/secure_server.h
 * @brief Header specification for the TLS 1.3 Secure API Component
 * @details Defines the strictly aligned network packet layouts and entry
 *          points for the hardened binary communication subsystem.
 * Standards: MISRA-C:2012, ASIL-D Topology Compliant
 */

#ifndef SECURE_SERVER_H
#define SECURE_SERVER_H

#include <stdint.h>
#include <stdbool.h>
#include "../../driver/obd_ioctl.h" /* For vci_shared_mem_t definition */

/* Hardened Network Configuration Parameters */
#define SECURE_API_PORT         8888U
#define MAX_PENDING_CONNS       5U
#define AUTH_TOKEN_EXPECTED     "K-OBD-VCI-PRO-2026"
#define VCI_NET_SYNC_WORD       0xAA55AA55U
#define VCI_NET_PAYLOAD_MAX     2048U

/**
 * @struct vci_api_packet_t
 * @brief Strictly aligned byte-accurate binary application layer packet protocol
 * @details Enforces a pack boundary of 1 byte to prevent compiler padding bits
 *          and ensure deterministic cross-platform deserialization (Android/Linux).
 */
#pragma pack(push, 1)
typedef struct {
    uint32_t sync_word;                       /**< Framing token: Always VCI_NET_SYNC_WORD */
    uint16_t version;                         /**< API protocol runtime layout version tracking */
    uint16_t command_id;                      /**< Diagnostic service operation token mapping */
    uint32_t payload_len;                     /**< Bounded size configuration array validation check */
    uint8_t  payload[VCI_NET_PAYLOAD_MAX];    /**< Memory-isolated static data transmission payload */
    uint32_t crc32;                           /**< Integrity confirmation IEEE 802.3 validation mark */
} vci_api_packet_t;
#pragma pack(pop)

/**
 * @brief Main execution entry point for the Secure TLS 1.3 Network Daemon
 * @param arg Pointer to the global vci_shared_mem_t zero-copy context allocation
 * @return void* Standard POSIX thread exit status context identifier
 */
void *secure_server_run(void *arg);

/**
 * @brief Global CRC32 IEEE 802.3 calculation subroutine for binary ingestion shielding
 * @param data Pointer to the continuous target byte array memory address location
 * @param length Byte size bound configuration integer driving loop tracking
 * @return uint32_t Computed bitwise residual checksum verification block
 */
uint32_t crc32_compute(const uint8_t *data, uint32_t length);

#endif /* SECURE_SERVER_H */
