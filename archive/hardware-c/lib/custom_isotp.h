/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: custom_isotp.h
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 1.0.0
 */


#ifndef CUSTOM_ISOTP_H
#define CUSTOM_ISOTP_H
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h> 
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/can.h>
#include <linux/can/isotp.h>

static int isotp_open(const char *ifname, uint32_t tx_id, uint32_t rx_id) {
    int s = socket(PF_CAN, SOCK_DGRAM, CAN_ISOTP);
    struct ifreq ifr;
    strcpy(ifr.ifr_name, ifname);
    ioctl(s, SIOCGIFINDEX, &ifr);
    struct sockaddr_can addr = { .can_family = AF_CAN, .can_ifindex = ifr.ifr_ifindex, 
                                 .can_addr.tp = { .tx_id = tx_id, .rx_id = rx_id } };
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) return -1;
    return s;
}
#endif
