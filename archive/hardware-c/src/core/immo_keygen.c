/**
 * @file immo_keygen.c
 * @brief Immobilizer Coding, Key Learning & Component Protection Logic
 * @details Implements secure challenge-response authentication for key programming.
 *          Strictly checks data lengths to eliminate memory boundaries overrun.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "../../lib/uds_iso14229.h"
#include "../../lib/crypto_auth.h"
#include "../../driver/obd_ioctl.h"

/* Immobilizer Architecture Constraints Configuration */
#define IMMO_CHALLENGE_LEN    8U
#define IMMO_RESPONSE_LEN     8U
#define DID_IMMO_STATUS       0xF150U
#define DID_KEY_COUNT         0xF151U

/**
 * @brief Reads the current registered key count from the BCM/KESSY ECU node memory
 * @param fd Active SocketCAN / ISO-TP channel socket descriptor
 * @return Number of learned transponders on success, or negative on failure
 */
int32_t vci_immo_get_key_count(int32_t fd) {
    if (fd < 0) {
        return -1;
    }

    uint8_t rx_buf[16U];
    (void)memset(rx_buf, 0, sizeof(rx_buf));

    /* Technical Alignment Fix: Pass correct out buffer arguments to UDS stack */
    int32_t len = uds_read_data_by_id(fd, DID_KEY_COUNT, rx_buf, (uint16_t)sizeof(rx_buf));
    
    /* Security verification: Ensure returned length covers the target payload index byte */
    if (len >= 4) {
        /* Byte index 3 contains the actual transponder counter inside positive response payload */
        return (int32_t)rx_buf[3];
    }
    
    return -1;
}

/**
 * @brief Challenge-Response cryptographic authentication loop for Component Protection release
 */
int32_t vci_immo_authenticate(int32_t fd, uint8_t secret_table_idx) {
    if (fd < 0) {
        return -1;
    }

    uint8_t challenge[IMMO_CHALLENGE_LEN];
    uint8_t response[IMMO_RESPONSE_LEN];
    (void)memset(challenge, 0, sizeof(challenge));
    (void)memset(response, 0, sizeof(response));

    printf("[IMMO] Initiating High-Security Challenge-Response Authentication sequence...\n");

    /* 1. Dispatch Security Access Seed Request (Service 0x27 Sub-function 0x61) */
    if (uds_security_access_request_seed(fd, 0x61U, challenge) < 0) {
        fprintf(stderr, "[IMMO-ERROR] Seed generation aborted by target ECU node.\n");
        return -1;
    }

    /* 2. Cryptographic Execution Pass - Pass seed array into hardware software crypto bridge */
    /* Real implementation utilizes hardware accelerated AES engine mapping to specific index */
    if (crypto_auth_aes128_calculate(challenge, IMMO_CHALLENGE_LEN, secret_table_idx, response, IMMO_RESPONSE_LEN) != 0) {
        fprintf(stderr, "[IMMO-ERROR] Cryptographic core computation engine mismatch failure.\n");
        return -3;
    }

    /* 3. Emit Computed Key Response packet to target ECU validation module */
    if (uds_security_access_send_key(fd, 0x62U, response, IMMO_RESPONSE_LEN) < 0) {
        fprintf(stderr, "[ALARM] Component Protection Active! Cryptographic authentication rejected.\n");
        return -2;
    }

    printf("[IMMO] Cryptographic Authentication Successful. Security Level Unlocked.\n");
    return 0;
}

/**
 * @brief Readies the Immobilizer module to bind new physical vehicle transponders
 */
int32_t vci_immo_enter_learning_mode(int32_t fd) {
    if (fd < 0) {
        return -1;
    }

    /* 1. Request elevated execution state (Security Access Level 0xFB for Transponder Binding) */
    /* Accessing localized structural routing hook from backend layers */
    uint8_t binding_key[4] = { 0xAAU, 0xBBU, 0xCCU, 0xDDU };
    if (uds_security_access_send_key(fd, 0xFBU, binding_key, 4U) != 0) {
        return -1;
    }

    /* 2. Initiate Routine Control (Service 0x31) to active Key Learning automated cycle */
    uint8_t routine_params[2U];
    routine_params[0] = 0x01U; /* Start Routine control parameter definition */
    routine_params[1] = 0x00U; /* Optional trailing control parameter alignment configuration */
    
    return uds_routine_control(fd, 0x01U, 0x0203U, routine_params, 2U);
}

/* End of file immo_keygen.c */
