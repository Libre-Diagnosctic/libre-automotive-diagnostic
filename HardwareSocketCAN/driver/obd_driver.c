#include <linux/module.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/can.h>
#include <linux/can/core.h>
#include <linux/netdevice.h>
#include <linux/wait.h>
#include "obd_ioctl.h"

#define DEVICE_NAME "obd_data"

static int major;
static obd_data_t shared_data;
static bool data_ready = false;
static DECLARE_WAIT_QUEUE_HEAD(obd_wait_queue);

// Функция за изпращане на CAN заявка
static void send_can_msg(int pid) {
    struct sk_buff *skb;
    struct can_frame *frame;
    struct net_device *dev = dev_get_by_name(&init_net, "can0");
    if (!dev) return;

    skb = alloc_skb(sizeof(struct can_frame), GFP_ATOMIC);
    if (skb) {
        skb->dev = dev;
        skb->protocol = htons(ETH_P_CAN);
        
        // Вземаме указател към данните и зануляваме рамката
        frame = (struct can_frame *)skb_put(skb, sizeof(struct can_frame));
        memset(frame, 0, sizeof(struct can_frame));
        
        // Стандартен начин за задаване на ID и дължина (DLC)
        frame->can_id = 0x7DF; 
        frame->len = 8;        // Директно задаваме дължината
        
        // OBD-II протокол: 02 (2 байта следват), 01 (Mode 1), PID
        frame->data[0] = 0x02; 
        frame->data[1] = 0x01; 
        frame->data[2] = pid;
        
        dev_queue_xmit(skb);
    }
    dev_put(dev);
}
static void can_rx_handler(struct sk_buff *skb, void *data) {
    struct can_frame *frame = (struct can_frame *)skb->data;
    
    // Проверка за валиден Mode 1 отговор (0x41)
    if (frame->data[1] != 0x41) return;
    
    if (frame->data[2] == 0x0C) { // RPM
        shared_data.rpm = ((frame->data[3] << 8) | frame->data[4]) / 4;
    }
    if (frame->data[2] == 0x0D) { // Speed
        shared_data.speed = frame->data[3];
    }
        
    data_ready = true;
    wake_up_interruptible(&obd_wait_queue);
}
// Преименувана функция, за да не се дублира с ядрото
static long my_obd_ioctl(struct file *file, unsigned int cmd, unsigned long arg) {
    int pid;
    if (cmd == SET_PID) {
        if (copy_from_user(&pid, (int __user *)arg, sizeof(pid))) return -EFAULT;
        send_can_msg(pid);
    } else if (cmd == GET_ALL_DATA) {
        if (copy_to_user((obd_data_t __user *)arg, &shared_data, sizeof(obd_data_t))) return -EFAULT;
    }
    return 0;
}

static ssize_t obd_read(struct file *file, char __user *buf, size_t len, loff_t *off) {
    if (wait_event_interruptible_timeout(obd_wait_queue, data_ready, msecs_to_jiffies(1000)) == 0) 
        return -ETIMEDOUT;
    if (copy_to_user(buf, &shared_data, sizeof(obd_data_t))) return -EFAULT;
    data_ready = false;
    return sizeof(obd_data_t);
}

static struct file_operations fops = {
    .unlocked_ioctl = my_obd_ioctl,
    .read = obd_read,
    .owner = THIS_MODULE,
};

static int __init obd_init(void) {
    struct net_device *dev;
    major = register_chrdev(0, DEVICE_NAME, &fops);
    
    dev = dev_get_by_name(&init_net, "can0");
    if (dev) {
        // Добавен NULL за новия параметър в can_rx_register
        can_rx_register(&init_net, dev, 0x7E8, 0x7FF, can_rx_handler, NULL, "obd_drv", NULL);
        dev_put(dev);
    }
    return 0;
}

static void __exit obd_exit(void) {
    struct net_device *dev = dev_get_by_name(&init_net, "can0");
    if (dev) {
        can_rx_unregister(&init_net, dev, 0x7E8, 0x7FF, can_rx_handler, NULL);
        dev_put(dev);
    }
    unregister_chrdev(major, DEVICE_NAME);
}

module_init(obd_init);
module_exit(obd_exit);
MODULE_LICENSE("GPL");
