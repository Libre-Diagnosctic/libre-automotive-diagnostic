/**
 * @file src/core/variant_coding.c
 * @brief ECU Variant Coding & Adaptation Management (OEM Configuration)
 * @details Реализира логиката за промяна на конфигурационни байтове и адаптационни канали.
 * Поддържа трансакционен модел за запис: Read -> Modify -> Write -> Verify.
 * Стандарти: ISO 14229 (UDS Services 0x22, 0x2E).
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "../../lib/uds_iso14229.h"
#include "../../lib/iso_tp_stack.h"

#define MAX_CODING_DATA 256

/**
 * @brief Изпълнява процедура по Variant Coding на конкретен модул
 * @param fd Дескриптор на ISO-TP канала
 * @param did Идентификатор на конфигурацията (напр. 0xF100)
 * @param byte_offset Офсет на байта, който ще се променя
 * @param bit_mask Маска на битовете за промяна
 * @param new_val Нова стойност
 */
int vci_execute_variant_coding(int fd, uint16_t did, uint16_t byte_offset, uint8_t bit_mask, uint8_t new_val) {
    uint8_t buffer[MAX_CODING_DATA];
    uint16_t data_len = 0;

    printf("[CODING] Initiating Variant Coding for DID 0x%04X...\n", did);

    /* 1. Преминаване в Extended Diagnostic Session (0x03) */
    if (uds_set_session(fd, 0x03) < 0) return -1;

    /* 2. Отключване на Security Access (обикновено Level 0x01 или OEM специфичен) */
    // if (vci_security_unlock(fd, 0x01) != 0) return -2;

    /* 3. Прочитане на текущата конфигурация (Read Data By Identifier) */
    if (uds_read_data_by_id(fd, did) < 0) return -3;
    
    int len = isotp_stack_receive(fd, buffer, MAX_CODING_DATA);
    if (len <= 3 || buffer[0] != 0x62) return -4; // 0x62 = Positive Response

    data_len = len - 3;
    uint8_t *coding_data = &buffer[3];

    /* 4. Модификация на битовете (Modify) */
    if (byte_offset >= data_len) return -5;
    
    coding_data[byte_offset] &= ~bit_mask;          /* Изчистване на старите битове */
    coding_data[byte_offset] |= (new_val & bit_mask); /* Прилагане на новите битове */

    /* 5. Запис на новата конфигурация (Write Data By Identifier - 0x2E) */
    printf("[CODING] Writing modified data to ECU...\n");
    if (uds_write_data_by_id(fd, did, coding_data, data_len) < 0) return -6;

    /* 6. Потвърждение на записа */
    len = isotp_stack_receive(fd, buffer, MAX_CODING_DATA);
    if (len >= 3 && buffer[0] == 0x6E) { // 0x6E = Positive Write Response
        printf("[CODING] Success! ECU updated and coding applied.\n");
        return 0;
    }

    fprintf(stderr, "[CODING] Write failed or rejected by ECU.\n");
    return -7;
}

/**
 * @brief Изпълнява адаптация (промяна на единичен параметър/канал)
 * @param fd Дескриптор
 * @param channel_did DID на адаптационния канал
 * @param value Нова стойност на параметъра
 */
int vci_execute_adaptation(int fd, uint16_t channel_did, uint32_t value, uint8_t val_size) {
    uint8_t payload[4];
    
    /* Подготовка на Big-endian стойноста */
    for (int i = 0; i < val_size; i++) {
        payload[val_size - 1 - i] = (uint8_t)(value >> (i * 8));
    }

    printf("[ADAPTATION] Setting Channel 0x%04X to value %u...\n", channel_did, value);
    
    return uds_write_data_by_id(fd, channel_did, payload, val_size);
}

/* Край на файл variant_coding.c */
