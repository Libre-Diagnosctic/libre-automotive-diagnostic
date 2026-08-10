/**
 * @file src/core/doip_activator.h
 * @brief DoIP physical layer activation + gateway (ISO 13400-2/3).
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#ifndef DOIP_ACTIVATOR_H
#define DOIP_ACTIVATOR_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Applies the DoIP activation signal (ISO 13400-3, Pin 8)
 * @return 0 on success
 */
int vci_doip_activate(void);

/**
 * @brief Deactivates the DoIP physical layer
 */
void vci_doip_deactivate(void);

/**
 * @brief Background DoIP gateway thread (client) - relays UDS over IP to CAN
 */
void *vci_doip_gateway_run(void *arg);

#ifdef __cplusplus
}
#endif

#endif /* DOIP_ACTIVATOR_H */
