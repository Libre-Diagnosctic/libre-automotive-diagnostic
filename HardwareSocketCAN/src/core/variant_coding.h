/**
 * @file src/core/variant_coding.h
 * @brief ECU Variant Coding & Adaptation interface.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef VARIANT_CODING_H
#define VARIANT_CODING_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Read-Modify-Write-Verify variant coding procedure
 * @param fd Active ISO-TP socket descriptor
 * @param did Configuration data identifier (e.g. 0xF100)
 * @param byte_offset Offset of the byte to modify
 * @param bit_mask Bits to change
 * @param new_val New bit values
 * @return 0 on success, negative on failure
 */
int vci_execute_variant_coding(int fd, uint16_t did, uint16_t byte_offset,
                               uint8_t bit_mask, uint8_t new_val);

/**
 * @brief Writes a single adaptation channel value
 */
int vci_execute_adaptation(int fd, uint16_t channel_did, uint32_t value,
                           uint8_t val_size);

#ifdef __cplusplus
}
#endif

#endif /* VARIANT_CODING_H */
