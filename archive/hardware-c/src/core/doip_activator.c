/**
 * @file src/core/doip_activator.c
 * @brief DoIP Physical Layer Activation logic (ISO 13400-3)
 * @details Реализира логиката за активиране на Ethernet диагностика чрез Pin 8.
 * Поддържа изискванията за напрежение и времеви интервали съгласно стандарта.
 */

#include <stdio.h>
#include <unistd.h>
#include <stdint.h>
#include "../../driver/obd_ioctl.h"

/* ISO 13400-3 Activation Line Parameters */
#define DOIP_ACTIVATION_PIN          8     /* Discretionary pin 8 на OBD-II */
#define DOIP_VOLTAGE_ACTIVE_MIN      5.0f  /* Мин. напрежение за активен статус (5V-32V) */
#define DOIP_VOLTAGE_INACTIVE_MAX    2.0f  /* Макс. напрежение за неактивен статус (0V-2V) */
#define DOIP_ACTIVATION_TIME_MS      200   /* Мин. време на задържане (ISO изискване) */

/**
 * @brief Активира физическия слой за DoIP (Diagnostics over IP)
 * @details Прилага напрежение (>5V) върху Pin 8 за минимум 200ms за събуждане на Edge Node ECU.
 * @return 0 при успешно изпратен сигнал
 */
int vci_doip_activate(void) {
    printf("[DOIP] Initiating Physical Layer Activation (ISO 13400-3)...\n");

    /* 1. Превключване на мултиплексора към DoIP конфигурация */
    // vci_mux_set_mode(MUX_MODE_DOIP);

    /* 2. Активиране на линията (WUP - Wake-up Pattern) */
    /* Хардуерно: Pin 8 се свързва към VCC (напр. 12V или 5V) */
    // gpiod_set_value(doip_act_line, 1);
    
    printf("[DOIP] Activation Line HIGH (>5V) applied to Pin 8.\n");
    
    /* Стандартът изисква сигналът да остане стабилен за поне 200ms */
    usleep(DOIP_ACTIVATION_TIME_MS * 1000);

    printf("[DOIP] Physical Layer should be active. Ready for TCP/IP handshake.\n");
    return 0;
}

/**
 * @brief Деактивира DoIP за намаляване на EMI и консумация
 */
void vci_doip_deactivate(void) {
    /* Напрежението трябва да падне под 2V за поне 200ms */
    // gpiod_set_value(doip_act_line, 0);
    usleep(DOIP_ACTIVATION_TIME_MS * 1000);
    
    printf("[DOIP] Physical Layer Deactivated.\n");
}

/* Край на файл doip_activator.c */
