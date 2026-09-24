
#define DRIVER_AUTHOR "Jens Neuhalfen <jens@neuhalfen.name>"
#define DRIVER_DESC   "Accessing raw memory from userspace, but in a controlled manner."

#define CHAR_DEVICE_NAME "phys_mem"
#define DEVICE_CLASS_NAME "phys_mem"
#define DEVICE_FILE_NAME "phys_mem"

#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>	
#include <linux/slab.h>		
#include <linux/fs.h>		
#include <linux/errno.h>	
#include <linux/types.h>	
#include <linux/proc_fs.h>
#include <linux/fcntl.h>	
#include <linux/aio.h>
#include <asm/uaccess.h>
#include <linux/mm.h>
#include <linux/device.h>

#include "phys_mem_int.h"           

int phys_mem_major = PHYS_MEM_MAJOR;
int phys_mem_devs = 1; 

static struct class *device_class;

struct phys_mem_dev *phys_mem_devices; 

void phys_mem_cleanup(void);

// LZU DSLAB CHANGE

struct kmem_cache *session_mem_cache;

void free_page_stati(struct phys_mem_session *session)
{
	if (session->frame_stati) {
		if (session->num_frame_stati) {
			size_t i;

			for (i = 0; i < session->num_frame_stati; i++) {
				struct page *p = session->frame_stati[i].page;
				if (p) {
					session->frame_stati[i].page = NULL;

					if (session->frame_stati[i].actual_source
					    == SOURCE_HOTPLUG_CLAIM) {
						// LZU DSLAB CHANGE

						continue;
					} else if (page_count(p)) {
#if 0
						pr_debug("Session %llu: Freeing page 0x%08lx @%lu with page_count %u\n",
							 session->session_id,
							 page_to_pfn(p), i,
							 page_count(p));
#endif
						__free_pages(p, 0);
					} else {
						pr_warn("Session %llu: NOT freeing page 0x%08lx @%lu with page_count %u\n",
							session->session_id,
							page_to_pfn(p), i,
							page_count(p));
					}
				}
			}
		}
		SESSION_FREE_FRAME_STATI(session->frame_stati);
	}

	session->num_frame_stati = 0;
	session->frame_stati = NULL;
}

static void phys_mem_setup_cdev(struct phys_mem_dev *dev, int index)
{
	int err, devno = MKDEV(phys_mem_major, index);

	cdev_init(&dev->cdev, &phys_mem_fops);
	dev->cdev.owner = THIS_MODULE;
	dev->cdev.ops = &phys_mem_fops;
	err = cdev_add(&dev->cdev, devno, 1);

	if (err)
		pr_notice("Error %d adding "CHAR_DEVICE_NAME"%d",
			  err, index);
}

#define PRINT_SIZE(t)  pr_notice("sizeof(%s) = %lu\n", #t ,sizeof(t))

int phys_mem_init(void)
{
	int result, i;
	dev_t dev = MKDEV(phys_mem_major, 0);

	if (phys_mem_major)
		result = register_chrdev_region(dev, phys_mem_devs,
						CHAR_DEVICE_NAME);
	else {
		result = alloc_chrdev_region(&dev, 0, phys_mem_devs,
					     CHAR_DEVICE_NAME);
		phys_mem_major = MAJOR(dev);
	}
	if (result < 0)
		return result;

	// LZU DSLAB CHANGE
	device_class = class_create(DEVICE_CLASS_NAME);
	if (IS_ERR(device_class)) {
		pr_warn("no udev support\n");
	}

	phys_mem_devices = kmalloc(phys_mem_devs * sizeof(struct phys_mem_dev),
				   GFP_KERNEL);
	if (!phys_mem_devices) {
		result = -ENOMEM;
		goto fail_malloc;
	}
	memset(phys_mem_devices, 0,
	       phys_mem_devs * sizeof(struct phys_mem_dev));
	for (i = 0; i < phys_mem_devs; i++) {
		sema_init(&phys_mem_devices[i].sem, 1);
		phys_mem_setup_cdev(phys_mem_devices + i, i);
		if (!IS_ERR(device_class)) {
			device_create(device_class, NULL,
				      MKDEV(phys_mem_major, i),
				      NULL, CHAR_DEVICE_NAME);
		}

	}

	session_mem_cache = kmem_cache_create("session_mem",
					      sizeof(struct phys_mem_session),
					      0, SLAB_HWCACHE_ALIGN, NULL); 
	if (!session_mem_cache) {
		phys_mem_cleanup();
		return -ENOMEM;
	}

	PRINT_SIZE(void *);
	PRINT_SIZE(short);
	PRINT_SIZE(int);
	PRINT_SIZE(long);
	PRINT_SIZE(long long);

	pr_notice("IOCTL for PHYS_MEM_IOC_MARK_FRAME_BAD: 0x%lx\n",
				PHYS_MEM_IOC_MARK_FRAME_BAD);
	PRINT_SIZE(struct mark_page_poison);

	pr_notice("IOCTL for PHYS_MEM_IOC_REQUEST_PAGES: 0x%lx\n",
				PHYS_MEM_IOC_REQUEST_PAGES);
	PRINT_SIZE(struct phys_mem_request);
	PRINT_SIZE(struct phys_mem_frame_status);
	PRINT_SIZE(struct phys_mem_frame_request);

	return 0; 

fail_malloc:
	unregister_chrdev_region(dev, phys_mem_devs);
	return result;
}

void phys_mem_cleanup(void)
{
	int i;

	if (!IS_ERR(device_class)) {
		for (i = 0; i < phys_mem_devs; i++)
			device_destroy(device_class, MKDEV(phys_mem_major, i));
		class_destroy(device_class);
	}

	for (i = 0; i < phys_mem_devs; i++)
		cdev_del(&phys_mem_devices[i].cdev);
	kfree(phys_mem_devices);

	if (session_mem_cache)
		kmem_cache_destroy(session_mem_cache);

	unregister_chrdev_region(MKDEV(phys_mem_major, 0), phys_mem_devs);
}

MODULE_LICENSE("GPL");
MODULE_AUTHOR(DRIVER_AUTHOR);
MODULE_DESCRIPTION(DRIVER_DESC);

module_init(phys_mem_init);
module_exit(phys_mem_cleanup);
