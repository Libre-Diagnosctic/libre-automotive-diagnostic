/**
 * @file src/core/security_unlock.c
 * @brief Implementation of Seed-Key Authentication & Security Gateway (SGW) Unlocking
 * @details Реализира ISO 14229 Service 0x27 за достъп до защитени функции.
 * Включва поддръжка за алгоритми с маскиране и подготовка за Token-based Auth.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "../../lib/uds_iso14229.h"
#include "../../lib/iso_tp_stack.h"

/* Стандартни нива на сигурност съгласно ISO 14229 */
#define UDS_SEC_LEVEL_L1_REQ_SEED 0x01
#define UDS_SEC_LEVEL_L1_SEND_KEY 0x02
#define UDS_SEC_LEVEL_L3_REQ_SEED 0x03
#define UDS_SEC_LEVEL_L3_SEND_KEY 0x04

/**
 * @brief Генерира ключ от получения seed (Примерен OEM алгоритъм)
 * @param seed Полученият от ECU-то 4-байтов seed
 * @param secret_mask Системен таен ключ
 */
static uint32_t vci_calculate_key(uint32_t seed, uint32_t secret_mask) {
    uint32_t key = seed ^ secret_mask;
    /* Примерна битова ротация за повишаване на ентропията */
    key = (key << 5) | (key >> 27);
    key += 0x12345678;
    return key;
}

/**
 * @brief Изпълнява пълната процедура по отключване на Security Access
 * @param fd Дескриптор на ISO-TP сокета
 * @param level Ниво на достъп (обикновено 0x01 или 0x03)
 */
int vci_security_unlock(int fd, uint8_t level) {
    uint8_t rx_buf[256];
    uint32_t seed = 0;
    uint32_t key = 0;

    printf("[SECURITY] Initiating Unlock Sequence for Level 0x%02X...\n", level);

    /* 1. Request Seed (Sub-function must be ODD) */
    uint8_t req_seed[] = { 0x27, level };
    if (isotp_stack_send(fd, req_seed, 2) <= 0) return -1;

    int len = isotp_stack_receive(fd, rx_buf, sizeof(rx_buf));
    if (len < 6 || rx_buf[0] != 0x67 || rx_buf[1] != level) {
        fprintf(stderr, "[SECURITY] Failed to receive valid Seed.\n");
        return -2;
    }

    /* Извличане на Seed-а от отговора (байтове 2-5) */
    memcpy(&seed, &rx_buf[2], 4);
    seed = ntohl(seed); /* Корекция на endianness */

    /* Проверка дали е вече отключено */
    if (seed == 0x00000000) {
        printf("[SECURITY] ECU already unlocked.\n");
        return 0;
    }

    /* 2. Calculate Key */
    key = vci_calculate_key(seed, 0xACE0BADE);
    uint32_t key_be = htonl(key);

    /* 3. Send Key (Sub-function must be EVEN: level + 1) */
    uint8_t send_key[6];
    send_key[0] = 0x27;
    send_key[1] = level + 1;
    memcpy(&send_key[2], &key_be, 4);

    if (isotp_stack_send(fd, send_key, 6) <= 0) return -3;

    len = isotp_stack_receive(fd, rx_buf, sizeof(rx_buf));
    if (len >= 2 && rx_buf[0] == 0x67 && rx_buf[1] == (level + 1)) {
        printf("[SECURITY] Access Granted! Level 0x%02X active.\n", level);
        return 0;
    }

    fprintf(stderr, "[SECURITY] Access Denied (Invalid Key).\n");
    return -4;
}

/* Край на файл security_unlock.c */
