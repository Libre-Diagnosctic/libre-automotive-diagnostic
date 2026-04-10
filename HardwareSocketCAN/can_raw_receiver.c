/*
 * Module: can_raw_receiver.c
 * Description: Low-level raw frame acquisition via SocketCAN.
 * Standard: ISO 11898-1
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>

int main(int argc, char *argv[]) {
    int s;
    struct sockaddr_can addr;
    struct ifreq ifr;
    struct can_frame frame;
    const char *ifname = "can0";

    // 1. Създаване на RAW CAN сокет
    if ((s = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) {
        perror("Socket Error");
        return 1;
    }

    // 2. Свързване с интерфейса (напр. can0)
    strcpy(ifr.ifr_name, ifname);
    ioctl(s, SIOCGIFINDEX, &ifr);

    memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("Bind Error");
        return 1;
    }

    printf("Listening for raw frames on %s...\n", ifname);

    // 3. Безкраен цикъл за четене на сурови данни
    while (1) {
        int nbytes = read(s, &frame, sizeof(struct can_frame));

        if (nbytes < 0) {
            perror("Read Error");
            break;
        }

        // Печат на суровия кадър в конзолата
        printf("ID: 0x%03X | DLC: %d | Data: ", frame.can_id, frame.can_dlc);
        for (int i = 0; i < frame.can_dlc; i++) {
            printf("%02X ", frame.data[i]);
        }
        printf("\n");
    }

    close(s);
    return 0;
}
