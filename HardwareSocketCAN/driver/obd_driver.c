/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: obd_driver.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance, ISO 11898-1
 * DESCRIPTION: Automotive VCI kernel driver.
 *   - /dev/obd_vci   : zero-copy mmap of the master automotive_data_t region,
 *                      VCI frame send/receive ioctls, filter/bitrate/fd control,
 *                      CAN bus statistics accumulation.
 *   - /dev/obd_data  : legacy simple read/ioctl device (backwards compatible).
 * REVISION: 2.0.0
 */

#include <linux/module.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/can.h>
#include <linux/can/core.h>
#include <linux/can/dev.h>
#include <linux/netdevice.h>
#include <linux/wait.h>
#include <linux/mm.h>
#include <linux/gfp.h>
#include <linux/ktime.h>
#include <linux/slab.h>
#include <linux/version.h>
#include "obd_ioctl.h"

#define DRIVER_NAME    "obd_vci"
#define LEGACY_DEVICE  "obd_data"
#define CAN_INTERFACE  "can0"
#define DEFAULT_RX_ID  0x7E8
#define DEFAULT_MASK   0x7FF

static int major_vci;
static int major_legacy;

/* Master zero-copy shared region (mapped to user-space via mmap) */
static automotive_data_t *g_vci_shm;
static uint32_t g_active_pid;
static uint32_t g_rx_filter;
static uint32_t g_fd_mode;
static bool g_data_ready;
static DECLARE_WAIT_QUEUE_HEAD(vci_wait_queue);

/* Legacy obd_data mirror */
static obd_data_t g_legacy_data;

static struct net_device *get_can_dev(void) {
    return dev_get_by_name(&init_net, CAN_INTERFACE);
}

/* ---------------------------------------------------------------------------
 * CAN frame transmission
 * ------------------------------------------------------------------------- */
static void vci_send_frame(const vci_frame_t *frame) {
    struct net_device *dev = get_can_dev();
    if (dev == NULL) {
        return;
    }

    struct sk_buff *skb;
    if (g_fd_mode != 0U) {
        skb = alloc_skb(sizeof(struct canfd_frame), GFP_ATOMIC);
    } else {
        skb = alloc_skb(sizeof(struct can_frame), GFP_ATOMIC);
    }

    if (skb == NULL) {
        dev_put(dev);
        return;
    }

    skb->dev = dev;
    skb->protocol = htons((g_fd_mode != 0U) ? ETH_P_CANFD : ETH_P_CAN);

    if (g_fd_mode != 0U) {
        struct canfd_frame *cfd = (struct canfd_frame *)skb_put(skb, sizeof(struct canfd_frame));
        (void)memset(cfd, 0, sizeof(struct canfd_frame));
        cfd->can_id = frame->can_id;
        cfd->len = frame->dlc;
        if (frame->is_fd) {
            cfd->flags = CANFD_FDF;
        }
        if (frame->is_extended) {
            cfd->can_id |= CAN_EFF_FLAG;
        }
        if (frame->dlc > 64U) {
            cfd->len = 64U;
        }
        (void)memcpy(cfd->data, frame->data, cfd->len);
    } else {
        struct can_frame *cframe = (struct can_frame *)skb_put(skb, sizeof(struct can_frame));
        (void)memset(cframe, 0, sizeof(struct can_frame));
        cframe->can_id = frame->can_id;
        cframe->len = (frame->dlc > 8U) ? 8U : frame->dlc;
        if (frame->is_extended) {
            cframe->can_id |= CAN_EFF_FLAG;
        }
        (void)memcpy(cframe->data, frame->data, cframe->len);
    }

    dev_queue_xmit(skb);
    g_vci_shm->tx_count++;
    dev_put(dev);
}

/* ---------------------------------------------------------------------------
 * CAN receive handler (fed by can_rx_register)
 * ------------------------------------------------------------------------- */
