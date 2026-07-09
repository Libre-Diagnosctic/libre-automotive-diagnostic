/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: obd_driver.mod.c
 * AUTHOR: Libre-Diagnostic
 * STANDARD: MISRA-C:2012 Compliance
 * DESCRIPTION: High-performance automotive gateway for Raspberry Pi.
 * REVISION: 1.0.0
 */

#include <linux/module.h>
#include <linux/export-internal.h>
#include <linux/compiler.h>

MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};



static const struct modversion_info ____versions[]
__used __section("__versions") = {
	{ 0xe2964344, "__wake_up" },
	{ 0xf70e4a4d, "preempt_schedule_notrace" },
	{ 0x418c10ec, "__register_chrdev" },
	{ 0x3e9f8208, "init_net" },
	{ 0xc5c60c2b, "dev_get_by_name" },
	{ 0xfd537580, "can_rx_register" },
	{ 0x4ebab782, "can_rx_unregister" },
	{ 0x6bc3fbc0, "__unregister_chrdev" },
	{ 0xfe487975, "init_wait_entry" },
	{ 0x8ddd8aad, "schedule_timeout" },
	{ 0x8c26d495, "prepare_to_wait_event" },
	{ 0x92540fbf, "finish_wait" },
	{ 0x6cbbfc54, "__arch_copy_to_user" },
	{ 0xf0fdf6cb, "__stack_chk_fail" },
	{ 0x12a4e128, "__arch_copy_from_user" },
	{ 0xc99f9494, "__alloc_skb" },
	{ 0x4d74cf4e, "skb_put" },
	{ 0xf901f51b, "__dev_queue_xmit" },
	{ 0x474e54d2, "module_layout" },
};

MODULE_INFO(depends, "can");


MODULE_INFO(srcversion, "CCE80F009A9163E45840117");
