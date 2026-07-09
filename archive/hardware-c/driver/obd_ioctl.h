/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: obd_ioctl.h
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 1.0.0
 */


#ifndef OBD_IOCTL_H
#define OBD_IOCTL_H
#include <linux/ioctl.h>

typedef struct {
    int rpm;
    int speed;
    int temp;
    unsigned long timestamp;
} obd_data_t;

#define OBD_MAGIC 'k'
#define SET_PID      _IOW(OBD_MAGIC, 1, int)
#define GET_ALL_DATA _IOR(OBD_MAGIC, 2, obd_data_t)
#endif
