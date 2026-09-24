
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>       
#include <linux/fs.h>           
#include <linux/errno.h>        
#include <linux/types.h>        
#include <linux/fcntl.h>        
#include <asm/uaccess.h>
#include <linux/mm.h>
#include <linux/memory_hotplug.h>
#include <linux/pageblock-flags.h>

#include "phys_mem.h"           
#include "phys_mem_int.h"           
#include "page_claiming.h"           

#define OFFLINE_AT_ONCE (1 << MAX_ORDER)

static int hotplug_bounce(u64 address)
{
	int ret;

	ret = remove_memory(address, OFFLINE_AT_ONCE << PAGE_SHIFT);
	if (!ret) {
		ret = online_pages(address >> PAGE_SHIFT, OFFLINE_AT_ONCE);
		if (ret) {
			pr_emerg("unclaim failed for pfn %08llx: ret %d\n",
				 address >> PAGE_SHIFT, ret);
		}
		ret = 0; 
	}
	return ret;
}

static u64 last_addr = -1;

int free_pages_via_hotplug(struct page *requested_page,
			   unsigned int allowed_sources,
			   struct page **allocated_page,
			   unsigned long *actual_source)
{
	if (allowed_sources & SOURCE_HOTPLUG) {
		unsigned long pfn = page_to_pfn(requested_page);
		u64 address = pfn << PAGE_SHIFT;

#if 0

		if (page_to_pfn(requested_page) < (0x8000000 >> PAGE_SHIFT))
			return CLAIMED_TRY_NEXT;
		if (page_to_pfn(requested_page) >= (0x10000000 >> PAGE_SHIFT))
			return CLAIMED_TRY_NEXT;
#endif

		u64 realaddress = address &
			~(((unsigned long)OFFLINE_AT_ONCE << PAGE_SHIFT) - 1UL);

		if (realaddress != last_addr) {
			last_addr = realaddress;

			if (hotplug_bounce(realaddress)) {
				if (allowed_sources & SOURCE_SHAKING) {

					//	LZU DSLAB CHANGE
					shake_page(requested_page);
					hotplug_bounce(realaddress);

				}
			}
		}
	}

	return CLAIMED_TRY_NEXT;
}