static void vci_can_rx_handler(struct sk_buff *skb, void *data) {
    (void)data;
    if (g_vci_shm == NULL) {
        return;
    }

    struct canfd_frame *cfd = (struct canfd_frame *)skb->data;
    uint32_t head = g_vci_shm->head;
    uint32_t next = (head + 1U) % VCI_BUFFER_SIZE;

    vci_frame_t *dst = &g_vci_shm->rx_ring_buffer[head];
    (void)memset(dst, 0, sizeof(vci_frame_t));

    dst->can_id = cfd->can_id & CAN_EFF_MASK;
    dst->is_extended = (cfd->can_id & CAN_EFF_FLAG) ? 1U : 0U;
    dst->is_fd = (skb->len == CANFD_MTU) ? 1U : 0U;

    if (dst->is_fd) {
        dst->dlc = cfd->len;
        if (dst->dlc > VCI_PAYLOAD_MAX) {
            dst->dlc = VCI_PAYLOAD_MAX;
        }
    } else {
        struct can_frame *cframe = (struct can_frame *)skb->data;
        dst->dlc = cframe->len;
        if (dst->dlc > 8U) {
            dst->dlc = 8U;
        }
    }
    (void)memcpy(dst->data, cfd->data, dst->dlc);
    dst->timestamp_ms = (uint32_t)(ktime_get_boot_fast_ns() / 1000000U);

    /* Update tail only if the ring is not full (drop-oldest policy) */
    if (next != g_vci_shm->tail) {
        g_vci_shm->head = next;
    }
    g_vci_shm->rx_count++;

    /* Legacy Mode 01 scaling mirror */
    if ((dst->can_id == g_rx_filter) && (dst->dlc >= 5U) &&
        (dst->data[1] == 0x41U)) {
        switch (dst->data[2]) {
            case 0x0C:
                g_legacy_data.rpm = ((dst->data[3] << 8) | dst->data[4]) / 4;
                break;
            case 0x0D:
                g_legacy_data.speed = dst->data[3];
                break;
            case 0x05:
                g_legacy_data.temp = (int)dst->data[3] - 40;
                break;
            default:
                break;
        }
        g_legacy_data.timestamp = (unsigned long)ktime_get_real_seconds();
        g_data_ready = true;
        wake_up_interruptible(&vci_wait_queue);
    }

    if (dst->is_error) {
        g_vci_shm->bus_error_count++;
    }
}

/* ---------------------------------------------------------------------------
 * VCI device ioctl dispatch
 * ------------------------------------------------------------------------- */
