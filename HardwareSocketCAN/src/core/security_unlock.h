/**
 * @file src/core/security_unlock.h
 * @brief UDS Security Access (Service 0x27) unlock interface.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef SECURITY_UNLOCK_H
#define SECURITY_UNLOCK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Runs the full seed-key unlock procedure on an ISO-TP channel
 * @param fd Active ISO-TP socket descriptor
 * @param level Security access level (typically 0x01 or 0x03)
 * @return 0 on success, negative on failure
 */
int vci_security_unlock(int fd, uint8_t level);

#ifdef __cplusplus
}
#endif

#endif /* SECURITY_UNLOCK_H */
