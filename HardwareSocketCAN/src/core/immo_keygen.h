/**
 * @file src/core/immo_keygen.h
 * @brief Immobilizer / Component Protection interface.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef IMMO_KEYGEN_H
#define IMMO_KEYGEN_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Reads the registered transponder key count (DID 0xF151)
 */
int32_t vci_immo_get_key_count(int32_t fd);

/**
 * @brief Challenge-response authentication for component protection release
 */
int32_t vci_immo_authenticate(int32_t fd, uint8_t secret_table_idx);

/**
 * @brief Enters immobilizer key learning mode (routine 0x0203)
 */
int32_t vci_immo_enter_learning_mode(int32_t fd);

#ifdef __cplusplus
}
#endif

#endif /* IMMO_KEYGEN_H */