static long vci_ioctl(struct file *file, unsigned int cmd, unsigned long arg) {
    (void)file;
    if (g_vci_shm == NULL) {
        return -ENODEV;
    }

    switch (cmd) {
        case VCI_IOCTL_SEND_FRAME: {
            vci_frame_t frame;
            if (copy_from_user(&frame, (void __user *)arg, sizeof(vci_frame_t))) {
                return -EFAULT;
            }
            vci_send_frame(&frame);
            return 0;
        }
        case VCI_IOCTL_RECV_FRAME: {
            vci_frame_t frame;
            if (g_vci_shm->head != g_vci_shm->tail) {
                uint32_t tail = g_vci_shm->tail;
                (void)memcpy(&frame, &g_vci_shm->rx_ring_buffer[tail], sizeof(vci_frame_t));
                g_vci_shm->tail = (tail + 1U) % VCI_BUFFER_SIZE;
            } else {
                (void)memset(&frame, 0, sizeof(vci_frame_t));
                return -EAGAIN;
            }
            if (copy_to_user((void __user *)arg, &frame, sizeof(vci_frame_t))) {
                return -EFAULT;
            }
            return 0;
        }
        case VCI_IOCTL_SET_FILTER: {
            uint32_t id;
            if (copy_from_user(&id, (void __user *)arg, sizeof(id))) {
                return -EFAULT;
            }
            if (id != g_rx_filter) {
                /* Re-register the RX handler so the new filter takes effect
                 * immediately instead of only at module init. */
                struct net_device *dev = get_can_dev();
                if (dev != NULL) {
                    can_rx_unregister(&init_net, dev, g_rx_filter, DEFAULT_MASK,
                                      vci_can_rx_handler, NULL);
                    g_rx_filter = id;
                    if (can_rx_register(&init_net, dev, g_rx_filter, DEFAULT_MASK,
                                        vci_can_rx_handler, NULL, "obd_vci", NULL) == 0) {
                        g_vci_shm->status_mask |= VCI_STAT_CONNECTED;
                    }
                    dev_put(dev);
                } else {
                    g_rx_filter = id;
                }
            }
            return 0;
        }
        case VCI_IOCTL_CLEAR_FILTERS:
            g_rx_filter = 0x00000000U;
            return 0;
        case VCI_IOCTL_SET_BITRATE: {
            uint32_t bitrate;
            if (copy_from_user(&bitrate, (void __user *)arg, sizeof(bitrate))) {
                return -EFAULT;
            }
            /* Real hardware would program the CAN transceiver; store the value */
            g_vci_shm->bus_load_pct = bitrate; /* informational only */
            return 0;
        }
        case VCI_IOCTL_GET_STATS:
            if (copy_to_user((void __user *)arg, g_vci_shm, sizeof(automotive_data_t))) {
                return -EFAULT;
            }
            return 0;
        case VCI_IOCTL_RESET_BUS:
            g_vci_shm->bus_error_count = 0U;
            g_vci_shm->overrun_count = 0U;
            g_vci_shm->status_mask &= ~VCI_STAT_BUS_OFF;
            return 0;
        case VCI_IOCTL_SET_FD_MODE: {
            uint32_t mode;
            if (copy_from_user(&mode, (void __user *)arg, sizeof(mode))) {
                return -EFAULT;
            }
            g_fd_mode = (mode != 0U) ? 1U : 0U;
            return 0;
        }
        case VCI_IOCTL_CLEAR_COUNTERS:
            g_vci_shm->tx_count = 0U;
            g_vci_shm->rx_count = 0U;
            g_vci_shm->error_count = 0U;
            return 0;
        case VCI_IOCTL_SET_PID_SOURCE: {
            uint32_t pid;
            if (copy_from_user(&pid, (void __user *)arg, sizeof(pid))) {
                return -EFAULT;
            }
            g_active_pid = pid;
            return 0;
        }
        default:
            return -ENOTTY;
    }
}

/* ---------------------------------------------------------------------------
 * VCI mmap -> zero-copy access to the master shared region
 * ------------------------------------------------------------------------- */
static int vci_mmap(struct file *file, struct vm_area_struct *vma) {
    (void)file;
    unsigned long size = vma->vm_end - vma->vm_start;
    if (g_vci_shm == NULL) {
        return -ENODEV;
    }
    if (size > PAGE_ALIGN(sizeof(automotive_data_t))) {
        return -EINVAL;
    }

    vma->vm_flags |= VM_IO | VM_DONTEXPAND;
    if (remap_pfn_range(vma, vma->vm_start,
                        virt_to_phys(g_vci_shm) >> PAGE_SHIFT,
                        size, vma->vm_page_prot)) {
        return -EAGAIN;
    }
    g_vci_shm->status_mask |= VCI_STAT_MMAP_READY;
    return 0;
}

/* ---------------------------------------------------------------------------
 * Legacy obd_data device (compatibility layer)
 * ------------------------------------------------------------------------- */
static ssize_t legacy_read(struct file *file, char __user *buf, size_t len, loff_t *off) {
    (void)file;
    (void)off;
    if (wait_event_interruptible_timeout(vci_wait_queue, g_data_ready,
                                         msecs_to_jiffies(1000)) == 0) {
        return -ETIMEDOUT;
    }
    if (copy_to_user(buf, &g_legacy_data, sizeof(obd_data_t))) {
        return -EFAULT;
    }
    g_data_ready = false;
    return sizeof(obd_data_t);
}

