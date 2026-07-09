/**
 * @file driver/can_fd_support.c
 * @brief CAN-FD (Flexible Data-rate) Stack implementation for MCP2518FD
 * @details Handles 64-byte payload mapping and Bit Rate Switch (BRS) logic for modern ECUs.
 */

#include <linux/can/fd.h>
#include <linux/can/dev.h>
#include <linux/skbuff.h>
#include "obd_ioctl.h"

/**
 * @brief Преобразува стандартен CAN_RAW пакет в CAN-FD рамка
 * @param fd_frame Указател към структурата за запълване
 * @param id CAN Идентификатор (поддържа Extended 29-bit)
 * @param data Указател към данните (до 64 байта)
 * @param len Дължина на полезния товар (DLC)
 */
void vci_can_fd_prepare_frame(struct canfd_frame *fd_frame, uint32_t id, const uint8_t *data, uint8_t len) {
    if (!fd_frame || !data) return;

    /* Изчистване на паметта съгласно MISRA-C */
    memset(fd_frame, 0, sizeof(struct canfd_frame));

    /* Настройка на ID и Extended флага ако е необходимо */
    if (id > 0x7FF) {
        fd_frame->can_id = id | CAN_EFF_FLAG;
    } else {
        fd_frame->can_id = id;
    }

    /* Настройка на CAN-FD специфични флагове */
    fd_frame->flags = CANFD_BRS | CANFD_FDF; /* Bit Rate Switch + FD Format */
    
    /* Валидация на дължината - CAN-FD поддържа до 64 байта */
    uint8_t dlc = (len > 64) ? 64 : len;
    fd_frame->len = dlc;

    /* Копиране на данните в буфера на рамката */
    memcpy(fd_frame->data, data, dlc);
}

/**
 * @brief Валидира дължината на CAN-FD според ISO 11898-1:2015 DLC таблица
 * @param len Дължина в байтове
 * @return Реалната DLC стойност
 */
uint8_t vci_can_fd_len_to_dlc(uint8_t len) {
    if (len <= 8)  return len;
    if (len <= 12) return 9;
    if (len <= 16) return 10;
    if (len <= 20) return 11;
    if (len <= 24) return 12;
    if (len <= 32) return 13;
    if (len <= 48) return 14;
    return 15; /* 64 bytes */
}

/**
 * @brief Проверява дали входящият skb пакет е CAN-FD
 * @param skb Мрежов буфер от ядрото
 * @return true ако е FD
 */
bool vci_is_fd_packet(struct sk_buff *skb) {
    if (!skb) return false;
    /* Проверка на флаговете в can_skb_priv */
    return (skb->len == CANFD_MTU);
}

/* Край на файл can_fd_support.c */
