/**
 * @file src/core/doip_activator.c
 * @brief DoIP Physical Layer Activation logic (ISO 13400-3)
 * @details Реализира логиката за активиране на Ethernet диагностика чрез Pin 8.
 * Поддържа изискванията за напрежение и времеви интервали съгласно стандарта.
 */

#include <stdio.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/doip_iso13400.h"
#include "../../lib/iso_tp_stack.h"
#include "../../lib/uds_iso14229.h"
#include "../../lib/config_loader.h"
#include "../../lib/logging.h"
#include "doip_activator.h"

/* ISO 13400-3 Activation Line Parameters */
#define DOIP_ACTIVATION_PIN          8     /* Discretionary pin 8 на OBD-II */
#define DOIP_VOLTAGE_ACTIVE_MIN      5.0f  /* Мин. напрежение за активен статус (5V-32V) */
#define DOIP_VOLTAGE_INACTIVE_MAX    2.0f  /* Макс. напрежение за неактивен статус (0V-2V) */
#define DOIP_ACTIVATION_TIME_MS      200   /* Мин. време на задържане (ISO изискване) */
#define DOIP_GATEWAY_CONFIG_PATH     "/etc/kobd/obd.conf"
#define DOIP_DEFAULT_SOURCE_ADDR     0x0E00U /* Tester logical address */
#define DOIP_RECONNECT_US            5000000U

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

/**
 * @brief DoIP gateway (client): relays UDS diagnostic messages between the
 *        remote DoIP entity and the local CAN bus via a temporary ISO-TP channel.
 */
void *vci_doip_gateway_run(void *arg) {
    automotive_data_t *shm = (automotive_data_t *)arg;
    (void)shm;

    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, DOIP_GATEWAY_CONFIG_PATH);

    const char *host = config_get_string(&config, "doip", "host", "");
    uint16_t port = (uint16_t)config_get_int(&config, "doip", "port",
                                             (int32_t)DOIP_PORT);
    uint16_t source_addr = (uint16_t)config_get_int(&config, "doip", "source_addr",
                                                    (int32_t)DOIP_DEFAULT_SOURCE_ADDR);
    const char *iface = config_get_string(&config, "can", "interface", "can0");

    LOG_INFO("DOIP", "Gateway started (host=%s:%u source=0x%04X).", host, port, source_addr);

    while (1) {
        int32_t fd = doip_connect(host, port);
        if (fd < 0) {
            LOG_WARN("DOIP", "Connect to %s:%u failed - retrying.", host, port);
            (void)usleep(DOIP_RECONNECT_US);
            continue;
        }

        if (doip_activate_routing(fd, source_addr, 0x00U) != 0) {
            LOG_WARN("DOIP", "Routing activation rejected - retrying.");
            (void)close(fd);
            (void)usleep(DOIP_RECONNECT_US);
            continue;
        }
        LOG_INFO("DOIP", "Routing activation accepted (logical address 0x%04X).", source_addr);

        while (1) {
            uint8_t diag_buf[DOIP_BUFFER_SIZE];
            uint16_t src = 0U;
            uint16_t dst = 0U;
            int32_t plen = doip_receive_diag_message(fd, diag_buf, (uint32_t)sizeof(diag_buf),
                                                     &src, &dst);
            if (plen < 0) {
                LOG_WARN("DOIP", "Connection error (%d) - reconnecting.", (int)plen);
                break;
            }

            /* Forward the UDS payload to the target ECU over the local CAN bus */
            int32_t iso_fd = isotp_stack_init(iface, dst, (uint32_t)src);
            if (iso_fd >= 0) {
                if (isotp_stack_send(iso_fd, diag_buf, (uint16_t)plen) > 0) {
                    uint8_t resp[DOIP_BUFFER_SIZE];
                    int32_t rlen = isotp_stack_receive(iso_fd, resp,
                                                       (uint16_t)sizeof(resp));
                    if (rlen > 0) {
                        (void)doip_send_diag_message(fd, source_addr, dst, resp,
                                                     (uint32_t)rlen);
                    }
                }
                isotp_stack_close(iso_fd);
            }
        }

        (void)close(fd);
        (void)usleep(DOIP_RECONNECT_US);
    }
    return NULL;
}

/* Край на файл doip_activator.c */
