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



module_init(obd_init);
module_exit(obd_exit);
MODULE_LICENSE("GPL");
