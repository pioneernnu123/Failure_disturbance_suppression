#include <linux/module.h>
#define INCLUDE_VERMAGIC
#include <linux/build-salt.h>
#include <linux/elfnote-lto.h>
#include <linux/export-internal.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

#ifdef CONFIG_UNWINDER_ORC
#include <asm/orc_header.h>
ORC_HEADER;
#endif

BUILD_SALT;
BUILD_LTO_INFO;

MODULE_INFO(vermagic, VERMAGIC_STRING);
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

#ifdef CONFIG_RETPOLINE
MODULE_INFO(retpoline, "Y");
#endif



static const struct modversion_info ____versions[]
__used __section("__versions") = {
	{ 0xc66dfc17, "mm_page_order" },
	{ 0xe3ec2f2b, "alloc_chrdev_region" },
	{ 0x88db9f48, "__check_object_size" },
	{ 0x13c49cc2, "_copy_from_user" },
	{ 0xe913dcd5, "class_destroy" },
	{ 0x80f913fc, "up" },
	{ 0xe422adc0, "pgtable_l5_enabled" },
	{ 0xffa5ac24, "root_mem_cgroup" },
	{ 0x14825044, "remap_pfn_range" },
	{ 0x37a0cba, "kfree" },
	{ 0x1e4d5997, "kmem_cache_create" },
	{ 0xf352023f, "memory_cgrp_subsys_enabled_key" },
	{ 0x267181df, "_raw_spin_lock_irqsave" },
	{ 0xcbd4898c, "fortify_panic" },
	{ 0x6b2dc060, "dump_stack" },
	{ 0x92997ed8, "_printk" },
	{ 0xbb21527, "kernel_map" },
	{ 0xf0fdf6cb, "__stack_chk_fail" },
	{ 0xb7cd731d, "__free_pages" },
	{ 0x63cfe2f5, "mm_buddy_expand" },
	{ 0x355a7a74, "get_pfnblock_flags_mask" },
	{ 0x19046583, "kmem_cache_alloc" },
	{ 0xeb6eb87, "add_taint" },
	{ 0xac29efff, "cdev_add" },
	{ 0xbcb36fe4, "hugetlb_optimize_vmemmap_key" },
	{ 0x3336db58, "is_free_buddy_page" },
	{ 0x31997b93, "down_write" },
	{ 0x83b084ae, "up_write" },
	{ 0x1a7bcf87, "device_create" },
	{ 0x7d136cd9, "down" },
	{ 0xac8353a0, "class_create" },
	{ 0x3199fbeb, "mem_section" },
	{ 0x8dcff862, "kmem_cache_free" },
	{ 0xbe0c6fe, "pgtable_l4_enabled" },
	{ 0x9049d4a6, "__list_del_entry_valid_or_report" },
	{ 0x79ebe2dd, "phys_ram_base" },
	{ 0xffb6a31, "_raw_spin_unlock_irqrestore" },
	{ 0xfb578fc5, "memset" },
	{ 0xdaca820e, "dynamic_preempt_schedule" },
	{ 0x6b10bee1, "_copy_to_user" },
	{ 0xe2d5255a, "strcmp" },
	{ 0x526c3a6c, "jiffies" },
	{ 0x999e8297, "vfree" },
	{ 0x6091b333, "unregister_chrdev_region" },
	{ 0x8dd1be3, "device_destroy" },
	{ 0x2cf56265, "__dynamic_pr_debug" },
	{ 0x1a61a219, "down_interruptible" },
	{ 0xa0abb1bc, "__mod_zone_page_state" },
	{ 0x76472c7f, "node_data" },
	{ 0x3fd78f3b, "register_chrdev_region" },
	{ 0x77358855, "iomem_resource" },
	{ 0xd6ee688f, "vmalloc" },
	{ 0xe354a97a, "cdev_init" },
	{ 0xeb233a45, "__kmalloc" },
	{ 0xe4d78d05, "cdev_del" },
	{ 0xbfdb5ce4, "kmem_cache_destroy" },
	{ 0xb74d1240, "module_layout" },
};

MODULE_INFO(depends, "");


MODULE_INFO(srcversion, "8868977E378E31558BCCB92");