static long legacy_ioctl(struct file *file, unsigned int cmd, unsigned long arg) {
    (void)file;
    int pid;

    switch (cmd) {
        case SET_PID:
            if (copy_from_user(&pid, (int __user *)arg, sizeof(pid))) {
                return -EFAULT;
            }
            g_active_pid = (uint32_t)pid;
            {
                vci_frame_t frame;
                (void)memset(&frame, 0, sizeof(vci_frame_t));
                frame.can_id = 0x7DF;
                frame.dlc = 8;
                frame.data[0] = 0x02;
                frame.data[1] = 0x01;
                frame.data[2] = (uint8_t)(g_active_pid & 0xFFU);
                vci_send_frame(&frame);
            }
            return 0;
        case GET_ALL_DATA:
            if (copy_to_user((obd_data_t __user *)arg, &g_legacy_data, sizeof(obd_data_t))) {
                return -EFAULT;
            }
            return 0;
        default:
            return -ENOTTY;
    }
}

/* ---------------------------------------------------------------------------
 * File operations registration
 * ------------------------------------------------------------------------- */
static const struct file_operations vci_fops = {
    .owner          = THIS_MODULE,
    .unlocked_ioctl = vci_ioctl,
    .mmap           = vci_mmap,
};

static const struct file_operations legacy_fops = {
    .owner          = THIS_MODULE,
    .unlocked_ioctl = legacy_ioctl,
    .read           = legacy_read,
};

static int __init obd_init(void) {
    /* Allocate the master shared region as physically contiguous pages */
    g_vci_shm = (automotive_data_t *)alloc_pages_exact(
        PAGE_ALIGN(sizeof(automotive_data_t)), GFP_KERNEL);
    if (g_vci_shm == NULL) {
        return -ENOMEM;
    }
    (void)memset(g_vci_shm, 0, sizeof(automotive_data_t));

    major_vci = register_chrdev(0, DRIVER_NAME, &vci_fops);
    if (major_vci < 0) {
        free_pages_exact(g_vci_shm, PAGE_ALIGN(sizeof(automotive_data_t)));
        g_vci_shm = NULL;
        return major_vci;
    }

    major_legacy = register_chrdev(0, LEGACY_DEVICE, &legacy_fops);
    if (major_legacy < 0) {
        unregister_chrdev(major_vci, DRIVER_NAME);
        free_pages_exact(g_vci_shm, PAGE_ALIGN(sizeof(automotive_data_t)));
        g_vci_shm = NULL;
        return major_legacy;
    }

    g_rx_filter = DEFAULT_RX_ID;
    g_fd_mode = 0U;
    g_active_pid = 0x0CU;
    g_data_ready = false;

    /* Register the CAN receive callback */
    {
        struct net_device *dev = get_can_dev();
        if (dev) {
            int err = can_rx_register(&init_net, dev, g_rx_filter, DEFAULT_MASK,
                                      vci_can_rx_handler, NULL, "obd_vci", NULL);
            if (err == 0) {
                g_vci_shm->status_mask |= VCI_STAT_CONNECTED;
            }
            dev_put(dev);
        }
    }

    pr_info("obd_vci: driver registered (majors %d / %d)\n", major_vci, major_legacy);
    return 0;
}

static void __exit obd_exit(void) {
    struct net_device *dev = get_can_dev();
    if (dev) {
        can_rx_unregister(&init_net, dev, g_rx_filter, DEFAULT_MASK,
                          vci_can_rx_handler, NULL);
        dev_put(dev);
    }

    if (major_legacy > 0) {
        unregister_chrdev(major_legacy, LEGACY_DEVICE);
    }
    if (major_vci > 0) {
        unregister_chrdev(major_vci, DRIVER_NAME);
    }
    if (g_vci_shm != NULL) {
        free_pages_exact(g_vci_shm, PAGE_ALIGN(sizeof(automotive_data_t)));
        g_vci_shm = NULL;
    }
    pr_info("obd_vci: driver unloaded\n");
}

module_init(obd_init);
module_exit(obd_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("K-OBD-Pi VCI kernel driver: mmap shared region + CAN ioctls");
